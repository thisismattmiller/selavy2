import re
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item, String, URL, Time, Quantity, ExternalID, MonolingualText
from wikibaseintegrator.models import Reference, References, Qualifiers
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseDatatype
from wikibaseintegrator.wbi_helpers import remove_claims

# Cache for property datatypes: { 'P46': 'time', 'P254': 'wikibase-item', ... }
_property_type_cache = {}


def get_property_datatype(wbi, property_qid):
    """Look up a property's datatype from Wikibase, with caching.

    Args:
        wbi: WikibaseIntegrator instance
        property_qid: Property ID like 'P46'

    Returns:
        str: The datatype string, e.g. 'wikibase-item', 'string', 'time', 'quantity', 'url', 'external-id'
    """
    if property_qid in _property_type_cache:
        return _property_type_cache[property_qid]

    try:
        prop = wbi.property.get(entity_id=property_qid)
        raw = prop.datatype
        # Handle WikibaseDatatype enum or plain string
        if isinstance(raw, WikibaseDatatype):
            datatype = raw.value
        elif hasattr(raw, 'value'):
            datatype = raw.value
        else:
            datatype = str(raw)
        _property_type_cache[property_qid] = datatype
        print(f"Property {property_qid} datatype: {datatype}", flush=True)
        return datatype
    except Exception as e:
        print(f"Could not determine datatype for {property_qid}: {e}", flush=True)
        return None


def build_claim_for_datatype(wbi, property_qid, object_qid, object_literal, references=None, qualifiers=None):
    """Build the correct WBI claim based on the property's datatype.

    Args:
        wbi: WikibaseIntegrator instance
        property_qid: The property ID
        object_qid: QID if the value is an item reference
        object_literal: Literal value (string, number, date, etc.)
        references: Optional References object
        qualifiers: Optional Qualifiers object

    Returns:
        A WBI datatype claim object
    """
    datatype = get_property_datatype(wbi, property_qid)
    kwargs = {'prop_nr': property_qid}
    if references:
        kwargs['references'] = references
    if qualifiers:
        kwargs['qualifiers'] = qualifiers

    if datatype == 'wikibase-item':
        if not object_qid:
            raise ValueError(f"Property {property_qid} expects an item but got object_qid={object_qid}")
        return Item(value=object_qid, **kwargs)

    elif datatype == 'time':
        # Convert literal to Wikibase time format
        time_val = str(object_literal or object_qid or '')
        # Handle bare year like '1967'
        if re.match(r'^\d{1,4}$', time_val):
            time_val = f'+{time_val.zfill(4)}-00-00T00:00:00Z'
        # Handle year-month like '1967-03'
        elif re.match(r'^\d{4}-\d{2}$', time_val):
            time_val = f'+{time_val}-00T00:00:00Z'
        # Handle full date like '1967-03-15'
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', time_val):
            time_val = f'+{time_val}T00:00:00Z'
        # Already formatted
        elif not time_val.startswith('+') and not time_val.startswith('-'):
            time_val = '+' + time_val
        return Time(time=time_val, **kwargs)

    elif datatype == 'quantity':
        amount = object_literal if object_literal is not None else object_qid
        return Quantity(amount=amount, **kwargs)

    elif datatype == 'url':
        url_val = str(object_literal or object_qid or '')
        return URL(value=url_val, **kwargs)

    elif datatype == 'external-id':
        val = str(object_literal or object_qid or '')
        return ExternalID(value=val, **kwargs)

    elif datatype == 'monolingualtext':
        val = str(object_literal or object_qid or '')
        return MonolingualText(text=val, language='en', **kwargs)

    elif datatype == 'string':
        val = str(object_literal or object_qid or '')
        return String(value=val, **kwargs)

    else:
        # Fallback: if object_qid is set, try Item; otherwise String
        if object_qid and not object_literal:
            return Item(value=object_qid, **kwargs)
        else:
            val = str(object_literal or object_qid or '')
            return String(value=val, **kwargs)


def create_document_item(wbi, label, description, instance_of_qids, project_qids):
    """Create a document item on Wikibase.

    Args:
        wbi: WikibaseIntegrator instance (already logged in)
        label: Document name/label
        description: Optional description
        instance_of_qids: List of QIDs for P1 (must include Q19069 for document)
        project_qids: List of project QIDs for P11

    Returns:
        str: QID of created item
    """
    new_item = wbi.item.new()
    new_item.labels.set('en', label)

    if description:
        new_item.descriptions.set('en', description)

    # P1: instanceOf
    for qid in instance_of_qids:
        if qid and str(qid).strip():
            new_item.claims.add(Item(prop_nr='P1', value=qid))

    # P11: project
    for qid in project_qids:
        if qid and str(qid).strip():
            new_item.claims.add(Item(prop_nr='P11', value=qid))

    result = new_item.write()
    return result.id


