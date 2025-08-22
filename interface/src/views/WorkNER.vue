<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/LoginModal.vue'
import { mapWritableState } from "pinia";
import JobStatus from '@/components/JobStatus.vue'

import MD5 from 'crypto-js/md5';


function asyncEmit(eventName, data) {
  return new Promise(function (resolve, reject) {
    socket.emit(eventName, data, (response) => {
      resolve(response);
    })
    setTimeout(reject, 1000 * 300);
  });
}
function unescapeHtmlEntities(escapedString) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(escapedString, 'text/html');
    return doc.documentElement.textContent;
}

export default {
  name: 'WorkNER',
  props: {
    documentId: {
      type: String,
      required: true
    },
  },
  components: {
    LoginModal,
    JobStatus
  },
  data() {
    return {
      documentDiffs: null,
      documentMarkup: "",
      documentOrginal: "",
      judgeStatus: null,
      workflowComplete: false,

      typeMap: {},  // holds the string -> qid mapping for class/type from the backend
      typeAlignment: {},  // the alignment to the current list of types
      editingType: null,  // tracks which type is currently being edited
      autoSave: true,  // auto-save entities when they change

      semlabClasses: [],

      showMoreBlocks: {}, // used to track which entities have "show more blocks" expanded
      expandedDescriptions: {}, // used to track which bad match descriptions are expanded
      wikidataSearchQueries: {}, // track search queries for each entity
      wikidataSearchResults: {}, // track search results for each entity
      wikidataSearchLoading: {}, // track loading state for each entity
      wikidataSearchTimers: {}, // debounce timers for search
      wikidataSelectedIndex: {}, // track selected index for keyboard navigation
      semlabSearchQueries: {}, // track search queries for SemLab
      semlabSearchResults: {}, // track search results for SemLab
      semlabSearchLoading: {}, // track loading state for SemLab
      semlabSearchTimers: {}, // debounce timers for SemLab search
      semlabSelectedIndex: {}, // track selected index for SemLab keyboard navigation

      useProjectBulkAlign: null, // used to track which project is selected for bulk alignment

      activeEntity: null, // used to track which entity is active for details view

      bulkInstanceOfBase: null,
      bulkInstanceOfDoc: null, // used to track which type is selected for bulk alignment

      blocks: [],
      entities: {},
      entitiesByType: {},
      projects: [], // list of SemLab projects


      statusProjectReconcile:null,

      statusClassReconcile: null,

      statusLabelNormalize:null,
      normalizingType: null, // tracks which type is currently being normalized
      isSavingEntities: false,
      entitiesHaveChanges: false,
      activeTab: 'reconcile', // tracks the active tab: 'reconcile', 'mint', or 'data'
      defaultProject: null, // stores the selected default project for minting


      workQueue1: false,
      workQueue2: false,
      workQueue3: false,
      workQueueTimer: null,
      workComplete: false,



      baseWorkQueue1: false,
      baseWorkQueue2: false,
      baseWorkQueue3: false,
      baseWorkQueueTimer: null,
      baseWorkComplete: false,

    }
  },
  computed: {
   
   //  ...mapStores(useUserStore),
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user']),
    
    // Filter entities for mint table - only show entities with wikiQid but no qid, or minted=true
    entitiesByTypeForMint() {
      const filtered = {};
      
      for (const type in this.entitiesByType) {
        const mintEntities = this.entitiesByType[type].filter(entity => {
          // Include if: has wikiQid but no qid, OR has minted flag set to true
          return (entity.wikiQid && !entity.qid) || entity.minted === true;
        }).map(entity => {
          // Create a copy of the entity with mintData
          const entityCopy = { ...entity };
          
          // Get unique variant labels
          const variantLabels = new Set();
          if (entity.labels && Array.isArray(entity.labels)) {
            entity.labels.forEach(label => variantLabels.add(label));
          }
          if (entity.normalizedLabel) {
            variantLabels.add(entity.normalizedLabel);
          }
          if (entity.useLabel) {
            variantLabels.add(entity.useLabel);
          }
          
          // Get the instanceOf QID from typeMap based on entity's type
          const instanceOfQid = entity.type ? this.typeMap[entity.type.toLowerCase()] : null;
          
          // Initialize mintData with values from entity
          entityCopy.mintData = {
            authLabel: entity.wikiLabel || entity.entity || '',
            description: entity.wikiDescription || '',
            variantLabel: Array.from(variantLabels),
            project: this.defaultProject ? [this.defaultProject] : [],
            instanceOf: instanceOfQid ? [instanceOfQid] : [],
            wikidataQid: entity.wikiQid || ''
          };
          
          return entityCopy;
        });
        
        // Only include type if it has matching entities
        if (mintEntities.length > 0) {
          filtered[type] = mintEntities;
        }
      }
      
      return filtered;
    }
 
 
   },
   
   watch: {
    // don't intialize until we have a user
    user(newUser, oldUser) {
      this.initialize()
    },
    entities: {
      deep: true,
      handler(newVal, oldVal) {
        if (oldVal && Object.keys(oldVal).length > 0) {
          this.entitiesHaveChanges = true;
          if (this.autoSave) {
            this.sendFilteredEntities();
          }
        }
      }
    }
  },
   
   
  methods: {
    // Add methods here

    async initialize() {

     
      socket.emit('get_ner', {doc:this.documentId, user:this.user}, (response) => {
        console.log("get_ner response", response)
        if (response.success) {
          // console.log("ner", response.ner)

          // populate the lookup tables by type
          this.blocks = response.ner.blocks
          this.entities = response.ner.entities
          this.typeMap = response.ner.class_map
          
          // Initialize hidden property for each entity
          for (let id in this.entities) {
            if (this.entities[id].hidden === undefined) {
              this.entities[id].hidden = false;
            }
          }

          // console.log("this.entities", this.entities)

          this.buildEntitesByType()

        } else {
          console.error("Error fetching document diffs:", response.error);
        }
      });

      this.getSemlabProjects()

      this.setSemlabClasses()

      
   },

    editEntityLabel(entity) {
      // console.log("editEntityLabel", entity)
      if (entity.hidden){
        return false
      }
      entity.editing = entity.entity;
      this.$nextTick(() => {
        const input = document.getElementById('label-select-' + entity.internal_id + '-entity');
        if (input) {
          input.focus();
        }
      });
    },
    finishEditing(event, entity) {
      console.log("event",event)
      // if it is a keyboard event and it was the enter key continuer otherwise return
      if (event && (event.type === "keyup" && event.key === "Enter") || event.type === "blur") {
        // continue with the editing process
      } else {
        return;
      }

      // console.log("finishEditing", entity)
      entity.editing = false;
      if (entity.entity && entity.entity.length > 0){
        if (entity.useLabel){
          entity.useLabel = entity.entity;
        }
      }else{
        alert("Entity label cannot be empty")
      }
    },

    async retriveWikidataEntity(entity){

      this.findSemlabEntityByWikiQid(entity)

      try {

        let sparql = `SELECT ?entity ?entityLabel ?entityDescription ?image {
          VALUES (?entity) {(wd:${entity.wikiQid})}
          optional{
            ?entity wdt:P18 ?image.
          }
          SERVICE wikibase:label { 
            bd:serviceParam wikibase:language "en" .
          }
        } `;


        let sparqlUrl = `https://query.wikidata.org/sparql`;


        const sparqlResponse = await fetch(sparqlUrl, {
          method: 'POST',
          headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/sparql-results+json',
          'User-Agent': 'Selvy Reconciliation Tool/1.0 (semlab.io), user: thisismattmiller'
          },
          body: `query=${encodeURIComponent(sparql)}`
        });
        const sparqlData = await sparqlResponse.json();


        if (sparqlData.results && sparqlData.results.bindings) {
          for (const binding of sparqlData.results.bindings) {
            // Process each binding
            console.log("binding", binding  )
            if (binding.entityLabel && binding.entityLabel.value) {
              entity.wikiLabel = binding.entityLabel.value;
            }
            if (binding.entityDescription && binding.entityDescription.value) {
              entity.wikiDescription = binding.entityDescription.value;
            }
            if (binding.image && binding.image.value && binding.image.value.startsWith('http')) {
              entity.wikiThumbnailOrg = binding.image.value
              entity.wikiThumbnail = this.convertToThumbnail(binding.image.value)
            }
            break // only process the first binding

          }
        }
        console.log("entity", this.entities) 
        if (entity.wikiLabel){
          for (let e in this.entities){
            if (this.entities[e].internal_id == entity.internal_id){
              this.entities[e].wikiLabel = entity.wikiLabel;
            }
          }
        }
        if (entity.wikiDescription){
          for (let e in this.entities){
            if (this.entities[e].internal_id == entity.internal_id){
              this.entities[e].wikiDescription = entity.wikiDescription;
            }
          }
        }
        if (entity.wikiThumbnail){
          for (let e in this.entities){
            if (this.entities[e].internal_id == entity.internal_id){
              this.entities[e].wikiThumbnail = this.convertToThumbnail(entity.wikiThumbnail);
              this.entities[e].wikiThumbnailOrg = entity.wikiThumbnailOrg;
            }
          }
        }
      } catch (error) {
        console.error("Error fetching from Wikidata:", error);
        return null;
      }



    },

    convertMarkupToHtml(blockText, highlighId){
      let matches = Array.from(blockText.matchAll(/{.*?}/g))

      for (let match of matches) {
        let label = match[0].split('|')[0].replace('{', '').replace('}', '')
        let id = match[0].split('|')[1]
        let type = match[0].split('|')[2].replace('{', '').replace('}', '')

        let fullMarkupString = match[0]

        if (highlighId){
          if (id == highlighId){
            // highlight this one
            blockText = blockText.replace(fullMarkupString, `<span style="" class="block-highlight">${label}</span>`)
          }else{
            // don't highlight this one
            blockText = blockText.replace(fullMarkupString, `<span>${label}</span>`)
          }

        }else{
          // highlight everyone
          blockText = blockText.replace(fullMarkupString, `<span class="highlighted">${label}</span>`)
        }


      }
      return blockText

    },
    


    toggleQueue(){
      if (this.workQueueTimer === null){
        this.workQueueTimer = setInterval(() => {
          this.workWikidataQueue();
        }, 1000 * 1); // every 10 seconds
      }else{
        clearInterval(this.workQueueTimer)
        this.workQueueTimer = null
      }
    },
    toggleWikibaseQueue(){
      if (this.baseWorkQueueTimer === null){
        this.baseWorkQueueTimer = setInterval(() => {
          this.workWikibaseQueue();
        }, 1000 * 1); // every 10 seconds
      }else{
        clearInterval(this.baseWorkQueueTimer)
        this.baseWorkQueueTimer = null
      }
    },
    
    startEditingType(type) {
      this.editingType = type;
      this.$nextTick(() => {
        const select = document.querySelector('.type-alignment-select');
        if (select) {
          select.focus();
        }
      });
    },
    
    stopEditingType() {
      this.editingType = null;
    },
    
    getTypeStringFromQid(qid) {
      for (let [typeString, typeQid] of Object.entries(this.typeMap)) {
        if (typeQid === qid) {
          return typeString;
        }
      }
      return qid; // Return the QID if no match found
    },
    
    removeFromArray(array, index) {
      array.splice(index, 1);
    },
    
    decodeHtmlEntities(text) {
      if (!text) return text;
      const textarea = document.createElement('textarea');
      textarea.innerHTML = text;
      text = textarea.value;
      text = text.replace(/&amp;/g, '&'); // Decode &amp; to &
      text = text.replace(/&lt;/g, '<'); // Decode &lt; to <
      text = text.replace(/&gt;/g, '>'); // Decode &gt; to >
      text = text.replace(/&quot;/g, '"'); // Decode &quot; to "
      text = text.replace(/&#39;/g, "'"); // Decode &#39; to '
      
      return textarea.value;
    },
    
    toggleEntityVisibility(entity) {
      // Toggle the hidden property directly on the entity
      entity.hidden = !entity.hidden;
    },
    
    async processAllEntitiesWikidata(type) {
      const entities = this.entitiesByType[type];
      if (!entities || entities.length === 0) {
        console.log(`No entities found for type: ${type}`);
        return;
      }
      
      console.log(`Processing ${entities.length} entities of type ${type} through Wikidata`);
      
      for (let i = 0; i < entities.length; i++) {
        const entity = entities[i];
        console.log(`Processing entity ${i + 1}/${entities.length}: ${entity.entity}`);
        
        // Process the entity through Wikidata
        await this.workEntity(entity.internal_id, true);
        
        // Add a small delay to avoid overwhelming the API
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      
      console.log(`Completed processing all ${type} entities through Wikidata`);
    },
    
    async processAllEntitiesSemlab(type) {
      const entities = this.entitiesByType[type];
      if (!entities || entities.length === 0) {
        console.log(`No entities found for type: ${type}`);
        return;
      }
      
      console.log(`Processing ${entities.length} entities of type ${type} through SemLab`);
      
      for (let i = 0; i < entities.length; i++) {
        const entity = entities[i];
        console.log(`Processing entity ${i + 1}/${entities.length}: ${entity.entity}`);
        
        // Process the entity through SemLab
        await this.workBaseEntity(entity.internal_id, true);
        
        // Add a small delay to avoid overwhelming the API
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      
      console.log(`Completed processing all ${type} entities through SemLab`);
    },
    
    async normalizeLabelsByType(type) {
      const entities = this.entitiesByType[type];
      if (!entities || entities.length === 0) {
        console.log(`No entities found for type: ${type}`);
        return;
      }
      
      // Set the loading state for this type
      this.normalizingType = type;
      
      const BATCH_SIZE = 10;
      
      // Prepare entities data for normalization - need to find the key in this.entities
      let typeEntities = [];
      for (let entity of entities) {
        // Find the key in this.entities that matches this entity
        let entityKey = null;
        for (let eId in this.entities) {
          if (this.entities[eId].internal_id === entity.internal_id) {
            entityKey = eId;
            break;
          }
        }
        
        if (entityKey) {
          typeEntities.push({
            internal_id: entity.internal_id,
            labels: entity.labels,
            normalizedLabels: [],
            entityId: entityKey
          });
        }
      }
      
      console.log(`Normalizing labels for ${typeEntities.length} entities of type ${type}`);
      this.statusLabelNormalize = `Normalizing ${type} entities...`;
      
      const totalBatches = Math.ceil(typeEntities.length / BATCH_SIZE);
      
      for (let batchNum = 0; batchNum < totalBatches; batchNum++) {
        const startIdx = batchNum * BATCH_SIZE;
        const endIdx = Math.min(startIdx + BATCH_SIZE, typeEntities.length);
        const batchEntities = typeEntities.slice(startIdx, endIdx);
        
        this.statusLabelNormalize = `Working on ${type} batch ${batchNum + 1} of ${totalBatches}`;
        
        // Collect blocks text for context
        let sendBlocks = [];
        for (let batchEntity of batchEntities) {
          let entity = this.entities[batchEntity.entityId];
          if (entity.blocks && entity.blocks.length > 0) {
            if (sendBlocks.indexOf(entity.blocks[0]) == -1) {
              sendBlocks.push(entity.blocks[0]);
              if (entity.blocks[1]) {
                sendBlocks.push(entity.blocks[1]);
              }
            }
          } else {
            console.warn(`Entity ${entity.internal_id} has no blocks, skipping normalization.`);
          }
        }
        let allBlockText = sendBlocks.map(b => this.blocks[b].clean).join(" ");
        
        // Prepare the list for the LLM
        const sendList = batchEntities.map(e => ({
          internal_id: e.internal_id,
          labels: e.labels,
          normalizedLabels: []
        }));
        
        let prompt = `Normalize the words in this list of objects, normalize the labels in the key "labels", if they have honorifics remove them, if they are a shortened version of the entity make it the fuller form, make the term more search friendly if you were searching Wikipedia for the term. Do not invent names or expand the word without strong evidence, if you cannot expand it return it as it is. After the JSON below is the text the names are found in, use this text to help expand the name. Return JSON Only.`
        prompt += `\n\nJSON:\n`
        prompt += JSON.stringify(sendList, null, 2);
        prompt += `\n\nText:\n"${allBlockText}"\n\n`
        console.log(`Processing ${type} batch ${batchNum + 1}/${totalBatches}:`, prompt)
        
        let response = null;
        try {
          response = await asyncEmit('ask_llm_normalize_labels', prompt);
        } catch (error) {
          console.error(`Error normalizing labels for ${type} batch ${batchNum + 1}:`, error);
          alert(`There was an error normalizing the labels for ${type} batch ${batchNum + 1}, please try again.`);
          this.statusLabelNormalize = null;
          this.normalizingType = null;
          return;
        }
        
        if (!response || !response.success || !response.response) {
          console.error(`Error normalizing labels for ${type} batch ${batchNum + 1}:`, response?.error);
          alert(`There was an error normalizing the labels for ${type} batch ${batchNum + 1}, please try again.`);
          this.statusLabelNormalize = null;
          this.normalizingType = null;
          return;
        }
        
        // Process the response
        for (let batchEntity of batchEntities) {
          let entity = this.entities[batchEntity.entityId];
          let lookForId = batchEntity.internal_id;
          let found = response.response.find(item => item.internal_id === lookForId);
          if (found) {
            if (found.normalizedLabels && found.normalizedLabels.length > 0) {
              if (found.normalizedLabels[0] && found.labels.indexOf(found.normalizedLabels[0]) == -1) {
                console.log("Adding normalized label", found.normalizedLabels[0], "to entity", entity.internal_id, "replacing", found.labels[0]);
                entity.normalizedLabel = found.normalizedLabels[0];
                entity.useLabel = found.normalizedLabels[0];
              }
            }
          }
        }
        
        // Small delay between batches
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      
      this.statusLabelNormalize = null;
      this.normalizingType = null;
      console.log(`Completed normalizing labels for ${type} entities`);
    },
    
    async findSemlabEntityByWikiQid(entity) {
      if (!entity.wikiQid) {
        console.log('No wikiQid provided for entity');
        return null;
      }
      
      try {
        // SPARQL query to find SemLab entity where P8 equals the Wikidata QID
        const sparql = `
          SELECT ?item ?itemLabel ?itemDescription WHERE {
            ?item wdt:P8 "${entity.wikiQid}" .
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
          }
          LIMIT 1
        `;
        
        const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
        const sparqlResponse = await fetch(sparqlUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/sparql-results+json'
          },
          body: `query=${encodeURIComponent(sparql)}`
        });
        
        const sparqlData = await sparqlResponse.json();
        
        if (sparqlData.results && sparqlData.results.bindings && sparqlData.results.bindings.length > 0) {
          const result = sparqlData.results.bindings[0];
          
          // Extract the QID from the full URI (e.g., http://base.semlab.io/entity/Q123 -> Q123)
          const fullUri = result.item.value;
          const qid = fullUri.split('/').pop();
          
          // Update the entity with SemLab data
          entity.qid = qid;
          
          if (result.itemLabel && result.itemLabel.value) {
            entity.labelSemlab = result.itemLabel.value;
          }
          
          if (result.itemDescription && result.itemDescription.value) {
            entity.descriptionSemlab = result.itemDescription.value;
          }
          
          console.log(`Found SemLab entity ${qid} for Wikidata ${entity.wikiQid}`);
          return entity;
        } else {
          console.log(`No SemLab entity found with P8=${entity.wikiQid}`);
          return null;
        }
      } catch (error) {
        console.error('Error querying SemLab SPARQL:', error);
        return null;
      }
    },

    async setSemlabClasses(){



      let sparql = `
          SELECT ?item ?itemLabel 
          WHERE 
          {
          ?item  wdt:P1 wd:Q19063.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
          }
      `
      
      const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
      const sparqlResponse = await fetch(sparqlUrl, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/sparql-results+json'
        },
        body: `query=${encodeURIComponent(sparql)}`
      });
      const sparqlData = await sparqlResponse.json();
      this.semlabClasses = []
      sparqlData.results.bindings.map(binding => {

        console.log("binding", binding)
        this.semlabClasses.push({
          qid: binding.item.value.replace('http://base.semlab.io/entity/', ''),
          label: binding.itemLabel.value
        })

      });


      this.semlabClasses = this.semlabClasses.sort((a, b) => a.label.localeCompare(b.label));

      return this.semlabClasses
    },


    async workEntity(internal_id,adHoc= false){

      let entity = this.entities[internal_id]

      if(entity.wikiQid){
        for (let queue of [this.workQueue1, this.workQueue2, this.workQueue3]){
          let index = queue.indexOf(internal_id);
          if (index > -1) {
            queue.splice(index, 1); // Remove the entity from the queue
          }
        }        
        return true // already has a qid, no need to work on it
      }

      if (!entity['llmLog']){
        entity.llmLog = []      
      }

      // if (entity.entity.indexOf('Lermolieff') == -1){
      //   for (let queue of [this.workQueue1, this.workQueue2, this.workQueue3]){
      //     let index = queue.indexOf(internal_id);
      //     if (index > -1) {
      //       queue.splice(index, 1); // Remove the entity from the queue
      //     }
      //   }
      //   entity.wikiChecked = true
      //   delete entity.wikiCheckedStatus
        
      //   return false
      // }


      entity.wikiCheckedStatus = 'INITIALIZING';

      delete entity.wikiNoMatch
      delete entity.wikiNoGoodMatch


      let sortOrderPrompt = await this.buildCompareOrderPrompt(entity);
      
      // entity.wikiSortOrderPrompt = sortOrderPrompt.prompt;

      entity.wikiCheckedStatus = 'SEARCHING';
      let newSortOrder
      if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 1){
        // we don't need to sort because ther is only one result
        newSortOrder = sortOrderPrompt.compareList
        newSortOrder[0].order = 1

        newSortOrder = {success: true, error:null, response: newSortOrder}

      }else if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 0){

        entity.wikiNoMatch = true;

      }else{

        try {
          newSortOrder = await asyncEmit('ask_llm_reconcile_build_search_order', sortOrderPrompt.prompt);
        } catch (error) {
          console.error("Error in ask_llm_reconcile_build_search_order:", error);
          newSortOrder = { success: false, error: "Timeout or other error occurred" };
        }

      }

      entity.llmLog.push({
        prompt: sortOrderPrompt,
        response: newSortOrder
      });

      // entity.wikiNewSortOrder = newSortOrder;
      entity.wikiCheckedStatus = 'RECONCILING';
      console.log("newSortOrder", newSortOrder)


      if (newSortOrder && newSortOrder.success && newSortOrder.response && newSortOrder.response.length > 0){

        for (let toReconcile of newSortOrder.response){

          // while it was reconciling they user might selected one of them
          if (entity.wikiQid){
            delete entity.badMatches
            break
          }

          if (toReconcile.label.toLowerCase() == 'nomatch' || toReconcile.qid.toLowerCase() == 'nomatch') {
            entity.wikiNoMatch = true;
            continue
          }

          // if (!entity.wikiComparePrompts){
          //   entity.wikiComparePrompts = []
          // }

          let tmpEntity = JSON.parse(JSON.stringify(entity));
          tmpEntity.qid = toReconcile.qid;
          tmpEntity.searchLabel = toReconcile.label;
          tmpEntity.searchDescription = toReconcile.description;
          let comparePrompt = await this.buildEntityComparePrompt(tmpEntity);
          // console.log("comparePrompt", comparePrompt)
          let compareData = comparePrompt.data;
          comparePrompt = comparePrompt.prompt;

          let compareResult = await asyncEmit('ask_llm_compare_wikidata_entity', comparePrompt);


          entity.llmLog.push({
            prompt: comparePrompt,          
            response: compareResult
          });
          
          

          // entity.wikiComparePrompts.push({
          //   prompt: comparePrompt,
          //   data: compareData,
          //   response: compareResult
          // });

          
          if (compareResult && compareResult.success && compareResult.response && compareResult.response.match){ 
            entity.wikiQid = toReconcile.qid;
            entity.wikiLabel = unescapeHtmlEntities(toReconcile.label);
            entity.wikiDescription = unescapeHtmlEntities(toReconcile.description);
            entity.wikiConfidence = compareResult.response.confidence;  
            entity.wikiReason = compareResult.response.reason;                    
            entity.wikiChecked = true;

            for (let d of compareData){
              if (d.p == 'image') {
                entity.wikiThumbnail = this.convertToThumbnail(d.o);
                entity.wikiThumbnailOrg = d.o;
                break
              }
            }

            this.findSemlabEntityByWikiQid(entity);


            delete entity.wikiCheckedStatus 
            break
          }else{


            if (!entity.badMatches){
              entity.badMatches = []
            }

            let badMatchType
            for (let d of compareData){
              if (d.p == 'instance of') {
                badMatchType = d.o;
                break
              }
            }

            entity.badMatches.push({
              qid: toReconcile.qid,
              label: toReconcile.label,
              description: toReconcile.description,
              reason: compareResult.response.reason,
              confidence: compareResult.response.confidence,
              type: badMatchType
            });
            

            console.log("No match found for entity", entity.entity, "with qid", toReconcile.qid, badMatchType, compareResult)

            //if one was selected remove the badmatches
            if(entity.wikiQid){
              entity.badMatches = []
            }



          }         
        }
      }else{

        if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 0){
          // there is no error since there was an empty response
        }else{
          // error in the sort order request
          entity.wikiCheckedStatus = 'ERROR';
          entity.wikiError = true
        }



      }

      if (!adHoc){
        for (let queue of [this.workQueue1, this.workQueue2, this.workQueue3]){
          let index = queue.indexOf(internal_id);
          if (index > -1) {
            queue.splice(index, 1); // Remove the entity from the queue
          }
        }
      }
      entity.wikiChecked = true
      delete entity.wikiCheckedStatus



      
    },

    
    async workBaseEntity(internal_id,adHoc= false){

      let entity = this.entities[internal_id]
      console.log("Working:", entity.entity,entity)
      if (entity.qid){
        for (let queue of [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3]){
          let index = queue.indexOf(internal_id);
          if (index > -1) {
            queue.splice(index, 1); // Remove the entity from the queue
          }
        }
        return true // already has a qid, no need to work on it
      }

      if (!entity['llmLog']){
        entity.llmLog = []      
      }
      delete entity.wikiBaseNoMatch
      delete entity.wikiBaseNoGoodMatch

      // if (entity.entity.indexOf('Florentine art') == -1){
      //   for (let queue of [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3]){
      //     let index = queue.indexOf(internal_id);
      //     if (index > -1) {
      //       queue.splice(index, 1); // Remove the entity from the queue
      //     }
      //   }
      //   entity.wikiBaseChecked = true
      //   delete entity.wikiBaseCheckedStatus

      //   return false
      // }


      entity.wikiBaseCheckedStatus = 'INITIALIZING';


      let sortOrderPrompt = await this.buildCompareOrderPromptSemlab(entity);
      // entity.wikiBaseSortOrderPrompt = sortOrderPrompt.prompt;
      // console.log("sortOrderPrompt", sortOrderPrompt)

      entity.wikiBaseCheckedStatus = 'SEARCHING';
      let newSortOrder
      if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 1){
        // we don't need to sort because ther is only one result
        newSortOrder = {success: true, error:null, response: sortOrderPrompt.compareList}
        newSortOrder.response[0].order = 1
      }else if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 0){

        entity.wikiBaseCheckedStatus = 'No Search Results';
        return false;

      }else{
        newSortOrder = await asyncEmit('ask_llm_reconcile_build_search_order', sortOrderPrompt.prompt);

      }

      entity.llmLog.push({
        prompt: sortOrderPrompt.prompt,
        response: newSortOrder
      });

      // entity.wikiBaseNewSortOrder = newSortOrder;
      entity.wikiBaseCheckedStatus = 'RECONCILING';
      // console.log("newSortOrder", newSortOrder)


      if (newSortOrder && newSortOrder.success && newSortOrder.response && newSortOrder.response.length > 0){

        for (let toReconcile of newSortOrder.response){

          if (toReconcile.noMatch){
            entity.wikiBaseNoMatch = true;
            continue
          }
          if (toReconcile.label.toLowerCase() == 'nomatch' || toReconcile.qid.toLowerCase() == 'nomatch') {
            entity.wikiBaseNoMatch = true;
            continue
          }

          // if (!entity.wikiBaseComparePrompts){
          //   entity.wikiBaseComparePrompts = []
          // }

          let tmpEntity = JSON.parse(JSON.stringify(entity));
          tmpEntity.qid = toReconcile.qid;
          tmpEntity.searchLabel = toReconcile.label;
          tmpEntity.searchDescription = toReconcile.description;
          let comparePrompt = await this.buildEntityComparePrompt(tmpEntity,true);
          // console.log("comparePrompt", comparePrompt)
          let compareData = comparePrompt.data;
          comparePrompt = comparePrompt.prompt;

          let compareResult = await asyncEmit('ask_llm_compare_wikidata_entity', comparePrompt);


          entity.llmLog.push({
            prompt: comparePrompt,          
            response: compareResult
          });
          
          

          // entity.wikiBaseComparePrompts.push({
          //   prompt: comparePrompt,
          //   data: compareData,
          //   response: compareResult
          // });

          
          if (compareResult && compareResult.success && compareResult.response && compareResult.response.match){ 
            entity.qid = toReconcile.qid;
            entity.labelSemlab = toReconcile.label;
            entity.descriptionSemlab = toReconcile.description;
            entity.wikiBaseConfidence = compareResult.response.confidence;  
            entity.wikiBaseReason = compareResult.response.reason;                    
            entity.wikiBaseChecked = true;
            // console.log("compareData", compareData  )
            for (let d of compareData){
              if (d.p == 'thumbnail URL') {
                entity.thumbnail = d.o;
                break
              }
            }
            for (let d of compareData){
              if (d.p == 'Wikidata QID') {
                entity.wikiQid = d.o;
                this.retriveWikidataEntity(entity)
                break
              }
            }

            // console.log("Matched to entity",entity)
            delete entity.wikiBaseCheckedStatus 
            break
          }         
        }
      }else{

        // error in the sort order request
        entity.wikiBaseCheckedStatus = 'ERROR';
        entity.wikiBaseError = true
      }

      if (!entity.wikiBaseNoMatch){
        entity.wikiBaseNoGoodMatch = true;
      }

      if (!adHoc){
        for (let queue of [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3]){
          let index = queue.indexOf(internal_id);
          if (index > -1) {
            queue.splice(index, 1); // Remove the entity from the queue
          }
        }
      }
      entity.wikiBaseChecked = true
      delete entity.wikiBaseCheckedStatus



      
    },




    workWikidataQueue(){

      for (let queue of [this.workQueue1, this.workQueue2, this.workQueue3]){

        let toWork = queue[0]
        let entity = this.entities[toWork]

        if (entity){
          if (!entity.wikiChecked && !entity.wikiCheckedStatus ){            
            this.workEntity(toWork)          
          }
        }
      }

      if (this.workQueue1.length == 0 && this.workQueue2.length == 0 && this.workQueue3.length == 0){
        clearInterval(this.workQueueTimer)
        this.workQueueTimer = null
        this.workComplete = true
      }

      
    },

    runSemlab(entity) {
      // Run SemLab reconciliation for the entity
      if (entity.internal_id){
        this.workBaseEntity(entity.internal_id,true)
      }else{
        alert("Entity not found")
      }
    },

    runWikidata(entity) {
      // Run Wikidata reconciliation for the entity
      if (entity.internal_id){
        this.workEntity(entity.internal_id,true)
      }else{
        alert("Entity not found")
      }
    },

    
    workWikibaseQueue(){

      for (let queue of [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3]){

        let toWork = queue[0]
        let entity = this.entities[toWork]

        if (entity){
          if (!entity.wikiBaseChecked && !entity.wikiBaseCheckedStatus ){            
            this.workBaseEntity(toWork)          
          }
        }
      }

      if (this.baseWorkQueue1.length == 0 && this.baseWorkQueue2.length == 0 && this.baseWorkQueue3.length == 0){
        clearInterval(this.baseWorkQueueTimer)
        this.baseWorkQueueTimer = null
        this.baseWorkComplete = true
      }

      
    },

    async initalizeWikibaseQueue() {

      if (this.baseWorkQueue1 !== false){
        alert("Queue already initated.")
        return false
      }
      this.baseWorkQueue1 = []
      this.baseWorkQueue2 = []
      this.baseWorkQueue3 = []

      for (let typeKey of Object.keys(this.entitiesByType).sort()){
        for (let entity of this.entitiesByType[typeKey]){        
          const queues = [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3];
          const queueIndex = (this.baseWorkQueue1.length + this.baseWorkQueue2.length + this.baseWorkQueue3.length) % 3;
          queues[queueIndex].push(entity.internal_id);
        }
      }
      this.toggleWikibaseQueue()

    },

    async initalizeWikidataQueue() {

      if (this.workQueue1 !== false){
        alert("Queue already initated.")
        return false
      }
      this.workQueue1 = []
      this.workQueue2 = []
      this.workQueue3 = []

      for (let typeKey of Object.keys(this.entitiesByType).sort()){
        for (let entity of this.entitiesByType[typeKey]){        
          const queues = [this.workQueue1, this.workQueue2, this.workQueue3];
          const queueIndex = (this.workQueue1.length + this.workQueue2.length + this.workQueue3.length) % 3;
          queues[queueIndex].push(entity.internal_id);
        }
      }

      this.toggleQueue()

    },

    async enrichWithSemlabLabels(data) {


      let allQids = Object.keys(data).map(k => data[k].qid).filter(qid => qid != null)
      // console.log("enrichWithSemlabLabels", allQids)

      const qidsForSparql = allQids.map(qid => `wd:${qid}`).join(' ');

      
      let sparql = `
        SELECT *
        WHERE 
        {  
          VALUES ?qids { ${qidsForSparql} }
          ?qids rdfs:label ?label .
          optional{
            ?qids wdt:P3 ?thumbnail .
          }
          optional{
            ?qids wdt:P8 ?wikidata .
          } 


        }  
      `
      
      const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
      const sparqlResponse = await fetch(sparqlUrl, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/sparql-results+json'
        },
        body: `query=${encodeURIComponent(sparql)}`
      });
      const sparqlData = await sparqlResponse.json();
      let allLabels = {}
      let allThumbnails = {}
      let allWikidata = {}
      sparqlData.results.bindings.map(binding => {

        allLabels[binding.qids.value.replace('http://base.semlab.io/entity/', '')] = binding.label.value
 
        if (binding.thumbnail) {
          allThumbnails[binding.qids.value.replace('http://base.semlab.io/entity/', '')] = binding.thumbnail.value
        }
        if (binding.wikidata) {
          allWikidata[binding.qids.value.replace('http://base.semlab.io/entity/', '')] = binding.wikidata.value
        }
      });

      return { allLabels, allThumbnails, allWikidata }





    },

    buildEntitesByType(){

      this.entitiesByType = {}
      for (let eId in this.entities){
        let entity = this.entities[eId]
        if (this.entitiesByType[entity.type] == undefined){
          this.entitiesByType[entity.type] = []

          let foundIt = false;
          for (let typeString of Object.keys(this.typeMap)) {
              if (typeString.toLocaleLowerCase() == entity.type.toLocaleLowerCase()){
                this.typeAlignment[entity.type.toLocaleLowerCase()] = this.typeMap[typeString];
                foundIt = true;
              }
          }
          if (!foundIt) {
            this.typeAlignment[entity.type.toLocaleLowerCase()] = null; // No alignment found
          }
        }

        this.entitiesByType[entity.type].push(entity)
      }
      // console.log("entitiesByType", this.entitiesByType)

      // for (let typeString of Object.keys(this.typeMap)) {
      //     if (!this.typeAlignment[typeString.toLocaleLowerCase()]) {
      //       console.log("No alignment for", typeString);
      //     }
      // }




    },

    details(entity) {
      // Toggle the active entity for details view
      console.log(entity, this.activeEntity)
      if (this.activeEntity && this.activeEntity.internal_id === entity.internal_id) {
        this.activeEntity = null;
      } else {
        this.activeEntity = entity;
      }
      // console.log("activeEntity", this.activeEntity)
    },

    selectBadMatch(entity, badMatch) {
      // Set the entity's wikiQid to the selected bad match
      entity.wikiQid = badMatch.qid;
      entity.wikiLabel = badMatch.label;
      entity.wikiDescription = badMatch.description;
      // Clear the bad matches list since one was selected
      delete entity.badMatches;
      // Optionally retrieve additional data from Wikidata
      this.retriveWikidataEntity(entity);
    },

    clearBadMatches(entity) {
      // Clear all bad matches from the entity
      delete entity.badMatches;
      // delete entity.wikiQid;
      // delete entity.wikiLabel;
      // delete entity.wikiDescription;
      delete entity.wikiNoMatch;
    },

    truncateDescription(description, entityId, matchIndex) {
      // Truncate description to 5 words if not expanded
      const key = `${entityId}_${matchIndex}`;
      if (!description) return '';
      
      const words = description.split(' ');
      if (words.length <= 5) return description;
      
      if (this.expandedDescriptions[key]) {
        return description;
      }
      return words.slice(0, 5).join(' ') + '...';
    },

    toggleDescription(entityId, matchIndex) {
      // Toggle the expanded state of a description
      const key = `${entityId}_${matchIndex}`;
      this.expandedDescriptions[key] = !this.expandedDescriptions[key];
    },

    async searchWikidata(entityId, query) {
      // Search Wikidata API with debounce
      if (!query || query.length < 2) {
        this.wikidataSearchResults[entityId] = [];
        this.wikidataSelectedIndex[entityId] = -1;
        return;
      }

      // Clear existing timer
      if (this.wikidataSearchTimers[entityId]) {
        clearTimeout(this.wikidataSearchTimers[entityId]);
      }

      // Set loading state
      this.wikidataSearchLoading[entityId] = true;

      // Debounce the search
      this.wikidataSearchTimers[entityId] = setTimeout(async () => {
        try {
          const searchUrl = `https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&limit=10&language=en&uselang=en&type=item&origin=*&search=${encodeURIComponent(query)}`;
          const response = await fetch(searchUrl);
          const data = await response.json();
          
          if (data.search) {
            const searchResults = data.search.map(item => ({
              id: item.id,
              label: item.label || item.id,
              description: item.description || '',
              image: null, // Will be populated by fetchWikidataImages
              imageLoading: false
            }));
            this.wikidataSearchResults[entityId] = searchResults;
            // Reset selected index when new results come in
            this.wikidataSelectedIndex[entityId] = -1;
            // Fetch images for the results
            this.fetchWikidataImages(entityId, searchResults);
          } else {
            this.wikidataSearchResults[entityId] = [];
            this.wikidataSelectedIndex[entityId] = -1;
          }
        } catch (error) {
          console.error('Error searching Wikidata:', error);
          this.wikidataSearchResults[entityId] = [];
          this.wikidataSelectedIndex[entityId] = -1;
        } finally {
          this.wikidataSearchLoading[entityId] = false;
        }
      }, 300); // 300ms debounce
    },

    selectWikidataItem(entity, item) {
      // Select a Wikidata item from search results
      entity.wikiQid = item.id;
      entity.wikiLabel = item.label;
      entity.wikiDescription = item.description;
      entity.wikiNoMatch = false;
      
      // Clear search state
      this.wikidataSearchQueries[entity.internal_id] = '';
      this.wikidataSearchResults[entity.internal_id] = [];


      // Retrieve additional data
      this.retriveWikidataEntity(entity);
    },

    clearWikidataSearch(entityId) {
      // Clear search results when clicking outside
      setTimeout(() => {
        this.wikidataSearchResults[entityId] = [];
        this.wikidataSelectedIndex[entityId] = -1;
      }, 200);
    },

    handleWikidataKeydown(event, entity) {
      const entityId = entity.internal_id;
      const results = this.wikidataSearchResults[entityId];
      
      if (!results || results.length === 0) {
        // If no results but typing, don't interfere with normal typing
        return;
      }
      
      // Initialize index if it doesn't exist
      if (this.wikidataSelectedIndex[entityId] === undefined) {
        this.wikidataSelectedIndex[entityId] = -1;
      }
      
      const currentIndex = this.wikidataSelectedIndex[entityId];
      
      switch(event.key) {
        case 'ArrowDown':
          event.preventDefault();
          event.stopPropagation();
          // Move down in the list, wrap to -1 at the end
          if (currentIndex >= results.length - 1) {
            this.wikidataSelectedIndex[entityId] = 0;
          } else {
            this.wikidataSelectedIndex[entityId] = currentIndex + 1;
          }
          console.log('Arrow Down - New index:', this.wikidataSelectedIndex[entityId]);
          this.scrollToSelectedItem(entityId);
          break;
          
        case 'ArrowUp':
          event.preventDefault();
          event.stopPropagation();
          // Move up in the list, wrap to bottom at the top
          if (currentIndex <= 0) {
            this.wikidataSelectedIndex[entityId] = results.length - 1;
          } else {
            this.wikidataSelectedIndex[entityId] = currentIndex - 1;
          }
          console.log('Arrow Up - New index:', this.wikidataSelectedIndex[entityId]);
          this.scrollToSelectedItem(entityId);
          break;
          
        case 'Enter':
          if (currentIndex >= 0 && currentIndex < results.length) {
            event.preventDefault();
            event.stopPropagation();
            this.selectWikidataItem(entity, results[currentIndex]);
            console.log('Enter - Selecting item at index:', currentIndex);
          }
          break;
          
        case 'Escape':
          event.preventDefault();
          event.stopPropagation();
          this.wikidataSearchResults[entityId] = [];
          this.wikidataSelectedIndex[entityId] = -1;
          console.log('Escape - Closing dropdown');
          break;
      }
    },

    scrollToSelectedItem(entityId) {
      // Scroll the dropdown to keep the selected item visible
      this.$nextTick(() => {
        const selectedIndex = this.wikidataSelectedIndex[entityId];
        if (selectedIndex < 0) return;
        
        // Find the dropdown container and the selected item
        const dropdownContainer = document.querySelector(`.wikidata-autocomplete-${entityId} .dropdown-content`);
        const selectedItem = document.querySelector(`.wikidata-autocomplete-${entityId} .dropdown-item:nth-child(${selectedIndex + 1})`);
        
        if (dropdownContainer && selectedItem) {
          const containerHeight = dropdownContainer.clientHeight;
          const itemHeight = selectedItem.offsetHeight;
          const itemTop = selectedItem.offsetTop;
          const scrollTop = dropdownContainer.scrollTop;
          
          // Check if item is above visible area
          if (itemTop < scrollTop) {
            dropdownContainer.scrollTop = itemTop;
          }
          // Check if item is below visible area
          else if (itemTop + itemHeight > scrollTop + containerHeight) {
            dropdownContainer.scrollTop = itemTop + itemHeight - containerHeight;
          }
        }
      });
    },

    async fetchWikidataImages(entityId, searchResults) {
      // Fetch images for search results using SPARQL
      if (!searchResults || searchResults.length === 0) return;
      
      const qids = searchResults.map(item => `wd:${item.id}`).join(' ');
      const sparql = `
        SELECT ?entity ?image WHERE {
          VALUES ?entity { ${qids} }
          OPTIONAL { ?entity wdt:P18 ?image. }
        }
      `;
      
      try {
        const sparqlUrl = 'https://query.wikidata.org/sparql';
        const response = await fetch(sparqlUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/sparql-results+json',
            'User-Agent': 'WikidataAutocomplete/1.0'
          },
          body: `query=${encodeURIComponent(sparql)}`
        });
        
        const data = await response.json();
        
        if (data.results && data.results.bindings) {
          // Create a map of QID to image URL
          const imageMap = {};
          data.results.bindings.forEach(binding => {
            if (binding.entity && binding.image) {
              const qid = binding.entity.value.replace('http://www.wikidata.org/entity/', '');
              imageMap[qid] = binding.image.value;
            }
          });
          
          // Update the search results with thumbnail images
          const currentResults = this.wikidataSearchResults[entityId];
          if (currentResults) {
            currentResults.forEach(item => {
              if (imageMap[item.id]) {
                // Convert to thumbnail URL (80px width)
                console.log("imageMap[item.id]", imageMap[item.id])
                console.log(item)
                item.image = this.convertToThumbnail(imageMap[item.id], 80);
              }
            });
          }
        }
      } catch (error) {
        console.error('Error fetching Wikidata images:', error);
      }
    },

    convertToThumbnail(imageUrl, width = 80) {
      // Convert full Wikimedia Commons URLs to thumbnail URLs using MD5 hashing
      if (!imageUrl || !imageUrl.includes('commons.wikimedia.org')) {
        return imageUrl;
      }

      try {
        // Extract filename from the URL
        let filename;
        if (imageUrl.includes('/wiki/File:')) {
          filename = imageUrl.split('/wiki/File:')[1];
        } else if (imageUrl.includes('/wikipedia/commons/')) {
          filename = imageUrl.split('/').pop();
        } else {
          filename = imageUrl.split('/').pop();
        }


        // Decode URL encoding if present
        filename = decodeURIComponent(filename);
        filename = filename.replace(/ /g, '_'); // Replace spaces with underscores for MD5

        console.log('Extracted filename:', filename);
        console.log(filename.replace(/ /g, '_'))
        // Generate MD5 hash of filename using proper MD5 implementation
        const md5Hash = MD5(filename).toString();

        
        // Build thumbnail URL according to Wikimedia rules:
        // https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/200px-Tour_Eiffel_Wikimedia_Commons.jpg
        const firstChar = md5Hash.charAt(0);
        const firstTwoChars = md5Hash.substring(0, 2);
        
        let thumbnailUrl = `https://upload.wikimedia.org/wikipedia/commons/thumb/${firstChar}/${firstTwoChars}/${encodeURIComponent(filename)}/${width}px-${encodeURIComponent(filename)}`;

        if (thumbnailUrl.endsWith(".tif")){
          thumbnailUrl = thumbnailUrl +  ".jpg"
        }
        if (thumbnailUrl.endsWith(".svg")){
          thumbnailUrl = thumbnailUrl +  ".png"
        }
        
        
        console.log('Converting image URL:', filename, 'hash:', md5Hash, '->', thumbnailUrl);
        return thumbnailUrl;
      } catch (error) {
        console.error('Error converting to thumbnail:', error);
        return imageUrl;
      }
    },

    handleWikidataFocus(entity) {
      // Pre-populate the search field with entity label and kick off search
      const entityId = entity.internal_id;
      const searchTerm = entity.useLabel || entity.entity;
      
      // Set the search query and trigger search
      this.wikidataSearchQueries[entityId] = searchTerm;
      this.searchWikidata(entityId, searchTerm);
    },

    async searchSemlab(entityId, query) {
      // Search SemLab API with debounce
      if (!query || query.length < 2) {
        this.semlabSearchResults[entityId] = [];
        this.semlabSelectedIndex[entityId] = -1;
        return;
      }

      // Clear existing timer
      if (this.semlabSearchTimers[entityId]) {
        clearTimeout(this.semlabSearchTimers[entityId]);
      }

      // Set loading state
      this.semlabSearchLoading[entityId] = true;

      // Debounce the search
      this.semlabSearchTimers[entityId] = setTimeout(() => {
        socket.emit('search_semlab_autocomplete',  query, (response) => {
          console.log('SemLab search response:', response);
          try {
            if (response.success && response.data && response.data.search) {
              const searchResults = response.data.search.map(item => ({
                id: item.id,
                label: item.label || item.id,
                description: item.description || ''
              }));
              this.semlabSearchResults[entityId] = searchResults;
              // Reset selected index when new results come in
              this.semlabSelectedIndex[entityId] = -1;
            } else {
              this.semlabSearchResults[entityId] = [];
              this.semlabSelectedIndex[entityId] = -1;
            }
          } catch (error) {
            console.error('Error processing SemLab search response:', error);
            this.semlabSearchResults[entityId] = [];
            this.semlabSelectedIndex[entityId] = -1;
          } finally {
            this.semlabSearchLoading[entityId] = false;
          }
        });
      }, 300); // 300ms debounce
    },

    async selectSemlabItem(entity, item) {
      // Select a SemLab item from search results
      entity.qid = item.id;
      entity.labelSemlab = item.label;
      entity.descriptionSemlab = item.description;
      
      // Clear search state
      this.semlabSearchQueries[entity.internal_id] = '';
      this.semlabSearchResults[entity.internal_id] = [];


      let enriched = await this.enrichWithSemlabLabels([entity]);

      if (enriched && enriched.allThumbnails && enriched.allThumbnails[entity.qid]) {
        entity.thumbnail = enriched.allThumbnails[entity.qid];
      }

      if (enriched && enriched.allWikidata && enriched.allWikidata[entity.qid]) {
        entity.wikiQid = enriched.allWikidata[entity.qid];
        entity.wikiLabel = enriched.allLabels[entity.qid] || '';
      }


      console.log('Enriched entity with SemLab labels:', enriched);
      console.log('Selected SemLab item:', entity);

    },

    clearSemlabSearch(entityId) {
      // Clear search results when clicking outside
      setTimeout(() => {
        this.semlabSearchResults[entityId] = [];
        this.semlabSelectedIndex[entityId] = -1;
      }, 200);
    },

    handleSemlabKeydown(event, entity) {
      const entityId = entity.internal_id;
      const results = this.semlabSearchResults[entityId];
      
      if (!results || results.length === 0) {
        return;
      }
      
      // Initialize index if it doesn't exist
      if (this.semlabSelectedIndex[entityId] === undefined) {
        this.semlabSelectedIndex[entityId] = -1;
      }
      
      const currentIndex = this.semlabSelectedIndex[entityId];
      
      switch(event.key) {
        case 'ArrowDown':
          event.preventDefault();
          event.stopPropagation();
          if (currentIndex >= results.length - 1) {
            this.semlabSelectedIndex[entityId] = 0;
          } else {
            this.semlabSelectedIndex[entityId] = currentIndex + 1;
          }
          this.scrollToSelectedSemlabItem(entityId);
          break;
          
        case 'ArrowUp':
          event.preventDefault();
          event.stopPropagation();
          if (currentIndex <= 0) {
            this.semlabSelectedIndex[entityId] = results.length - 1;
          } else {
            this.semlabSelectedIndex[entityId] = currentIndex - 1;
          }
          this.scrollToSelectedSemlabItem(entityId);
          break;
          
        case 'Enter':
          if (currentIndex >= 0 && currentIndex < results.length) {
            event.preventDefault();
            event.stopPropagation();
            this.selectSemlabItem(entity, results[currentIndex]);
          }
          break;
          
        case 'Escape':
          event.preventDefault();
          event.stopPropagation();
          this.semlabSearchResults[entityId] = [];
          this.semlabSelectedIndex[entityId] = -1;
          break;
      }
    },

    scrollToSelectedSemlabItem(entityId) {
      // Scroll the SemLab dropdown to keep the selected item visible
      this.$nextTick(() => {
        const selectedIndex = this.semlabSelectedIndex[entityId];
        if (selectedIndex < 0) return;
        
        const dropdownContainer = document.querySelector(`.semlab-autocomplete-${entityId} .dropdown-content`);
        const selectedItem = document.querySelector(`.semlab-autocomplete-${entityId} .dropdown-item:nth-child(${selectedIndex + 1})`);
        
        if (dropdownContainer && selectedItem) {
          const containerHeight = dropdownContainer.clientHeight;
          const itemHeight = selectedItem.offsetHeight;
          const itemTop = selectedItem.offsetTop;
          const scrollTop = dropdownContainer.scrollTop;
          
          if (itemTop < scrollTop) {
            dropdownContainer.scrollTop = itemTop;
          } else if (itemTop + itemHeight > scrollTop + containerHeight) {
            dropdownContainer.scrollTop = itemTop + itemHeight - containerHeight;
          }
        }
      });
    },

    handleSemlabFocus(entity) {
      // Pre-populate the SemLab search field with entity label and kick off search
      const entityId = entity.internal_id;
      const searchTerm = entity.useLabel || entity.entity;
      
      this.semlabSearchQueries[entityId] = searchTerm;
      this.searchSemlab(entityId, searchTerm);
    },

    removeWikidataQid(entity) {
      // Remove Wikidata QID and related data from entity
      delete entity.wikiQid;
      delete entity.wikiLabel;
      delete entity.wikiDescription;
      delete entity.wikiConfidence;
      delete entity.wikiReason;
      delete entity.wikiThumbnail;
      delete entity.wikiChecked;
      delete entity.wikiNoMatch;
      delete entity.wikiThumbnailOrg;

    },

    removeSemlabQid(entity) {
      // Remove SemLab QID and related data from entity
      delete entity.qid;
      delete entity.labelSemlab;
      delete entity.descriptionSemlab;
      delete entity.wikiBaseConfidence;
      delete entity.wikiBaseReason;
      delete entity.thumbnail;
      delete entity.wikiBaseChecked;
      delete entity.wikiBaseNoMatch;
      delete entity.wikiBaseNoGoodMatch;
    },

    // markComplete() {
    //   // Mark the job as complete
    //   socket.emit('update_document_status', {doc:this.documentId, user:this.user, workflow:'DIFF_REVIEW',value:'COMPLETE'}, (response) => {
    //     if (response.success) {
          // console.log("Job marked as complete");
    //       this.$refs.jobstatus.initialize()
    //     } else {
    //       console.error("Error marking job as complete:", response.error);
    //     }
    //   });
    // },



      
    onJobStatus(job) {
      // Handle job status updates
      // this.judgeStatus = job.status
      if (job.workflow && job.workflow.DIFF_REVIEW && job.workflow.DIFF_REVIEW.status == 'COMPLETE') {
        this.workflowComplete = true
      } else {
        this.workflowComplete = false
      }
    },

    async buildCompareOrderPrompt(entity) {
            
      try {
              let searchLabel = entity.entity
              if (entity.useLabel){
                searchLabel = entity.useLabel
              }
              let searchUrl = `https://www.wikidata.org/w/api.php?action=query&format=json&list=search&srsearch=${encodeURIComponent(searchLabel)}&utf8=&srprop=snippet|titlesnippet|redirecttitle|sectiontitle&origin=*&srlimit=10`;
              const response = await fetch(searchUrl);
              const data = await response.json();

              let compareList = []
              if (data.query && data.query.search && data.query.search.length > 0) {
                const searchResults = data.query.search;

                for (let sr of searchResults) {
                        
                  let label = sr.titlesnippet.replace(/<\/?[^>]+(>|$)/g, "");;
                  let description = sr.snippet.replace(/<\/?[^>]+(>|$)/g, ""); 
                  let qid = sr.title;

                  compareList.push({
                    label: label,
                    description: description,
                    qid: qid,
                    order: null
                  })
                }                
              }


              
              let contextText = this.blocks[entity.blocks[0]].clean;
              if (entity.blocks.length > 1) {
              const firstBlockWordCount = this.blocks[entity.blocks[0]].clean.split(/\s+/).length; // Split by any whitespace
              if (firstBlockWordCount < 100 && this.blocks[entity.blocks[1]]) { // Check if second block exists
                contextText += " " + this.blocks[entity.blocks[1]].clean;
              }
              }

              let useLabel = entity.useLabel ? entity.useLabel : entity.entity;

              let prompt = `The ${entity.type}: "${useLabel}" described in this text:\n`
              prompt += `"${contextText}"\n\n`

              prompt += `Below are the JSON search results for looking for this ${entity.type} in the database. Each object in the JSON array has a null 'order' value, change it to match the order the results should be investiaged further from mosty likely of being a match (1) to least likely of being a match (10, or length of array) modify the JSON and return it as VALID JSON. If there appear to be no good matches return [{"noMatch":true}] \n\n`

              prompt += JSON.stringify(compareList, null, 2);
              console.log("---------------------")
              console.log(prompt)
              console.log("---------------------")

              return {prompt: prompt, compareList: compareList}
        } catch (error) {
          console.error("Error fetching from Wikidata:", error);
          return null;
        }
  
    },

    async buildCompareOrderPromptSemlab(entity) {
            
      try {
              
              let searchResults = await asyncEmit('search_base', entity.entity);
              // console.log("searchResults", searchResults  )
              if (searchResults.success == false) {
                console.error("Error fetching from SemLab:", searchResults.error);
                return null;
              }
              
              let compareList = searchResults.response;
              // console.log("compareList", compareList)

              if (compareList.length == 0) {
                // No results found
                return {prompt: `No results found for ${entity.entity}`, compareList: [{"noMatch": true}]};
              }

              // let searchUrl = `https://base.semlab.io/w/api.php?action=wbsearchentities&search=${encodeURIComponent(entity.entity)}&format=json&errorformat=plaintext&language=en&uselang=en&origin=*&type=item`;
              // const response = await fetch(searchUrl);
              // const data = await response.json();

              // let compareList = []
              // if (data && data.search && data.search.length > 0) {
              //   const searchResults = data.search;

              //   for (let sr of searchResults) {

              //     let label = sr.label.replace(/<\/?[^>]+(>|$)/g, "");
              //     let description = sr.description.replace(/<\/?[^>]+(>|$)/g, ""); 
              //     let qid = sr.id;

              //     compareList.push({
              //       label: label,
              //       description: description,
              //       qid: qid,
              //       order: null
              //     })
              //   }                
              // }

              let contextText = this.blocks[entity.blocks[0]].clean;
              if (entity.blocks.length > 1) {
              const firstBlockWordCount = this.blocks[entity.blocks[0]].clean.split(/\s+/).length; // Split by any whitespace
              if (firstBlockWordCount < 100 && this.blocks[entity.blocks[1]]) { // Check if second block exists
                contextText += " " + this.blocks[entity.blocks[1]].clean;
              }
              }

              let useLabel = entity.useLabel ? entity.useLabel : entity.entity;

              let prompt = `The ${entity.type}: "${useLabel}" described in this text:\n`
              prompt += `"${contextText}"\n\n`

              prompt += `Below are the JSON search results for looking for this ${entity.type} in the database. Each object in the JSON array has a null 'order' value, change it to match the order the results should be investiaged further from mosty likely of being a match (1) to least likely of being a match (10, or length of array) modify the JSON and return it as VALID JSON. If there appear to be no good matches return [{"noMatch":true}] \n\n`

              prompt += JSON.stringify(compareList, null, 2);
              // console.log("prompt", prompt  )
              return {prompt: prompt, compareList: compareList}
        } catch (error) {
          console.error("Error fetching from Wikidata:", error);
          return null;
        }
  
    },


    async buildPromptByClass(){


      if (!this.bulkInstanceOfBase || !this.bulkInstanceOfDoc) {
        alert("Please select a class to align with");
        return;
      }
      this.statusClassReconcile = true;

      let sparql = `      

       SELECT ?entity ?entityLabel ?entityDesc (GROUP_CONCAT(?alias; SEPARATOR=", ") AS ?aliasObjects)
        WHERE 
        {
          ?entity wdt:P1 wd:${this.bulkInstanceOfBase}.
          optional{
            ?entity schema:description ?entityDesc .
          }
          optional{
            ?entity skos:altLabel ?alias .
            FILTER (LANG(?alias) = "en")            
          }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }                    
        }
        GROUP BY ?entity ?entityLabel ?entityDesc

        LIMIT 10000

      
      `
      
      const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
      const sparqlResponse = await fetch(sparqlUrl, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/sparql-results+json'
        },
        body: `query=${encodeURIComponent(sparql)}`
      });
      const sparqlData = await sparqlResponse.json();

      let allLabels = sparqlData.results.bindings.map(binding => {
        return {
          id: binding.entity.value.replace('http://base.semlab.io/entity/', ''),
          label: binding.entityLabel.value,
          description: (binding.entityDesc) ? binding.entityDesc.value : null,
          alias: (binding.aliasObjects) ? binding.aliasObjects.value : null
        }
      });


      let prompt = `The following is a list of entities that need to be matched to the data in the JSON structure. Modify the JSON stucture to change the qid value to the for the most likely match. Only make high confidece matches.\n\n`

      for (let i = 0; i < allLabels.length; i++) {
        let entity = allLabels[i];
        prompt += `- ${entity.label} ${entity.alias ? `(Also known as: ${entity.alias})` : ''} ${entity.description ? `(${entity.description})` : ''} - ID: ${entity.id}\n`;
      }
      let promptEntities = []
      for (let type of Object.keys(this.entitiesByType).sort()){
        if (type == this.bulkInstanceOfDoc){
          // only include entities of the selected class
          for (let entity of this.entitiesByType[type]){
            if (entity.blocks.length > 0){
              promptEntities.push({
                entity: (entity.useLabel ? entity.useLabel : entity.entity),
                type: entity.type,
                internal_id: entity.internal_id,
                qid: null
              });
              
            }
          }
        }
      }
      // console.log("promptEntities", promptEntities)
      prompt += `\n\nBelow is the JSON structure to modify with the qid values for the most likely match:\n\n`
      prompt += JSON.stringify(promptEntities, null, 2);

      console.log("prompt", prompt)

      socket.emit('ask_llm', {prompt:prompt, task:'RECONCILE_PROJECT_WIDE'}, async (response) => {

        // console.log("LLM Response", response)
        if (response && response.success) {
          // Process the response and update the entities with the qid values
          let errors = []
          for (let i = 0; i < response.response.length; i++) {
            let entity = response.response[i];
            // console.log("entity", entity)
            if (entity.qid) {
              if (this.entities[entity.internal_id] && (!this.entities[entity.internal_id].qid || this.entities[entity.internal_id].qid == null || this.entities[entity.internal_id].qid == '')) {
                this.entities[entity.internal_id].qid = entity.qid;
                // console.log("this.entities[entity.internal_id]",this.entities[entity.internal_id])
              }else{
                errors.push(`Entity with internal_id ${entity.internal_id} not found in entities. For ${entity}`);
              }              
            }else{
              this.entities[entity.internal_id].qid = null;
            }
          }
          // console.log("this.entities", this.entities)
          let enrichResults = await this.enrichWithSemlabLabels(this.entities);

          for (let eId in this.entities){
            if (enrichResults.allLabels[this.entities[eId].qid]){
              this.entities[eId].labelSemlab = enrichResults.allLabels[this.entities[eId].qid];
            }
            if (enrichResults.allThumbnails[this.entities[eId].qid]){
              this.entities[eId].thumbnail = enrichResults.allThumbnails[this.entities[eId].qid].replace("<",'').replace("<",'');
            }
            if (enrichResults.allWikidata[this.entities[eId].qid]){
              this.entities[eId].wikiQid = enrichResults.allWikidata[this.entities[eId].qid];
              this.retriveWikidataEntity(this.entities[eId]);
            }

          }
          
         this.buildEntitesByType();
        //  console.log("this.entitiesByType", this.entitiesByType)
          // console.log("this.entities", this.entities)


        } else {
          if (response && response.error){
            console.error("Error processing LLM response:", response.error);
            alert("There was an error processing the LLM response, please try again: " + response.error);
          }else{
            alert("There was an error processing the LLM response, please try again.");
          }
          
          
        }

        this.statusClassReconcile = null;

      })





    },

    async buildPromptAllSemlab(){

      if (!this.useProjectBulkAlign) {
        alert("Please select a project to align with");
        return;
      }
      this.statusProjectReconcile = true;
      // Fetch the list of SemLab projects
      let sparql = `
        SELECT ?entity ?entityLabel ?instanceOf ?instanceOfLabel ?entityDesc (GROUP_CONCAT(?alias; SEPARATOR=", ") AS ?aliasObjects)
        WHERE 
        {          
          ?entity wdt:P11 wd:${this.useProjectBulkAlign}.
          ?entity wdt:P1 ?instanceOf.          
          optional{
            ?entity schema:description ?entityDesc .
          }
          optional{
            ?entity skos:altLabel ?alias .
            FILTER (LANG(?alias) = "en")            
          }         
          
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
          
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q20664 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q2013 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19069 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q23572 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q27513 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19069 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19063 }   
          
        }
        GROUP BY ?entity ?entityLabel ?instanceOf ?instanceOfLabel ?entityDesc
        limit 10000   

      `
      
      const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
      const sparqlResponse = await fetch(sparqlUrl, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/sparql-results+json'
        },
        body: `query=${encodeURIComponent(sparql)}`
      });
      const sparqlData = await sparqlResponse.json();

      let allLabels = sparqlData.results.bindings.map(binding => {
        return {
          id: binding.entity.value.replace('http://base.semlab.io/entity/', ''),
          label: binding.entityLabel.value,
          instanceOfId: binding.instanceOf.value.replace('http://base.semlab.io/entity/', ''),
          instanceOfLabel: binding.instanceOfLabel.value,
          description: (binding.entityDesc) ? binding.entityDesc.value : null,
          alias: (binding.aliasObjects) ? binding.aliasObjects.value : null

        }
      });

      
      let prompt = `The following is a list of entities that need to be matched to the data in the JSON structure. Modify the JSON stucture to change the qid value to the for the most likely match. Only make high confidece matches.\n\n`

      for (let i = 0; i < allLabels.length; i++) {
        let entity = allLabels[i];
        prompt += `- ${entity.label} (${entity.instanceOfLabel}) ${entity.alias ? `(Also known as: ${entity.alias})` : ''} ${entity.description ? `(${entity.description})` : ''} - ID: ${entity.id}\n`;
      }
      let promptEntities = []
      for (let type of Object.keys(this.entitiesByType).sort()){
        for (let entity of this.entitiesByType[type]){
          if (entity.blocks.length > 0){
            promptEntities.push({
              entity: (entity.useLabel ? entity.useLabel : entity.entity),
              type: entity.type,
              internal_id: entity.internal_id,
              qid: null
            });
            
          }
        }
      }
      // console.log("promptEntities", promptEntities)
      prompt += `\n\nBelow is the JSON structure to modify with the qid values for the most likely match:\n\n`
      prompt += JSON.stringify(promptEntities, null, 2);

      // console.log("prompt", prompt)


      socket.emit('ask_llm', {prompt:prompt, task:'RECONCILE_PROJECT_WIDE'}, async (response) => {

        // console.log("LLM Response", response)
        if (response && response.success) {
          // Process the response and update the entities with the qid values
          let errors = []
          for (let i = 0; i < response.response.length; i++) {
            let entity = response.response[i];
            // console.log("entity", entity)
            if (entity.qid) {
              if (this.entities[entity.internal_id] && (!this.entities[entity.internal_id].qid || this.entities[entity.internal_id].qid == null || this.entities[entity.internal_id].qid == '')) {
                this.entities[entity.internal_id].qid = entity.qid;
                // console.log("this.entities[entity.internal_id]",this.entities[entity.internal_id])
              }else{
                errors.push(`Entity with internal_id ${entity.internal_id} not found in entities. For ${entity}`);
              }              
            }else{
              this.entities[entity.internal_id].qid = null;
            }
          }
          // console.log("this.entities", this.entities)
          let enrichResults = await this.enrichWithSemlabLabels(this.entities);

          for (let eId in this.entities){
            if (enrichResults.allLabels[this.entities[eId].qid]){
              this.entities[eId].labelSemlab = enrichResults.allLabels[this.entities[eId].qid];
            }
            if (enrichResults.allThumbnails[this.entities[eId].qid]){
              this.entities[eId].thumbnail = enrichResults.allThumbnails[this.entities[eId].qid].replace("<",'').replace("<",'');
            }
            if (enrichResults.allWikidata[this.entities[eId].qid]){
              this.entities[eId].wikiQid = enrichResults.allWikidata[this.entities[eId].qid];
              this.retriveWikidataEntity(this.entities[eId]);
            }

          }
          
         this.buildEntitesByType();
        //  console.log("this.entitiesByType", this.entitiesByType)
          // console.log("this.entities", this.entities)


        } else {
          if (response && response.error){
            console.error("Error processing LLM response:", response.error);
            alert("There was an error processing the LLM response, please try again: " + response.error);
          }else{
            alert("There was an error processing the LLM response, please try again.");
          }
          
          
        }

        this.statusProjectReconcile = null;

      })

    },

    async normalizeLabels(){

      const BATCH_SIZE = 10;
      
      let allEntities = [];
      for (let eId in this.entities){
        let entity = this.entities[eId];
        allEntities.push({
          internal_id: entity.internal_id,
          labels: entity.labels,
          normalizedLabels: [],
          entityId: eId
        });

      }

      
      const totalBatches = Math.ceil(allEntities.length / BATCH_SIZE);
      
      for (let batchNum = 0; batchNum < totalBatches; batchNum++) {
        const startIdx = batchNum * BATCH_SIZE;
        const endIdx = Math.min(startIdx + BATCH_SIZE, allEntities.length);
        const batchEntities = allEntities.slice(startIdx, endIdx);
        
        this.statusLabelNormalize = `Working on batch ${batchNum + 1} of ${totalBatches}`;
        let sendBlocks = [];     

        for (let batchEntity of batchEntities){
          let entity = this.entities[batchEntity.entityId];
          if (entity.blocks && entity.blocks.length > 0) {
            if (sendBlocks.indexOf(entity.blocks[0]) == -1){
              sendBlocks.push(entity.blocks[0]);
              if (entity.blocks[1]){
                sendBlocks.push(entity.blocks[1]);
              }

            }
          }else{
            console.warn(`Entity ${entity.internal_id} has no blocks, skipping normalization.`);
          }
        }
        let allBlockText = sendBlocks.map(b => this.blocks[b].clean).join(" ");


        const sendList = batchEntities.map(e => ({
          internal_id: e.internal_id,
          labels: e.labels,
          normalizedLabels: []
        }));

        let prompt = `Normalize the words in this list of objects, normalize the labels in the key "labels", if they have honorifics remove them, if they are a shortened version of the entity make it the fuller form, make the term more search friendly if you were searching Wikipedia for the term. Do not invent names or expand the word without strong evidence, if you cannot expand it return it as it is. After the JSON below is the text the names are found in, use this text to help expand the name. Return JSON Only.`
        prompt += `\n\nJSON:\n`
        prompt += JSON.stringify(sendList, null, 2);
        prompt += `\n\nText:\n"${allBlockText}"\n\n`
        console.log(`Processing batch ${batchNum + 1}/${totalBatches}:`, prompt)
        
        let response = null;
        try{
          response = await asyncEmit('ask_llm_normalize_labels', prompt);
        }catch (error) {
          console.error(`Error normalizing labels for batch ${batchNum + 1}:`, error);
          alert(`There was an error normalizing the labels for batch ${batchNum + 1}, please try again.`);
          this.statusLabelNormalize = null;
          return;
        }
        
        if (!response || !response.success || !response.response) {
          console.error(`Error normalizing labels for batch ${batchNum + 1}:`, response?.error);
          alert(`There was an error normalizing the labels for batch ${batchNum + 1}, please try again.`);
          this.statusLabelNormalize = null;
          return;
        }

        for (let batchEntity of batchEntities){
          let entity = this.entities[batchEntity.entityId];
          let lookForId = batchEntity.internal_id;
          let found = response.response.find(item => item.internal_id === lookForId);
          if (found) {
            if (found.normalizedLabels && found.normalizedLabels.length > 0) {
              if (found.normalizedLabels[0] && found.labels.indexOf(found.normalizedLabels[0]) == -1){
                console.log("Adding normalized label", found.normalizedLabels[0], "to entity", entity.internal_id, "replacing", found.labels[0]);
                entity.normalizedLabel = found.normalizedLabels[0]
                entity.useLabel = entity.normalizedLabel
              }
            }
          }
        }
        
        console.log(`Batch ${batchNum + 1} LLM Response`, response)
      }

      this.statusLabelNormalize = null;
      console.log("All batches completed")
      return true;

    },

    async sendFilteredEntities() {
      this.isSavingEntities = true;
      
      const allowedKeys = [
        'entity',
        'hidden',
        'type',
        'wikiReason',
        'internal_id',
        'labels',
        'blocks',
        'count',
        'qid',
        'labelSemlab',
        'descriptionSemlab',
        'wikiBaseReason',
        'thumbnail',
        'wikiQid',
        'wikiLabel',
        'wikiDescription',
        'wikiThumbnailOrg',
        'wikiThumbnail'
      ];

      const filteredEntities = {};
      
      for (let eId in this.entities) {
        const entity = this.entities[eId];
        const filteredEntity = {};
        
        for (let key of allowedKeys) {
          if (key in entity) {
            filteredEntity[key] = entity[key];
          }
        }
        
        filteredEntities[eId] = filteredEntity;
      }

      console.log('Sending filtered entities to backend:', filteredEntities);
      
      try {
        const response = await asyncEmit('save_ner_entities', { user: this.user, job_id: this.documentId, entities: filteredEntities });
        if (response && response.success) {
          console.log('Entities saved successfully');
          this.isSavingEntities = false;
          this.entitiesHaveChanges = false;
          return response;
        } else {
          console.error('Failed to save entities:', response?.error);
          alert('Failed to save entities to backend');
          this.isSavingEntities = false;
          return null;
        }
      } catch (error) {
        console.error('Error sending entities to backend:', error);
        alert('Error sending entities to backend');
        this.isSavingEntities = false;
        return null;
      }
    },

    async getSemlabProjects() {
      // Fetch the list of SemLab projects
      let sparql = `
        SELECT  ?project ?projectLabel
        WHERE 
        {
          ?project wdt:P1 wd:Q19064.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
        }

        ORDER BY ?projectLabel      
      `
      
      const sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
      const sparqlResponse = await fetch(sparqlUrl, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/sparql-results+json'
        },
        body: `query=${encodeURIComponent(sparql)}`
      });
      const sparqlData = await sparqlResponse.json();

      this.projects = sparqlData.results.bindings.map(binding => {
        return {
          id: binding.project.value.replace('http://base.semlab.io/entity/', ''),
          label: binding.projectLabel.value
        }
      });
      // console.log("zzzzzz sparqlData", this.projects)


    },

    async buildEntityComparePrompt(entity,useSemlab){

      let useLabel = entity.useLabel ? entity.useLabel : entity.entity;
      let prompt = `Is the ${entity.type}: "${unescapeHtmlEntities(useLabel)}" described in this text:\n`
      prompt += `"${this.blocks[entity.blocks[0]].clean}"\n\n`


      // ask wikidata for possible matches
      try {

          let sparql = `SELECT ?wdLabel ?ps_Label ?wdpqLabel ?pq_Label{
            VALUES (?entity) {(wd:${entity.qid})}

            ?entity ?p ?statement .
            ?statement ?ps ?ps_ .
            
            ?wd wikibase:claim ?p.
            ?wd wikibase:statementProperty ?ps.
            ?wd wikibase:propertyType ?dataType .

            OPTIONAL {
              ?statement ?pq ?pq_ .
              ?wdpq wikibase:qualifier ?pq .

            }
            ${  (useSemlab) ? '' : 'FILTER (?dataType != wikibase:ExternalId)'}
            SERVICE wikibase:label { 
              bd:serviceParam wikibase:language "en" .
            }
          } ORDER BY ?wd ?statement ?ps_`
          

          let sparqlUrl = `https://query.wikidata.org/sparql`;

          if (useSemlab){
            sparqlUrl = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql`;
          }

          const sparqlResponse = await fetch(sparqlUrl, {
            method: 'POST',
            headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/sparql-results+json'
            },
            body: `query=${encodeURIComponent(sparql)}`
          });
          const sparqlData = await sparqlResponse.json();

          let instance_ofs = sparqlData.results.bindings.filter(binding => binding.wdLabel && binding.wdLabel.value === 'instance of');
          instance_ofs = instance_ofs.map(binding => {
            return binding.ps_Label.value
          });
          
          let promptPart2 = ''
          let bindingData = []

          if (sparqlData.results && sparqlData.results.bindings) {
            for (const binding of sparqlData.results.bindings) {
              // Process each binding
              bindingData.push({
                p: binding.wdLabel.value,
                o: binding.ps_Label.value
              });
              let statement = `${binding.wdLabel.value}: ${binding.ps_Label.value}`;
              if (binding.wdpqLabel) {
                statement += ` (${binding.wdpqLabel.value}: ${binding.pq_Label.value})`;
              }
              promptPart2 += `- ${statement}\n`;

            }
          }
          //You are a helpful assistant comparing entities between text and a database. You will be given an entity and its context and then a possible match from the database. Compare the context of the entity in the text to the data points from the database. Reply in JSON Object with three keys, "match" is true or false depending on if it is a match or not and "confidence" a percentage 0 to 100 that this is the correct match if it is believed to be a match and "reason" a short one sentence explanation for your reasoning. 
          promptPart2 = `Below is the data for the ${instance_ofs.join(", ")} "${entity.searchLabel}"\n\nlabel:${entity.searchLabel}\ndescription:${entity.searchDescription}\n${promptPart2}`

          let promptFinal = prompt + promptPart2;


          promptFinal = promptFinal + '\n ' + `Is the ${entity.type} "${unescapeHtmlEntities(entity.entity)}" the same as the ${instance_ofs.join(", ")} "${unescapeHtmlEntities(entity.searchLabel)}" based on this data?`

          return {data: bindingData, prompt: promptFinal}
            
      } catch (error) {
        console.error("Error fetching from Wikidata:", error);
        return null;
      }




    },

    

    
  },


  mounted() {
    // Component lifecycle hook when component is mounted
    this.initialize()
  }
}


</script>
  
<template>

  <LoginModal v-if="!isAuthenticated"/>
  <template v-else>
    <div class="home">

      <div class="content">


        <div class="columns">
          <div class="column">

            <!-- <div class="toolbar">
              <button class="button home-button" @click="$router.push('/')"><font-awesome-icon :icon="['fas', 'arrow-left']" />  <span>Home</span></button>
            </div>
            <div class="toolbar">
              <button class="button" @click="llmJudge">Request LLM Review</button>

              <button class="button" v-if="!workflowComplete" @click="markComplete">Mark as Complete</button>
              <button class="button" v-if="workflowComplete" disabled>Mark as Complete</button>


            </div> -->
          

          </div>
          <div class="column">

            <JobStatus :jobId="documentId" ref="jobstatus" @jobStatus="onJobStatus"  />

          </div>
        </div>
<!-- 
        <div class="tabs is-toggle is-fullwidth">
          <ul>
            <li class="is-active">
              <a>
                <span class="icon is-small"><font-awesome-icon :icon="['fas', 'shapes']" /></span>
                <span>Reconcile via LLM Type / Wikibase Type Compare</span>
              </a>
            </li>
            <li>
              <a>
                <span class="icon is-small" ><font-awesome-icon :icon="['fas', 'database']" /></span>
                <span>Reconcile via Wikibase Search + LLM Compare</span>
              </a>
            </li>
            
          </ul>
        </div> -->
        

        

        <div class="columns">
          <div class="column">
            <div class="etype-list">
              <div v-for="type in Object.keys(entitiesByType).sort()" :key="type">
                
                <a :href="'#type-'+type" >
                  {{ type }} <span class="lite-text">[{{ entitiesByType[type].length }}]</span> 
                </a>  
                  <span v-if="editingType !== type && typeAlignment[type.toLocaleLowerCase()] === null" 
                        class="has-text-danger type-no-alignment">
                    [No Alignment]
                    <font-awesome-icon 
                      :icon="['fas', 'pencil']" 
                      class="edit-icon"
                      @click.prevent.stop="startEditingType(type)" />
                  </span>
                  
                  <span v-if="editingType !== type && typeAlignment[type.toLocaleLowerCase()] !== null" 
                        class="type-is-aligned lite-text-more">
                    <span class="qid-display">{{ typeAlignment[type.toLocaleLowerCase()] }}</span>
                    <span class="type-string-display"><a target="_blank" :href="'https://base.semlab.io/entity/' + typeAlignment[type.toLocaleLowerCase()]">{{ getTypeStringFromQid(typeAlignment[type.toLocaleLowerCase()]) }}</a></span>
                    <font-awesome-icon 
                      :icon="['fas', 'pencil']" 
                      class="edit-icon"
                      @click.prevent.stop="startEditingType(type)" />
                  </span>
                  
                  <select v-if="editingType === type"
                          v-model="typeAlignment[type.toLocaleLowerCase()]"
                          @change="stopEditingType()"
                          @blur="stopEditingType()"
                          @click.stop
                          class="type-alignment-select">
                    <option :value="null">No Alignment</option>
                    <option v-for="(qid, typeString) in typeMap" 
                            :key="qid" 
                            :value="qid">
                      {{ typeString }} ({{ qid }})
                    </option>
                  </select>
                
              </div>
            </div>
          </div>
          <div class="column">
            <div class="a-diff">
              <h3 class="title is-4">All Entities Actions</h3>
              <div>





                <button class="button" v-if="!statusLabelNormalize" @click="normalizeLabels()">Normalize Search Labels</button>
                
                <span v-if="statusLabelNormalize" class="status-text">{{ statusLabelNormalize }}</span>
                <font-awesome-icon v-if="statusLabelNormalize !== null" class="spin" style="font-size: 2em;" :icon="['fas', 'hourglass-half']" />

                <hr class="actions-hr">
                <span>Bulk Reconcile by Project:</span>
                <select v-model="useProjectBulkAlign">
                <option value="" disabled selected>Select a project</option>
                  <option v-for="project in projects" :key="project.id"  :value="project.id">{{ project.label }}</option>
                </select> 

                <button v-if="!statusProjectReconcile" class="button" @click="buildPromptAllSemlab" style="height: 1.5em;">Go</button>
                <font-awesome-icon class="spin" v-else  style="font-size: 2em;" :icon="['fas', 'hourglass-half']" />
                <hr class="actions-hr">
                Bulk Reconcile by Instance Of: Match <select v-model="bulkInstanceOfDoc">
                  <option value="" disabled selected>Doc Type</option>
                  <option v-for="type in Object.keys(entitiesByType).sort()" :key="type" :value="type">{{ type }}</option>
                </select>
                <span>&lt;-TO-&gt;</span>
                <select v-model="bulkInstanceOfBase">
                  <option value="" disabled selected>Wikibase Type</option>
                  <option v-for="type of semlabClasses" :key="type" :value="type.qid">{{ type.label }} ({{ type.qid }})</option>
                </select>
                <button v-if="!statusClassReconcile" class="button" @click="buildPromptByClass" style="height: 1.5em;">Go</button>
                <font-awesome-icon class="spin" v-else  style="font-size: 2em;" :icon="['fas', 'hourglass-half']" />


                <hr class="actions-hr">
                
                <div class="columns">

                  <div class="column" style="border-right: solid 1px black;">
                    
                    <button class="button" v-if="baseWorkQueue1 === false" @click="initalizeWikibaseQueue()">Start Wikibase/LLM Reconciliation Queues</button>
                  
                  
                    <template v-if="baseWorkComplete == false">
                      <button class="button" v-if="baseWorkQueue1 !== false && baseWorkQueueTimer !== null" @click="toggleWikibaseQueue()"> <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'circle-pause']" />Pause Queues</button>
                      <button class="button" v-if="baseWorkQueue1 !== false && baseWorkQueueTimer === null" @click="toggleWikibaseQueue()"> <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'circle-play']" />Resume Queues</button>

                      <div v-if="baseWorkQueue1">Work Queue #1: {{ baseWorkQueue1.length }}</div>
                      <div v-if="baseWorkQueue2">Work Queue #2: {{ baseWorkQueue2.length }}</div>
                      <div v-if="baseWorkQueue3">Work Queue #3: {{ baseWorkQueue3.length }}</div>
                    </template>
                    <template v-else>
                      <div>Work complete</div>
                    </template>
                  

                  </div>
                  <div class="column" >
                    <button class="button" v-if="workQueue1 === false" @click="initalizeWikidataQueue()">Start Wikidata/LLM Reconciliation Queues</button>

                    <template v-if="workComplete == false">
                      <button class="button" v-if="workQueue1 !== false && workQueueTimer !== null" @click="toggleQueue()"> <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'circle-pause']" />Pause Queues</button>
                      <button class="button" v-if="workQueue1 !== false && workQueueTimer === null" @click="toggleQueue()"> <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'circle-play']" />Resume Queues</button>

                      <div v-if="workQueue1">Work Queue #1: {{ workQueue1.length }}</div>
                      <div v-if="workQueue2">Work Queue #2: {{ workQueue2.length }}</div>
                      <div v-if="workQueue3">Work Queue #3: {{ workQueue3.length }}</div>
                    </template>
                    <template v-else>
                      <div>Work complete</div>
                    </template>

                  </div>

                </div>
                
                

              </div>
            </div>


          </div>
            
        </div>

        <div class="buttons" style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center;">
            <button 
              class="button is-primary" 
              :class="{ 'is-loading': isSavingEntities }"
              @click="sendFilteredEntities()"
              :disabled="isSavingEntities || !entities || Object.keys(entities).length === 0">
              {{ entitiesHaveChanges ? 'Save Work' : 'Saved' }}
            </button>
            <label class="checkbox" style="margin-left: 15px;">
              <input type="checkbox" v-model="autoSave">
              Auto-save
            </label>
          </div>
          
          <div class="tabs">
            <ul>
              <li :class="{ 'is-active': activeTab === 'reconcile' }">
                <a @click="activeTab = 'reconcile'">
                  <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'circle-nodes']" />
                  Reconcile
                </a>
              </li>
              <li :class="{ 'is-active': activeTab === 'mint' }">

                <a @click="activeTab = 'mint'">
                  <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'burst']" />
                  Mint</a>
              </li>
              <li :class="{ 'is-active': activeTab === 'data' }">
                <a @click="activeTab = 'data'">
                  <font-awesome-icon style="font-size: 1em; padding-right: 0.5em;" :icon="['fas', 'database']" />
                  Data</a>
              </li>
            </ul>
          </div>
        </div>

        <!-- Reconcile Tab Content -->
        <table v-if="activeTab === 'reconcile'" class="table is-striped is-hoverable is-fullwidth">
          <thead>
            <tr>
              <th>Entity</th>
              <th>Wikibase</th>
              <th>Wikidata</th>
              <th>Blocks</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>

            <template v-for="index in Object.keys(entitiesByType).sort()">
              <tr>
                <td colspan="6" :id="'type-'+index"  class="entity-table-class-header">
                  <a :href="'#type-'+index">{{ index }} <span class="lite-text">[{{ entitiesByType[index].length }}]</span></a>
                  <button class="button is-small type-batch-button-left" 
                          :class="{ 'is-loading': normalizingType === index }"
                          @click="normalizeLabelsByType(index)" 
                          :disabled="normalizingType !== null"
                          style="margin-left: 10px;">
                    <font-awesome-icon v-if="normalizingType !== index" :icon="['fas', 'arrow-down']" style="margin-right: 5px;" />
                    Normalize All
                  </button>
                  <button class="button is-small type-batch-button" @click="processAllEntitiesWikidata(index)" style="margin-left: 5px;">
                    <font-awesome-icon :icon="['fas', 'arrow-down']" style="margin-right: 5px;" />
                    Wiki All
                  </button>
                  <button class="button is-small type-batch-button" @click="processAllEntitiesSemlab(index)" style="margin-left: 5px;">
                    <font-awesome-icon :icon="['fas', 'arrow-down']" style="margin-right: 5px;" />
                    SemLab All
                  </button>
                </td>
              </tr>
              <template v-for="entity in entitiesByType[index]">
                <tr :class="{ 'disabled-row': entity.hidden }">
                  <td v-if="entity.editing">
                    <input type="text" v-model="entity.entity" @keyup.enter="finishEditing($event,entity)" :id="'label-select-'+entity.internal_id+'-entity'" class="input is-small edit-entity-input" @blur="finishEditing($event,entity)" />
                  </td>
                  <td v-else-if="entity.normalizedLabel">

                      <div><input type="radio" @change="entity.useLabel = entity.entity" :value="entity.entity" class="use-label-radio" :id="'label-select-'+entity.internal_id+'-entity'" :name="'label-select-'+entity.internal_id"  :checked="(entity.entity == entity.useLabel)" /><label :for="'label-select-'+entity.internal_id+'-entity'" >{{ entity.entity }}</label> <font-awesome-icon class="edit-entity-uselabel-icon" @click="editEntityLabel(entity)" :icon="['fas', 'pencil']"/></div>
                      <div><input type="radio" @change="entity.useLabel = entity.normalizedLabel" :value="entity.normalizedLabel" class="use-label-radio" :id="'label-select-'+entity.internal_id+'-normalized'" :name="'label-select-'+entity.internal_id"  :checked="(entity.normalizedLabel == entity.useLabel)" /><label :for="'label-select-'+entity.internal_id+'-normalized'" >{{ entity.normalizedLabel }}</label></div>


                  </td>
                  <td v-else> <span class="edit-entity-label" @click="editEntityLabel(entity)">{{ entity.entity }}<font-awesome-icon class="edit-entity-icon" :icon="['fas', 'pencil']"/></span></td>
                  <td class="entity-rec-td" v-if="!entity.qid">



                    <font-awesome-icon v-if="entity.wikiBaseCheckedStatus" class="spin" style="font-size: 1em;" :icon="['fas', 'hourglass-half']" />
                    <span v-if="entity.wikiBaseCheckedStatus === 'SEARCHING'" class="tag is-info">Searching...</span>
                    <span v-if="entity.wikiBaseCheckedStatus === 'RECONCILING'" class="tag is-warning">Reconciling...</span>
                    <span v-if="entity.wikiBaseCheckedStatus === 'ERROR' || entity.wikiBaseError" class="tag is-danger">Error</span>
                    <span v-if="entity.wikiBaseNoMatch" class="tag is-warning">No Search Results</span>
                    <span v-if="entity.wikiBaseNoGoodMatch" class="tag is-warning">No Good Match Found</span>


                    
                    <template v-if="entity.wikiBaseChecked && entity.qid">
                      <span class="tag is-success matched-tag">Matched</span>

                      <div class="hint--top hint--large" :aria-label="entity.wikiBaseReason">
                        <div class="semlab-match-container">
                          <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />
                          <div class="semlab-text-content">
                            <a  :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank">{{ entity.labelSemlab }}</a>
                            <span class="lite-text">({{ entity.wikiBaseDescription }})[{{ entity.wikiBaseConfidence }}%]</span>
                          </div>
                          <font-awesome-icon 
                            class="remove-semlab-icon" 
                            :icon="['fas', 'times']" 
                            @click="removeSemlabQid(entity)"
                            title="Remove SemLab match"
                          />
                        </div>

                      </div>
                    </template>

                    <template v-if="!entity.qid && !entity.wikiBaseCheckedStatus">
                      <div class="semlab-autocomplete" :class="`semlab-autocomplete-${entity.internal_id}`">
                        <input 
                          type="text" 
                          class="input is-small wikidata-search-input"
                          :disabled="entity.hidden"
                          :placeholder="'Search SemLab for ' + (entity.useLabel || entity.entity)"
                          v-model="semlabSearchQueries[entity.internal_id]"
                          @input="searchSemlab(entity.internal_id, $event.target.value)"
                          @keydown="handleSemlabKeydown($event, entity)"
                          @focus="handleSemlabFocus(entity)"
                          @blur="clearSemlabSearch(entity.internal_id)"
                        />
                        <div v-if="semlabSearchLoading[entity.internal_id]" class="dropdown-content is-active">
                          <div class="dropdown-item">Loading...</div>
                        </div>
                        <div v-else-if="semlabSearchResults[entity.internal_id] && semlabSearchResults[entity.internal_id].length > 0" class="dropdown-content is-active">
                          <a 
                            v-for="(item, index) in semlabSearchResults[entity.internal_id]" 
                            :key="item.id"
                            class="dropdown-item"
                            :class="{ 'is-active': semlabSelectedIndex[entity.internal_id] === index }"
                            @mousedown.prevent="selectSemlabItem(entity, item)"
                            @mouseenter="semlabSelectedIndex[entity.internal_id] = index"
                          >
                            <div class="autocomplete-item-content">
                              <div class="autocomplete-item-text">
                                <strong>{{ decodeHtmlEntities(item.label) }}</strong>
                                <div v-if="item.description" class="lite-text" style="font-size: 0.85em; margin-top: 2px;">{{ item.description }}</div>
                              </div>
                            </div>
                          </a>
                        </div>
                      </div>
                    </template>


                  </td>
                  <td class="entity-rec-td" v-else>


                    <template v-if="entity.wikiBaseChecked && entity.qid">
                      <span class="tag is-success matched-tag">Matched</span>

                      <div class="hint--top hint--large" :aria-label="entity.wikiBaseReason">
                        <div class="semlab-match-container">
                          <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />
                          <div class="semlab-text-content">
                            <a  :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank">{{ entity.labelSemlab }}</a>
                            <span class="lite-text">[{{ entity.wikiBaseConfidence }}%]</span>
                          </div>
                          <font-awesome-icon 
                            class="remove-semlab-icon" 
                            :icon="['fas', 'times']" 
                            @click="removeSemlabQid(entity)"
                            title="Remove SemLab match"
                          />
                        </div>

                      </div>

                    
                    </template>
                    <template v-else>
                    <div class="semlab-match-container">
                      <a :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank" class="">
                        <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />
                        <span v-if="entity.labelSemlab" class="thumbnail-label">{{ entity.labelSemlab }}</span>
                        <span v-else>{{ entity.qid }}</span>
                      </a>
                      <font-awesome-icon 
                        class="remove-semlab-icon" 
                        :icon="['fas', 'times']" 
                        @click="removeSemlabQid(entity)"
                        title="Remove SemLab match"
                      />
                    </div>
                    </template>

                  </td>

                  <td class="entity-rec-td">
                    

                    <font-awesome-icon v-if="entity.wikiCheckedStatus" class="spin" style="font-size: 1em;" :icon="['fas', 'hourglass-half']" />
                    <span v-if="entity.wikiCheckedStatus === 'SEARCHING'" class="tag is-info">Searching...</span>
                    <span v-if="entity.wikiCheckedStatus === 'RECONCILING'" class="tag is-warning">Reconciling...</span>
                    <span v-if="entity.wikiCheckedStatus === 'ERROR' || entity.wikiError" class="tag is-danger">Error</span>
                    <span v-if="entity.wikiNoMatch" class="tag is-warning">No Search Results</span>


                    


                    <template v-if="entity.wikiChecked && entity.wikiQid">
                      <span class="tag is-success matched-tag">Matched</span>
                      
                      <div class="hint--top hint--large" :aria-label="entity.wikiReason">


                        <div class="wikidata-match-container">


                          <a  :href="'https://www.wikidata.org/wiki/' + entity.wikiQid" target="_blank">
                                                    <img v-if="entity.wikiThumbnail" :src="entity.wikiThumbnail" alt="Thumbnail" class="thumbnail-wikidata" />

                            {{ entity.wikiLabel }}
                          </a>
                          <span class="lite-text">({{ entity.wikiDescription }})[{{ entity.wikiConfidence }}%]</span>
                          <font-awesome-icon 
                            class="remove-wikidata-icon" 
                            :icon="['fas', 'times']" 
                            @click="removeWikidataQid(entity)"
                            title="Remove Wikidata match"
                          />
                        </div>

                      </div>
                    </template>
                    <template v-else-if="entity.wikiQid">
                     
                      
                      <div class="wikidata-match-container hint--top hint--large" :aria-label="entity.wikiReason">
                        <div class="wikidata-text-content">
                          <a  :href="'https://www.wikidata.org/wiki/' + entity.wikiQid" target="_blank">
                                                    <img v-if="entity.wikiThumbnail" :src="entity.wikiThumbnail" alt="Thumbnail" class="thumbnail-wikidata" />

                            {{ entity.wikiLabel }}</a>
                          <span class="lite-text" v-if="entity.wikiDescription">({{ entity.wikiDescription }})</span>
                        <font-awesome-icon 
                          class="remove-wikidata-icon" 
                          :icon="['fas', 'times']" 
                          @click="removeWikidataQid(entity)"
                          title="Remove Wikidata match"
                        />                          
                        </div>

                      </div>
                    </template>      

                    <template v-if="entity.badMatches && entity.badMatches.length > 0">
                      <div v-for="(match, index) in entity.badMatches" :key="index" > 
                        <div class="hint--top hint--large" :aria-label="match.reason">
                          <span 
                            class="tag is-danger hint--top hint--large clickable-bad-match" 
                            :aria-label="match.reason"
                            @click="selectBadMatch(entity, match)"
                          >
                            {{ decodeHtmlEntities(match.label) }}
                          </span>
                        </div>                       
                        <a :href="'https://www.wikidata.org/entity/' + match.qid" target="_blank"><span class="lite-text">({{ match.qid }})</span></a>
                        <span class="lite-text">
                          ({{ truncateDescription(match.description, entity.internal_id, index) }})
                          <span 
                            v-if="match.description && match.description.split(' ').length > 5"
                            class="expand-description"
                            @click="toggleDescription(entity.internal_id, index)"
                          >
                            {{ expandedDescriptions[`${entity.internal_id}_${index}`] ? ' [less]' : ' [more]' }}
                          </span>
                        </span>
                      </div>
                      <div style="margin-top: 0.5em;">
                        <span 
                          class="tag is-light clickable-none-option"
                          @click="clearBadMatches(entity)"
                        >
                          Clear Non-Matches
                        </span>
                      </div>
                    </template>

                    <template v-if="!entity.wikiQid && (!entity.badMatches)">
                      <div class="wikidata-autocomplete" :class="`wikidata-autocomplete-${entity.internal_id}`">
                        <input 
                          type="text" 
                          class="input is-small wikidata-search-input"
                          :placeholder="'Search Wikidata for ' + (entity.useLabel || entity.entity)"
                          :disabled="entity.hidden"

                          v-model="wikidataSearchQueries[entity.internal_id]"
                          @input="searchWikidata(entity.internal_id, $event.target.value)"
                          @keydown="handleWikidataKeydown($event, entity)"
                          @focus="handleWikidataFocus(entity)"
                          @blur="clearWikidataSearch(entity.internal_id)"
                        />
                        <div v-if="wikidataSearchLoading[entity.internal_id]" class="dropdown-content is-active">
                          <div class="dropdown-item">Loading...</div>
                        </div>
                        <div v-else-if="wikidataSearchResults[entity.internal_id] && wikidataSearchResults[entity.internal_id].length > 0" class="dropdown-content is-active">
                          <a 
                            v-for="(item, index) in wikidataSearchResults[entity.internal_id]" 
                            :key="item.id"
                            class="dropdown-item"
                            :class="{ 'is-active': wikidataSelectedIndex[entity.internal_id] === index }"
                            @mousedown.prevent="selectWikidataItem(entity, item)"
                            @mouseenter="wikidataSelectedIndex[entity.internal_id] = index"
                          >
                            <div class="autocomplete-item-content">
                              <img 
                                v-if="item.image" 
                                :src="item.image" 
                                alt="Wikidata image"
                                class="autocomplete-item-image"
                                @error="$event.target.style.display='none'"
                              />
                              <div class="autocomplete-item-text">
                                <strong>{{ decodeHtmlEntities(item.label) }}</strong>
                                <div v-if="item.description" class="lite-text" style="font-size: 0.85em; margin-top: 2px;">{{ item.description }}</div>
                              </div>
                            </div>
                          </a>
                        </div>
                      </div>
                    </template>


                  </td>
                  <td>{{ entity.blocks.length}} block{{ entity.blocks.length === 1 ? '' : 's' }}</td>
                  <td style="white-space: nowrap;">

 
                    <button :disabled="entity.hidden" class="button reconcile-button" @click="details(entity)">{{ activeEntity && activeEntity.internal_id === entity.internal_id ? 'Hide' : 'Details' }}</button>
                    <button :disabled="entity.hidden" class="button reconcile-button" @click="runSemlab(entity)">SemLab</button>
                    <button :disabled="entity.hidden" class="button reconcile-button" @click="runWikidata(entity)">Wiki</button>
                   <button class="button reconcile-button eye-button" @click="toggleEntityVisibility(entity)" :class="{ 'always-visible': true }">
                      <font-awesome-icon :icon="['fas', entity.hidden ? 'eye-slash' : 'eye']" />
                    </button>

                  </td>
                </tr>
                <tr v-if="activeEntity && activeEntity.internal_id == entity.internal_id">
                  <td colspan="6">
                    <div class="a-diff">
                      <h3 class="title is-4">{{ entity.entity }}</h3>
                      <p><strong>Type:</strong> {{ entity.type }}</p>
                      <p><strong>Block IDs:</strong> {{ entity.blocks.join(', ') }}</p>
                      <p><strong>Context:</strong><p v-html="convertMarkupToHtml(blocks[entity.blocks[0]].markup, entity.internal_id)"></p></p>
                      <button v-if="entity.blocks.length>1" @click="showMoreBlocks[entity.internal_id] = true" class="button is-small">Show more blocks</button>

                      <template v-if="showMoreBlocks[entity.internal_id]">
                        <p v-for="(block, index) in entity.blocks.slice(1)" :key="index"><strong>Block {{ block }}:</strong> <span v-html="convertMarkupToHtml(blocks[block].markup, entity.internal_id)"></span></p>
                        

                      </template>

                      

                      <template v-if="entity.llmLog">
                        <h4 class="title is-5">LLM Log</h4>
                        <ul>
                          <li v-for="(log, index) in entity.llmLog" :key="index">
                            <strong>Prompt:</strong> 
                            <textarea readonly style="font-size: 0.75em;">{{ log.prompt }}</textarea>
                            <strong>Response:</strong>
                            <textarea readonly style="font-size: 0.75em;">{{ log.response }}</textarea>
                          </li>
                        </ul>
                      </template>

                      <!-- <button class="button" @click="buildEntityComparePrompt(entity)">Build Compare Prompt</button>
                      <button class="button" @click="buildCompareOrderPrompt(entity)">Build Serach Order Prompt</button> -->

                    </div>
                  </td>

                </tr>
              </template>



            </template>

            
            <tr v-for="entity in entities" :key="entity.id">
            </tr>
            <tr>
              <td colspan="4" class="has-text-centered">
                <p class="has-text-grey">Click on an entity to build a prompt for LLM comparison.</p>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Mint Tab Content -->
        <div v-if="activeTab === 'mint'">
          <div class="field" style="margin-bottom: 1.5rem;">
            <label class="label">Default Project for Minting</label>
            <div class="control">
              <div class="select is-fullwidth">
                <select v-model="defaultProject">
                  <option :value="null">Select a project...</option>
                  <option v-for="project in projects" :key="project.id" :value="project.id">
                    {{ project.label }}
                  </option>
                </select>
              </div>
            </div>
            <p class="help">Select the default project to use when minting new entities</p>
          </div>
          
          <table class="table is-striped is-hoverable is-fullwidth">
          <thead>
            <tr>
              <th>Entity</th>
              <th>Data</th>
              <th>Action</th>
              <!-- Add more columns as needed -->
            </tr>
          </thead>
          <tbody>
            <template v-for="(entities, type) in entitiesByTypeForMint" :key="'mint-type-' + type">
              <tr>
                <td colspan="4" class="entity-table-class-header">
                  <strong>{{ type }}</strong> <span class="lite-text">[{{ entities.length }}]</span>
                </td>
              </tr>
              <template v-for="entity in entities" :key="'mint-entity-' + entity.internal_id">
                <tr>
                  <td class="mint-table-label">{{ entity.entity }}</td>
                  <td class="mint-table-data" >
                    
                    <div class="columns is-multiline">
                      <!-- Auth Label (single) -->
                      <div class="column is-2">
                        <label class="label is-small">Auth Label</label>
                        <input class="input is-small" type="text" v-model="entity.mintData.authLabel">
                      </div>
                      
                      <!-- Description (single) -->
                      <div class="column is-3">
                        <label class="label is-small">Description</label>
                        <input class="input is-small" type="text" v-model="entity.mintData.description">
                      </div>
                      
                      <!-- Variant Labels (multiple) -->
                      <div class="column is-2">
                        <label class="label is-small">Variant Labels</label>
                        <div v-for="(variant, vIndex) in entity.mintData.variantLabel" :key="'variant-' + vIndex" class="field has-addons">
                          <div class="control is-expanded">
                            <input class="input is-small" type="text" v-model="entity.mintData.variantLabel[vIndex]">
                          </div>
                          <div class="control">
                            <button class="button is-small is-danger" @click="removeFromArray(entity.mintData.variantLabel, vIndex)">
                              <font-awesome-icon :icon="['fas', 'times']" />
                            </button>
                          </div>
                        </div>
                        <button class="button is-small is-success" @click="entity.mintData.variantLabel.push('')">
                          <font-awesome-icon :icon="['fas', 'plus']" /> Add
                        </button>
                      </div>
                      
                      <!-- Projects (multiple) -->
                      <div class="column is-2">
                        <label class="label is-small">Projects</label>
                        <div v-for="(proj, pIndex) in entity.mintData.project" :key="'project-' + pIndex" class="field has-addons">
                          <div class="control is-expanded">
                            <div class="select is-small is-fullwidth">
                              <select v-model="entity.mintData.project[pIndex]">
                                <option v-for="project in projects" :key="project.id" :value="project.id">
                                  {{ project.label }}
                                </option>
                              </select>
                            </div>
                          </div>
                          <div class="control">
                            <button class="button is-small is-danger" @click="removeFromArray(entity.mintData.project, pIndex)">
                              <font-awesome-icon :icon="['fas', 'times']" />
                            </button>
                          </div>
                        </div>
                        <button class="button is-small is-success" @click="entity.mintData.project.push('')">
                          <font-awesome-icon :icon="['fas', 'plus']" /> Add
                        </button>
                      </div>
                      
                      <!-- Instance Of (multiple) -->
                      <div class="column is-2">
                        <label class="label is-small">Instance Of</label>
                        <div v-for="(inst, iIndex) in entity.mintData.instanceOf" :key="'instance-' + iIndex" class="field has-addons">
                          <div class="control is-expanded">
                            <input class="input is-small" type="text" v-model="entity.mintData.instanceOf[iIndex]" placeholder="QID">
                          </div>
                          <div class="control">
                            <button class="button is-small is-danger" @click="removeFromArray(entity.mintData.instanceOf, iIndex)">
                              <font-awesome-icon :icon="['fas', 'times']" />
                            </button>
                          </div>
                        </div>
                        <button class="button is-small is-success" @click="entity.mintData.instanceOf.push('')">
                          <font-awesome-icon :icon="['fas', 'plus']" /> Add
                        </button>
                      </div>
                      
                      <!-- Wikidata QID (single) -->
                      <div class="column is-1">
                        <label class="label is-small">Wiki QID</label>
                        <input class="input is-small" type="text" v-model="entity.mintData.wikidataQid" readonly>
                      </div>
                    </div>



                  </td>
                  <td class="mint-table-action">
                    Mint
                  </td>

                  <!-- Add more columns as needed -->
                </tr>
              </template>
            </template>
            <template v-if="Object.keys(entitiesByTypeForMint).length === 0">
              <tr>
                <td colspan="4" class="has-text-centered">
                  <p class="has-text-grey">No entities ready for minting</p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        </div>

        <!-- Data Tab Content -->
        <div v-if="activeTab === 'data'" class="data-tab-content" style="padding: 20px; min-height: 400px;">
          <!-- Data content will go here -->
          <p class="has-text-grey">Data view coming soon...</p>
        </div>

<!-- 
        <template v-for="(etype, index) in entitiesByType">
          <div >
            {{ index }}
          </div>
          <template v-for="entity in etype">
            <div>
            {{ entity }}
            
            <button class="button" @click="buildCompareOrderPrompt(entity)">Build Prompt</button>
              

            </div>

          </template>
          
        </template> -->


      </div>
    </div>
      
  </template>


  

  
</template>
<style>
.entity-rec-td{
  min-width: 300px;
}

.block-highlight {  
  background-color: #ff0;
  box-shadow: 0px 0px 10px 0px #ff0;
  color: black;
  border-radius: 3px;
  padding: 1px;  
}

@media (prefers-color-scheme: dark) {
.block-highlight {  
    background-color: #ffff0052;
    box-shadow: 0px 0px 10px 0px #ffff0052;
    color: white;
    border-radius: 3px;
    padding: 1px;
}
}

</style>

<style scoped>


.actions-hr{
 background-color: var(--bulma-text);
 height: 1px;
}

.match-info{
  color: var(--bulma-text);
  font-size: 1em;
  vertical-align: middle;
  padding-left: 0.5em;
  

}

.thumbnail-wikidata{
  width: 50px;
  height: 50px;
  vertical-align: middle;
  object-fit: cover;
  aspect-ratio: 1;
clip-path: polygon(20% 0%, 80% 0%, 100% 20%, 100% 80%, 80% 100%, 20% 100%, 0% 80%, 0% 20%);

}

.thumbnail-semlab {

  width: 50px;
  height: 50px; vertical-align: middle;
  aspect-ratio: 1;
  clip-path: polygon(50% 100%, 0 0, 100% 0);

  object-fit: cover;
}

.thumbnail-semlab-link{
    transform: scale(1);

}

.thumbnail-semlab-link:hover {
  transform: scale(2);
  transition: transform 0.3s ease-in-out;

}

.thumbnail-label {
  vertical-align: middle; line-height: 50px; display: inline-block; height: 50px;
}

.entity-table-class-header{
  background-color: #f0f0f0;
  font-weight: bold;
  text-transform: uppercase;

}
.etype-list{
  padding: 1em;
  margin: 1em;
  width: 75%;
  background-color: whitesmoke;
  columns: 2;
  border: solid 1px #ccc;
}
.etype-list a{
  text-transform: capitalize;
  color:#2c2c2c
}
.lite-text{
  font-size: 0.8em;
  color: #666;
}
.lite-text-more{
  font-size: 0.8em;
  color: #838383;
}

.a-diff{
  padding: 1em;
  margin: 1em;
  background-color: whitesmoke;
}
.diff-example{
  font-family: 'Courier New', Courier, monospace;
}


.wikidata-search-input{
  max-width: 200px;
}


textarea {
  width: 100%;
  height: 100%;
  min-height: 600px;
  padding: 1em;
  font-size: 1.5em;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
}

.home{
  padding: 1em;
}

.matched-tag{
  animation: fadeinout 2s linear forwards;
  opacity: 1;

}
.use-label-radio{
  margin-right: 0.25em;
}
label{
  cursor: pointer;
}

.edit-entity-label{
  cursor: pointer;

}

.edit-entity-label .edit-entity-icon{
  opacity: 0;
  margin-left: 0.25em;
  cursor: pointer;
}
.edit-entity-label:hover .edit-entity-icon{
  opacity: 1;
}
.edit-entity-uselabel-icon{
  opacity: 0;
  margin-left: 0.25em;
  cursor: pointer;
}
.edit-entity-uselabel-icon:hover{
  opacity: 1;
}

@keyframes fadeinout {
  0% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    display: none;
  }
}

@media (prefers-color-scheme: dark) {
  .a-diff, textarea {
    background-color: #2c2c2c; /* Darker background for dark mode */
    color: #f5f5f5; /* Lighter text for dark mode */
  }

  .entity-table-class-header{
    background-color: #41404f;
    font-weight: bold;
    text-transform: uppercase;

  }
  .etype-list{
    background-color: #41404f;
  }
  .etype-list a, .lite-text{
    color: #f5f5f5 !important;
  }
  .clickable-none-option {
    background-color: #4a4a4a !important;
    color: #f5f5f5 !important;
  }
  .clickable-none-option:hover {
    background-color: #6c757d !important;
    color: white !important;
  }
  
  .wikidata-autocomplete .dropdown-content,
  .semlab-autocomplete .dropdown-content {
    background: #2c2c2c;
    border-color: #4a4a4a;
  }
  
  .wikidata-autocomplete .dropdown-item,
  .semlab-autocomplete .dropdown-item {
    color: #f5f5f5;
    border-bottom-color: #3a3a3a;
  }
  
  .wikidata-autocomplete .dropdown-item:hover,
  .wikidata-autocomplete .dropdown-item.is-active,
  .semlab-autocomplete .dropdown-item:hover,
  .semlab-autocomplete .dropdown-item.is-active {
    background-color: #0056b3;
    color: white;
  }
  
  .wikidata-autocomplete .dropdown-item:hover .lite-text,
  .wikidata-autocomplete .dropdown-item.is-active .lite-text,
  .semlab-autocomplete .dropdown-item:hover .lite-text,
  .semlab-autocomplete .dropdown-item.is-active .lite-text {
    color: rgba(255, 255, 255, 0.8) !important;
  }
  
  .wikidata-autocomplete .dropdown-item strong,
  .semlab-autocomplete .dropdown-item strong {
    color: #f5f5f5;
  }
  
  .wikidata-autocomplete .dropdown-item .lite-text,
  .semlab-autocomplete .dropdown-item .lite-text {
    color: #b0b0b0 !important;
  }
  
  .wikidata-autocomplete .input,
  .semlab-autocomplete .input {
    background-color: #3a3a3a;
    color: #f5f5f5;
    border-color: #4a4a4a;
  }
  
  .autocomplete-item-image {
    background-color: #3a3a3a;
  }
  
  .remove-wikidata-icon, .remove-semlab-icon {
    color: #ff6b6b;
  }
  
  .remove-wikidata-icon:hover, .remove-semlab-icon:hover {
    color: #ff5252;
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.spin {
  animation: spin 2s linear infinite;
}

@keyframes growShrink {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.5); /* Grow to 1.5 times the size */
  }
  100% {
    transform: scale(1); /* Shrink back to normal */
  }
}

.thumbs-up {
  animation: growShrink 0.5s ease-in-out; /* Adjust duration and timing function as needed */
}

@keyframes fadeWarning {
  0%, 100% {
    color: inherit; /* Or specify the default icon color */
  }
  50% {
    color: orangered; 
  }
}

.warning {
  animation: fadeWarning 2.5s ease-in-out infinite; /* Adjust duration as needed */
}

.clickable-bad-match {
  cursor: pointer;
  transition: all 0.2s ease;
  max-width: 200px;
  overflow: hidden;
}

.clickable-bad-match:hover {
  background-color: #dc3545 !important;
  transform: scale(1.05);
}

.expand-description {
  cursor: pointer;
  color: #007bff;
  text-decoration: underline;
  font-size: 0.9em;
}

.expand-description:hover {
  color: #0056b3;
}

.clickable-none-option {
  cursor: pointer;
  transition: all 0.2s ease;
}

.clickable-none-option:hover {
  background-color: #6c757d !important;
  color: white !important;
  transform: scale(1.05);
}

.wikidata-autocomplete,
.semlab-autocomplete {
  position: relative;
  width: 100%;
}

.wikidata-autocomplete .input,
.semlab-autocomplete .input {
  width: 100%;
}

.wikidata-autocomplete .dropdown-content,
.semlab-autocomplete .dropdown-content {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  background: white;
  border: 1px solid #dbdbdb;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  max-height: 200px;
  overflow-y: auto;
  overflow-x: hidden;
  margin-top: 2px;
}

.wikidata-autocomplete .dropdown-item,
.semlab-autocomplete .dropdown-item {
  padding: 0.75rem;
  cursor: pointer;
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  color: #363636;
  border-bottom: 1px solid #f0f0f0;
}

.wikidata-autocomplete .dropdown-item:last-child,
.semlab-autocomplete .dropdown-item:last-child {
  border-bottom: none;
}

.wikidata-autocomplete .dropdown-item:hover,
.wikidata-autocomplete .dropdown-item.is-active,
.semlab-autocomplete .dropdown-item:hover,
.semlab-autocomplete .dropdown-item.is-active {
  background-color: #007bff;
  color: white;
}

.wikidata-autocomplete .dropdown-item:hover .lite-text,
.wikidata-autocomplete .dropdown-item.is-active .lite-text,
.semlab-autocomplete .dropdown-item:hover .lite-text,
.semlab-autocomplete .dropdown-item.is-active .lite-text {
  color: rgba(255, 255, 255, 0.8) !important;
}

.wikidata-autocomplete .dropdown-item strong,
.semlab-autocomplete .dropdown-item strong {
  display: block;
  margin-bottom: 2px;
  color: #363636;
}

.autocomplete-item-content {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.autocomplete-item-image {
  width: 40px;
  height: 40px;
  max-width: 40px;
  max-height: 40px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
  background-color: #f5f5f5;
}

.autocomplete-item-text {
  flex: 1;
  min-width: 0; /* Allow text to shrink */
}

.wikidata-match-container, .semlab-match-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  position: relative;
}

.wikidata-text-content, .semlab-text-content {
  flex: 1;
}

.remove-wikidata-icon, .remove-semlab-icon {
  opacity: 0;
  color: #dc3545;
  cursor: pointer;
  transition: opacity 0.2s ease;
  font-size: 1.25em;
  vertical-align: middle;
  padding-left: 0.25em;
}

.wikidata-match-container:hover .remove-wikidata-icon,
.semlab-match-container:hover .remove-semlab-icon {
  opacity: 1;
}

.remove-wikidata-icon:hover, .remove-semlab-icon:hover {
  color: #c82333;
  transform: scale(1.2);
}

.judgement-text{
  font-style: italic;
}

.toolbar{
  padding: 1em;
}



.edit-icon {
  display: none;
  margin-left: 5px;
  cursor: pointer;
  font-size: 0.95em !important;
  color: inherit;
  transition: color 0.2s;
}

.edit-icon:hover {
  color: #333;
}

.type-no-alignment:hover .edit-icon,
.type-is-aligned:hover .edit-icon {
  display: inline-block;
}

.type-is-aligned .qid-display {
  margin-left: 5px;
  display: inline;
}

.type-is-aligned .type-string-display {
  margin-left: 5px;
  display: none;
  text-decoration: underline;
}

.type-is-aligned:hover .qid-display {
  display: none;
}

.type-is-aligned:hover .type-string-display {
  display: inline;
}

.type-alignment-select {
  display: inline-block;
  margin-left: 10px;
  padding: 2px 5px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 0.9em;
}

.disabled-row {
  position: relative;
  opacity: 0.5;
}

.disabled-row::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(128, 128, 128, 0.2) 10px,
    rgba(128, 128, 128, 0.2) 20px
  );
  pointer-events: none;
  z-index: 1;
}

.disabled-row .eye-button.always-visible {
  position: relative;
  z-index: 2;
  opacity: 1 !important;
  pointer-events: auto;
}

.eye-button {
  min-width: 40px;
  height: 2.5em;
  padding: calc(0.5em - 1px) 0.75em;
}

.type-batch-button {
  float: right;
  margin-top: -3px;
}

.type-batch-button-left {
  margin-top: -3px;
  margin-left: 10px;
}

.mint-table-data {
  width: 75%;
  min-width: 300px;
}
.mint-table-label{
  max-width: 200px;
  width: 125px;
  overflow: hidden;
}
.mint-table-action{
  width: 50px;
  max-width: 50px;
}

</style>