def create_block_item(wbi, label, document_qid, project_qids, block_id, s3_url, associated_entity_qids, block_text=''):
    """Create a block item on Wikibase.

    Args:
        wbi: WikibaseIntegrator instance
        label: Block label (e.g., "Document Name - Block 0")
        document_qid: Parent document QID
        project_qids: List of project QIDs for P11
        block_id: Local block ID number
        s3_url: S3 URL to block text
        associated_entity_qids: List of entity QIDs mentioned in block
        block_text: The block text (first 390 chars used for P19)

    Returns:
        str: QID of created block item
    """
    new_item = wbi.item.new()
    new_item.labels.set('en', label)

    # P1 = Q2013 (block)
    new_item.claims.add(Item(prop_nr='P1', value='Q2013'))

    # P24 = parent document
    new_item.claims.add(Item(prop_nr='P24', value=document_qid))

    # P17 = local block ID
    new_item.claims.add(String(prop_nr='P17', value=str(block_id)))

    # P19 = block text (first 250 characters, newlines replaced with spaces)
    if block_text:
        clean_text = ' '.join(block_text.split())[:250]
        if clean_text:
            new_item.claims.add(String(prop_nr='P19', value=clean_text))

    # P20 = block text URL
    new_item.claims.add(URL(prop_nr='P20', value=s3_url))

    # P11 = projects
    for qid in project_qids:
        if qid and str(qid).strip():
            new_item.claims.add(Item(prop_nr='P11', value=qid))

    # P21 = associated entities
    for qid in associated_entity_qids:
        if qid and str(qid).strip():
            new_item.claims.add(Item(prop_nr='P21', value=qid))

    result = new_item.write()
    return result.id


def create_statement_with_reference(wbi, subject_qid, property_qid, object_qid, object_literal, block_qid, contexts=None):
    """Create a statement on a subject entity with a P26 reference to the block.

    Args:
        wbi: WikibaseIntegrator instance
        subject_qid: The entity to add the statement to
        property_qid: The property (e.g., 'P5')
        object_qid: The object entity QID (if item type), or None
        object_literal: The literal string value (if string type), or None
        block_qid: The block QID for the P26 reference
        contexts: List of qualifier dicts [{propertyQid, value, valueType}]

    Returns:
        str: The claim GUID of the created statement
    """
    # Build the reference: P26 -> block QID
    reference = Reference()
    reference.add(Item(prop_nr='P26', value=block_qid))
    references = References()
    references.add(reference)

    # Build qualifiers from contexts
    qualifiers = Qualifiers()
    if contexts:
        for ctx in contexts:
            if not ctx.get('propertyQid') or not ctx.get('value'):
                continue
            ctx_datatype = get_property_datatype(wbi, ctx['propertyQid'])
            if ctx_datatype == 'wikibase-item':
                qualifiers.add(Item(prop_nr=ctx['propertyQid'], value=ctx['value']))
            elif ctx_datatype == 'time':
                time_val = str(ctx['value'])
                if re.match(r'^\d{1,4}$', time_val):
                    time_val = f'+{time_val.zfill(4)}-00-00T00:00:00Z'
                elif not time_val.startswith('+') and not time_val.startswith('-'):
                    time_val = '+' + time_val
                qualifiers.add(Time(prop_nr=ctx['propertyQid'], time=time_val))
            else:
                qualifiers.add(String(prop_nr=ctx['propertyQid'], value=str(ctx['value'])))

    # Build the main claim using the property's actual datatype
    claim = build_claim_for_datatype(wbi, property_qid, object_qid, object_literal, references=references, qualifiers=qualifiers)

    # Create a fresh item with only the new claim to avoid serialization
    # issues with existing claims on the entity
    item = wbi.item.new()
    item.id = subject_qid
    item.claims.add(claim, action_if_exists=ActionIfExists.FORCE_APPEND)
    result = item.write()

    # Find the claim GUID - get the last claim added for this property
    claims_for_prop = result.claims.get(property_qid)
    if claims_for_prop:
        return claims_for_prop[-1].id
    return None


def delete_claim(wbi, entity_qid, claim_id):
    """Remove a specific claim from an entity.

    Uses wbremoveclaims API directly so it doesn't need to load the entity.

    Args:
        wbi: WikibaseIntegrator instance
        entity_qid: The entity QID that has the claim
        claim_id: The claim GUID to remove
    """
    remove_claims(claim_id, login=wbi.login)


def delete_block_item(wbi, block_qid):
    """Clear a block item (remove all claims, mark as deleted).

    Wikibase doesn't support true deletion via API for non-admins,
    so we clear the item and mark it as deleted.

    Args:
        wbi: WikibaseIntegrator instance
        block_qid: The block item QID to delete
    """
    item = wbi.item.get(entity_id=block_qid)
    # Remove all claims
    for prop_nr in list(item.claims.claims.keys()):
        for claim in item.claims.get(prop_nr):
            claim.remove()
    item.labels.set('en', f'[DELETED] {block_qid}')
    item.descriptions.set('en', 'Deleted by publish undo')
    item.write()
