<script>
import { socket } from '../socket';
import { mapWritableState } from 'pinia';
import { useUserStore } from '../stores/user';
import LoginModal from '../components/LoginModal.vue';
import JobStatus from '../components/JobStatus.vue';

// Helper function to promisify socket.emit
function asyncEmit(eventName, data) {
  return new Promise(function (resolve, reject) {
    socket.emit(eventName, data, (response) => {
      resolve(response);
    });
  });
}

export default {
  name: 'WorkBlocks',
  components: {
    LoginModal,
    JobStatus
  },
  data() {
    return {
      documentId: null,
      blocks: {},
      blockIds: [],
      entities: {},
      classMap: {},

      // Convenience entities (global entities available in all blocks)
      convenienceEntities: [], // Array of {qid, label}
      showConvenienceEntityModal: false,
      convenienceEntitySearchQuery: '',
      convenienceEntitySearchResults: [],
      convenienceEntitySearchLoading: false,
      convenienceEntitySelectedIndex: -1,

      // Virtual scrolling
      containerHeight: 600,
      itemHeight: 100, // estimated height per block
      scrollTop: 0,
      visibleStart: 0,
      visibleEnd: 0,
      bufferSize: 5, // extra items to render above/below viewport

      // Custom search
      searchActive: false,
      searchQuery: '',
      searchResults: [],
      currentSearchIndex: 0,

      // Job Status panel
      jobStatusExpanded: false,

      // Block focus
      focusedBlockId: null,
      showAllEntities: false,

      // Drag-and-drop line drawing
      isDragging: false,
      dragStartEntity: null,
      dragStartElement: null,
      dragHoverElement: null, // Track element currently being hovered over during drag
      dragLineX: 0,
      dragLineY: 0,
      dragLine: null,

      // Triple statements organized by block ID
      // Format: { blockId: [ {triple objects} ] }
      tripleStatements: {},

      // Property typeahead state
      propertySearchQuery: {},  // { tripleId: searchQuery }
      propertySearchResults: {}, // { tripleId: [results] }
      propertySearchActive: {},  // { tripleId: boolean }
      propertySearchSelectedIndex: {}, // { tripleId: number }
      originalPropertyValues: {}, // { tripleId: { label, qid } } - for cancel/escape

      // Context/Qualifier state
      contextPropertySearchQuery: {}, // { tripleId: searchQuery }
      contextPropertySearchResults: {}, // { tripleId: [results] }
      contextPropertySearchActive: {}, // { tripleId: boolean }
      contextPropertySearchSelectedIndex: {}, // { tripleId: number }
      contextCursorMode: null, // { tripleId, propertyQid, propertyLabel, propertyType } when in selection mode
      contextErrorMessage: null, // Temporary error message to display

      // Block-subject triple state
      blockSubjectSelectionMode: null, // { blockId, blockLabel } when selecting object for block-subject triple

      // Recent properties
      recentTripleProperties: [], // Last 10 properties used for triples
      recentQualifierProperties: [], // Last 10 properties used for qualifiers
      showRecentProperties: {}, // { tripleId: boolean }
      showRecentQualifierProperties: {}, // { tripleId: boolean }

      // Properties data
      propertiesData: null,
      allProperties: [],
      propertiesBySubject: {},
      propertiesByObject: {},
      propertiesByPair: {},
      excludedProperties: ['P1','P21'], // Properties to never show in relationships

      // Property validation data from semlab.io
      propertyPatternsData: null, // Full properties.json data

      isLoading: false,
      isExtractingRelationships: false,
      lastExtractionFoundNone: false,

      // Advanced triple generation modal
      showAdvancedTripleModal: false,
      advancedTripleBlockId: null,
      availableProperties: [],
      selectedProperties: [],
      selectAllProperties: false,
      useReconciledOnly: true,
      customPromptText: '',
      loadingProperties: false,
      propertySearchFilter: '',

      // Batch processing
      isBatchProcessing: false,
      batchProcessingStopped: false,
      batchCurrentBlockIndex: 0,
      batchTotalBlocks: 0,

      // Triple save debouncing
      tripleSaveTimer: null,
      tripleSaveDelay: 1000, // 1 second delay before saving
      isLoadingTriples: false, // Flag to prevent saving during initial load

      // Block editing
      editingBlockId: null,
      editingMarkup: '',

      // Reconciliation interface
      reconcilingEntityId: null,
      reconcilingBlockId: null, // Track which block the reconciliation is for
      reconcilingEntityElement: null, // Track the clicked entity element for positioning
      reconcilingEntityOccurrence: 0, // Track which occurrence of the entity (0-indexed)
      reconcileSearchQuery: '',
      reconcileSearchResults: [],
      reconcileSearchLoading: false,
      reconcileSelectedIndex: -1,
      reconcileSearchTimer: null,

      // Wikidata search
      wikidataSearchQuery: '',
      wikidataSearchResults: [],
      wikidataSearchLoading: false,
      wikidataSelectedIndex: -1,
      wikidataSearchTimer: null,

      // Mint interface
      mintData: {
        authLabel: '',
        description: '',
        variantLabel: [],
        project: [], // Array of {qid, label}
        instanceOf: [] // Array of {qid, label}
      },
      mintValidationError: '',

      // Mint typeahead state
      mintProjectQuery: '',
      mintProjectResults: [],
      mintProjectSearchActive: false,
      mintProjectSelectedIndex: -1,
      mintInstanceQuery: '',
      mintInstanceResults: [],
      mintInstanceSearchActive: false,
      mintInstanceSelectedIndex: -1,

      // Projects list
      projects: [],

      // Wikidata import project selection
      wikidataImportProject: null,

      // Last used project (for auto-defaulting)
      lastUsedProject: null,

      // Text selection tooltip for entification
      selectionTooltip: {
        show: false,
        x: 0,
        y: 0,
        selectedText: '',
        selectedClass: '',
        blockId: null,
        selectionStart: 0,
        selectionEnd: 0,
        hasEntityOverlap: false
      },
      isProcessingEntification: false,
      recentClasses: [], // Last 5 used classes for quick selection
      // Pending triple entification - to update triple after entifying text
      pendingTripleEntification: null, // { triple, entityType: 'subject' | 'object' }
    };
  },

  computed: {
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user', 'login_token']),

    visibleBlocks() {
      // Render all blocks - no virtual scrolling for now to avoid height calculation issues
      return this.blockIds.map((id) => ({
        id: parseInt(id), // Ensure ID is a number for comparison
        block: this.blocks[id]
      }));
    },

    sortedClassMap() {
      // Return classMap sorted alphabetically by class name
      const sorted = {};
      Object.keys(this.classMap)
        .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
        .forEach(key => {
          sorted[key] = this.classMap[key];
        });
      return sorted;
    },

    currentSearchResult() {
      if (this.searchResults.length === 0) return null;
      return this.searchResults[this.currentSearchIndex];
    },

    focusedBlockEntities() {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined || !this.blocks[this.focusedBlockId]) return [];

      const block = this.blocks[this.focusedBlockId];
      const markup = block.markup || '';
      const entityIds = new Set();

      // Extract entity IDs from markup
      const regex = /\{([^|]+)\|([^|]+)\|([^}]+)\}/g;
      let match;
      while ((match = regex.exec(markup)) !== null) {
        entityIds.add(match[2]); // match[2] is the entity ID
      }

      // Return entities with their metadata
      const allEntities = Array.from(entityIds).map(id => ({
        id,
        ...this.entities[id]
      })).filter(e => e.entity); // Filter out any missing entities

      // Filter to only show entities with qid (Wikibase) unless showAllEntities is true
      if (this.showAllEntities) {
        return allEntities;
      } else {
        return allEntities.filter(e => e.qid);
      }
    },

    focusedBlockEntitiesCount() {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined || !this.blocks[this.focusedBlockId]) return { withQid: 0, total: 0 };

      const block = this.blocks[this.focusedBlockId];
      const markup = block.markup || '';
      const entityIds = new Set();

      const regex = /\{([^|]+)\|([^|]+)\|([^}]+)\}/g;
      let match;
      while ((match = regex.exec(markup)) !== null) {
        entityIds.add(match[2]);
      }

      const allEntities = Array.from(entityIds).map(id => this.entities[id]).filter(e => e && e.entity);
      const withQid = allEntities.filter(e => e.qid).length;

      return { withQid, total: allEntities.length };
    },

    currentBlockTriples() {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined) return [];
      return this.tripleStatements[this.focusedBlockId] || [];
    },

    filteredProperties() {
      if (!this.propertySearchFilter.trim()) {
        return this.availableProperties;
      }

      const query = this.propertySearchFilter.toLowerCase();
      return this.availableProperties.filter(prop => {
        return (
          prop.pid.toLowerCase().includes(query) ||
          prop.label.toLowerCase().includes(query) ||
          (prop.description && prop.description.toLowerCase().includes(query)) ||
          prop.ranges.some(r => r.toLowerCase().includes(query))
        );
      });
    }
  },

  watch: {
    user(newUser, oldUser) {
      if (newUser && !oldUser) {
        this.initialize();
      }
    },
    'selectionTooltip.selectedClass'(newVal, oldVal) {
      console.log('selectedClass changed from', oldVal, 'to', newVal);
    },
    wikidataImportProject(newVal) {
      if (newVal) {
        this.saveLastUsedProject(newVal);
      }
    },
    selectedProperties: {
      handler() {
        if (this.showAdvancedTripleModal) {
          this.saveAdvancedTripleSettings();
        }
      },
      deep: true
    },
    useReconciledOnly() {
      if (this.showAdvancedTripleModal) {
        this.saveAdvancedTripleSettings();
      }
    },
    customPromptText() {
      if (this.showAdvancedTripleModal) {
        this.saveAdvancedTripleSettings();
      }
    },
    tripleStatements: {
      handler() {
        // Don't save if we're currently loading triples from backend
        if (this.isLoadingTriples) {
          return;
        }

        // Debounce the save operation to avoid excessive API calls
        if (this.tripleSaveTimer) {
          clearTimeout(this.tripleSaveTimer);
        }
        this.tripleSaveTimer = setTimeout(() => {
          this.saveTriplesToBackend();
        }, this.tripleSaveDelay);
      },
      deep: true
    }
  },

  methods: {
    async initialize() {
      this.documentId = this.$route.params.id;
      if (!this.documentId) {
        console.error('No document ID provided');
        return;
      }

      await this.loadBlocks();
      await this.loadPropertiesData();
      await this.loadProjects();
      await this.loadTriplesFromBackend();
    },

    async loadPropertiesData() {
      try {
        const response = await fetch('https://semlab.io/property-explorer/data/properties.json');
        const jsonData = await response.json();

        // The data is nested under 'properties' key
        this.propertiesData = jsonData.properties;

        console.log('=== PROPERTIES DATA LOADED ===');
        console.log('Raw data structure:', Object.keys(jsonData));
        console.log('Number of properties:', Object.keys(this.propertiesData).length);

        this.derivePropertyDatasets();
      } catch (error) {
        console.error('Failed to load properties data:', error);
      }
    },

    derivePropertyDatasets() {
      console.log('\n=== DERIVING PROPERTY DATASETS ===\n');

      if (!this.propertiesData || typeof this.propertiesData !== 'object') {
        console.error('Invalid properties data');
        return;
      }

      // 1. List of all properties and their P IDs
      this.allProperties = Object.entries(this.propertiesData).map(([pid, data]) => ({
        pid,
        label: data.label,
        description: data.description,
        type: data.type || 'unknown', // Property type for context selection
        subStatsTotal: data.subStatsTotal || 0,
        objStatsTotal: data.objStatsTotal || 0,
        totalUse: (data.subStatsTotal || 0) + (data.objStatsTotal || 0)
      }));

      console.log('1. ALL PROPERTIES:', this.allProperties.length, 'properties loaded');
      if (this.allProperties.length > 0) {
        console.log('Sample properties:', this.allProperties.slice(0, 3));
      }

      // 2. Properties by Subject QID (subStats)
      this.propertiesBySubject = {};
      Object.entries(this.propertiesData).forEach(([pid, data]) => {
        if (data.subStats) {
          Object.entries(data.subStats).forEach(([qid, statObj]) => {
            if (!this.propertiesBySubject[qid]) {
              this.propertiesBySubject[qid] = [];
            }
            this.propertiesBySubject[qid].push({
              pid,
              label: data.label,
              count: statObj.count,
              percent: statObj.percent,
              qidLabel: statObj.label,
              role: 'subject'
            });
          });
        }
      });

      // Sort by count descending for each QID
      Object.keys(this.propertiesBySubject).forEach(qid => {
        this.propertiesBySubject[qid].sort((a, b) => b.count - a.count);
      });

      console.log('\n2. PROPERTIES BY SUBJECT QID:', Object.keys(this.propertiesBySubject).length, 'unique subject QIDs');
      const sampleSubjectQid = Object.keys(this.propertiesBySubject)[0];
      if (sampleSubjectQid && this.propertiesBySubject[sampleSubjectQid]) {
        console.log(`Sample - QID ${sampleSubjectQid} as subject can use:`, this.propertiesBySubject[sampleSubjectQid].slice(0, 5));
      }

      // 3. Properties by Object QID (objStats)
      this.propertiesByObject = {};
      Object.entries(this.propertiesData).forEach(([pid, data]) => {
        if (data.objStats) {
          Object.entries(data.objStats).forEach(([qid, statObj]) => {
            if (!this.propertiesByObject[qid]) {
              this.propertiesByObject[qid] = [];
            }
            this.propertiesByObject[qid].push({
              pid,
              label: data.label,
              count: statObj.count,
              percent: statObj.percent,
              qidLabel: statObj.label,
              role: 'object'
            });
          });
        }
      });

      // Sort by count descending for each QID
      Object.keys(this.propertiesByObject).forEach(qid => {
        this.propertiesByObject[qid].sort((a, b) => b.count - a.count);
      });

      console.log('\n3. PROPERTIES BY OBJECT QID:', Object.keys(this.propertiesByObject).length, 'unique object QIDs');
      const sampleObjectQid = Object.keys(this.propertiesByObject)[0];
      if (sampleObjectQid && this.propertiesByObject[sampleObjectQid]) {
        console.log(`Sample - QID ${sampleObjectQid} as object can use:`, this.propertiesByObject[sampleObjectQid].slice(0, 5));
      }

      // 4. Properties by entity type pair (subject QID -> object QID)
      this.propertiesByPair = {};
      Object.entries(this.propertiesData).forEach(([pid, data]) => {
        if (data.subStats && data.objStats) {
          Object.keys(data.subStats).forEach(subQid => {
            Object.keys(data.objStats).forEach(objQid => {
              const pairKey = `${subQid}|${objQid}`;
              if (!this.propertiesByPair[pairKey]) {
                this.propertiesByPair[pairKey] = [];
              }
              // Use minimum of the two counts as an estimate of pair frequency
              const estimatedCount = Math.min(data.subStats[subQid].count, data.objStats[objQid].count);
              this.propertiesByPair[pairKey].push({
                pid,
                label: data.label,
                count: estimatedCount,
                subCount: data.subStats[subQid].count,
                objCount: data.objStats[objQid].count,
                subLabel: data.subStats[subQid].label,
                objLabel: data.objStats[objQid].label
              });
            });
          });
        }
      });

      // Sort by count descending for each pair
      Object.keys(this.propertiesByPair).forEach(pairKey => {
        this.propertiesByPair[pairKey].sort((a, b) => b.count - a.count);
      });

      console.log('\n4. PROPERTIES BY ENTITY PAIR:', Object.keys(this.propertiesByPair).length, 'unique entity type pairs');
      const samplePairKey = Object.keys(this.propertiesByPair)[0];
      if (samplePairKey && this.propertiesByPair[samplePairKey]) {
        const [sampleSubQid, sampleObjQid] = samplePairKey.split('|');
        console.log(`Sample - QID ${sampleSubQid} -> QID ${sampleObjQid}:`, this.propertiesByPair[samplePairKey].slice(0, 5));
      }

      console.log('\n=== DATASET GENERATION COMPLETE ===\n');
      console.log('Summary:');
      console.log(`- Total properties: ${this.allProperties.length}`);
      console.log(`- Subject QIDs covered: ${Object.keys(this.propertiesBySubject).length}`);
      console.log(`- Object QIDs covered: ${Object.keys(this.propertiesByObject).length}`);
      console.log(`- Entity pairs covered: ${Object.keys(this.propertiesByPair).length}`);
    },

    async fetchPropertyPatterns() {
      try {
        const response = await fetch('https://semlab.io/property-explorer/data/properties.json');
        this.propertyPatternsData = await response.json();
        console.log('Property patterns loaded:', Object.keys(this.propertyPatternsData.properties).length, 'properties');
      } catch (error) {
        console.error('Failed to fetch property patterns:', error);
      }
    },

    getEntityInstanceOfClasses(entity) {
      // Get all P1 (instance of) values for an entity
      if (!entity || !entity.qid) return [];

      // Check if entity has statements and P1 property
      if (entity.statements && entity.statements.P1) {
        return entity.statements.P1.map(stmt => stmt.value);
      }

      return [];
    },

    validateTriplePattern(triple) {
      if (!this.propertyPatternsData) {
        return { valid: true, confidence: 1, reason: 'No pattern data loaded' };
      }

      const propertyData = this.propertyPatternsData.properties[triple.propertyQid];
      if (!propertyData || !propertyData.instanceOfStats) {
        return { valid: true, confidence: 0.5, reason: 'Property has no pattern data' };
      }

      // Get subject and object entities
      const subjectEntity = this.entities[triple.subjectId];
      const objectEntity = this.entities[triple.objectId];

      // If either entity is unreconciled, we can't validate the pattern
      if (!subjectEntity?.qid || !objectEntity?.qid) {
        return { valid: true, confidence: 0.5, reason: 'Unreconciled entities cannot be validated' };
      }

      // Get instance of classes for both entities
      const subjectClasses = this.getEntityInstanceOfClasses(subjectEntity);
      const objectClasses = this.getEntityInstanceOfClasses(objectEntity);

      if (subjectClasses.length === 0 || objectClasses.length === 0) {
        return { valid: true, confidence: 0.5, reason: 'Missing instance of data' };
      }

      // Check if any combination of subject/object classes appears in the pattern data
      let foundPattern = false;
      let maxCount = 0;

      for (const subClass of subjectClasses) {
        for (const objClass of objectClasses) {
          const pattern = `${subClass}-${objClass}`;
          const count = propertyData.instanceOfStats[pattern];
          if (count) {
            foundPattern = true;
            maxCount = Math.max(maxCount, count);
          }
        }
      }

      if (!foundPattern) {
        return {
          valid: false,
          confidence: 0,
          reason: `No examples of ${triple.propertyQid} connecting ${subjectClasses[0]} to ${objectClasses[0]}`
        };
      }

      // Calculate confidence based on count (higher count = higher confidence)
      let confidence = 1;
      if (maxCount < 3) confidence = 0.3;
      else if (maxCount < 10) confidence = 0.6;
      else if (maxCount < 50) confidence = 0.8;

      return { valid: true, confidence, reason: `Found ${maxCount} examples in system` };
    },

    async loadProjects() {
      try {
        const sparql = `SELECT ?project ?projectLabel WHERE {
          ?project wdt:P1 wd:Q19064.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
        }
        ORDER BY ?projectLabel`;

        const sparqlResponse = await fetch('https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql', {
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
        console.log('Projects loaded:', this.projects.length);
      } catch (error) {
        console.error('Failed to load projects:', error);
      }
    },

    async loadBlocks() {
      this.isLoading = true;

      socket.emit('get_ner', { doc: this.documentId, user: this.user }, (response) => {
        console.log("get_ner response", response);

        if (response.success) {
          // Process blocks from NER response
          this.blocks = response.ner.blocks;
          this.blockIds = Object.keys(this.blocks).sort((a, b) => parseInt(a) - parseInt(b));

          // Store entities for qid lookup
          if (response.ner.entities) {
            this.entities = response.ner.entities;
          }

          // Store class map for instance of labels
          if (response.ner.class_map) {
            console.log('DEBUG: Received class_map type:', typeof response.ner.class_map);
            console.log('DEBUG: Received class_map:', response.ner.class_map);
            console.log('DEBUG: Is Array?', Array.isArray(response.ner.class_map));
            this.classMap = response.ner.class_map;
            console.log('DEBUG: Stored classMap type:', typeof this.classMap);
            console.log('DEBUG: Stored classMap keys:', Object.keys(this.classMap).slice(0, 5));
          }

          // Load convenience entities from get_ner response
          if (response.ner.convenience_entities) {
            this.convenienceEntities = response.ner.convenience_entities;
            console.log('Loaded convenience entities from get_ner:', this.convenienceEntities.length);
          } else {
            // Fallback: try separate call to get_convenience_entities
            this.loadConvenienceEntities();
          }

          console.log(`Loaded ${this.blockIds.length} blocks`);

          this.isLoading = false;
        } else {
          console.error('Failed to load blocks:', response?.error);
          this.isLoading = false;
        }
      });
    },

    onScroll(event) {
      this.scrollTop = event.target.scrollTop;
      this.updateSearchHighlights();
    },

    // Convert custom markup to HTML
    markupToHTML(markup, blockId = null) {
      if (!markup) return '';

      let html = '';
      let i = 0;
      const hasSearch = this.searchActive && this.searchQuery.trim();
      const searchQuery = hasSearch ? this.searchQuery.toLowerCase() : null;

      // Helper to highlight search matches in text
      const highlightSearchMatches = (text) => {
        if (!searchQuery) return text;

        const regex = new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
      };

      while (i < markup.length) {
        // Check for entity markup {text|id|type}
        if (markup[i] === '{') {
          const closeIndex = markup.indexOf('}', i);
          if (closeIndex !== -1) {
            const content = markup.substring(i + 1, closeIndex);
            const parts = content.split('|');

            if (parts.length === 3) {
              const [text, id, type] = parts;
              // Only apply block-entity class if entity has a qid (Wikibase)
              const entity = this.entities[id];
              const hasQid = entity && entity.qid;
              const entityClass = hasQid ? 'block-entity' : 'block-entity-no-qid';

              // Get instance type QID for color coding (only for entities with QID)
              const typeLabel = entity?.type || '';
              const instanceOfQid = (hasQid && typeLabel) ? this.classMap[typeLabel] : null;
              const colorClass = instanceOfQid ? `entity-type-${instanceOfQid}` : '';

              const highlightedText = highlightSearchMatches(text);
              html += `<span class="${entityClass} ${colorClass}" data-id="${id}" data-type="${type}">${highlightedText}</span>`;
              i = closeIndex + 1;
              continue;
            }
          }
        }

        // Check for newline
        if (markup[i] === '\n') {
          html += '<br class="block-newline">';
          i++;
          continue;
        }

        // Regular text - accumulate words (including spaces)
        let word = '';
        while (i < markup.length && markup[i] !== '{' && markup[i] !== '\n') {
          word += markup[i];
          i++;
        }

        // Split accumulated text into words (preserving spaces)
        if (word) {
          const words = word.match(/\S+\s*/g) || [];
          words.forEach(w => {
            const highlightedWord = highlightSearchMatches(w);
            html += `<span class="block-word">${highlightedWord}</span>`;
          });
        }
      }

      return html;
    },

    // Split markup into parts around the reconciling entity
    splitMarkupForReconcile(markup, entityId, occurrence) {
      if (!entityId || !markup) return { before: markup, after: '' };

      const entityPattern = new RegExp(`\\{([^|]+)\\|${entityId}\\|([^}]+)\\}`, 'gi');
      let matches = [];
      let match;

      // Find all matches
      while ((match = entityPattern.exec(markup)) !== null) {
        matches.push({
          index: match.index,
          length: match[0].length,
          fullMatch: match[0]
        });
      }

      if (matches.length === 0) return { before: markup, after: '' };

      // Get the specific occurrence
      const targetMatch = matches[occurrence] || matches[0];
      const matchIndex = targetMatch.index;
      const matchLength = targetMatch.length;

      return {
        before: markup.substring(0, matchIndex + matchLength),
        after: markup.substring(matchIndex + matchLength)
      };
    },

    // Convert HTML back to custom markup
    htmlToMarkup(html) {
      // Create temporary element to parse HTML
      const temp = document.createElement('div');
      temp.innerHTML = html;

      let markup = '';

      const processNode = (node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          return node.textContent;
        }

        if (node.nodeType === Node.ELEMENT_NODE) {
          if (node.classList.contains('block-entity') || node.classList.contains('block-entity-no-qid')) {
            const text = node.textContent;
            const id = node.getAttribute('data-id');
            const type = node.getAttribute('data-type');
            return `{${text}|${id}|${type}}`;
          } else if (node.classList.contains('block-newline') || node.tagName === 'BR') {
            return '\n';
          } else if (node.classList.contains('block-word')) {
            return node.textContent;
          }
        }

        // Process children
        let result = '';
        node.childNodes.forEach(child => {
          result += processNode(child);
        });
        return result;
      };

      return processNode(temp);
    },

    // Custom search functionality
    openSearch() {
      this.searchActive = true;
      this.$nextTick(() => {
        this.$refs.searchInput?.focus();
      });
    },

    closeSearch() {
      this.searchActive = false;
      this.searchQuery = '';
      this.searchResults = [];
      this.currentSearchIndex = 0;
    },

    performSearch() {
      if (!this.searchQuery.trim()) {
        this.searchResults = [];
        return;
      }

      const query = this.searchQuery.toLowerCase();
      this.searchResults = [];

      this.blockIds.forEach((blockId, index) => {
        const block = this.blocks[blockId];
        const text = block.clean || block.markup || '';

        if (text.toLowerCase().includes(query)) {
          this.searchResults.push({
            blockId,
            blockIndex: index,
            text: text.substring(0, 100) // preview
          });
        }
      });

      this.currentSearchIndex = 0;
      if (this.searchResults.length > 0) {
        this.scrollToSearchResult(0);
      }
    },

    nextSearchResult() {
      if (this.searchResults.length === 0) return;
      this.currentSearchIndex = (this.currentSearchIndex + 1) % this.searchResults.length;
      this.scrollToSearchResult(this.currentSearchIndex);
    },

    prevSearchResult() {
      if (this.searchResults.length === 0) return;
      this.currentSearchIndex = (this.currentSearchIndex - 1 + this.searchResults.length) % this.searchResults.length;
      this.scrollToSearchResult(this.currentSearchIndex);
    },

    scrollToSearchResult(index) {
      const result = this.searchResults[index];
      if (!result) return;

      // Scroll to the block element
      const blockElement = document.querySelector(`[data-block-id="${result.blockId}"]`);
      if (blockElement) {
        blockElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },

    startAutoRelationships() {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined) return;

      console.log('\n=== AUTO RELATIONSHIP PROMPT ===\n');

      // Get all entities in the focused block
      const block = this.blocks[this.focusedBlockId];
      const markup = block.markup || '';
      const entityIds = new Set();

      const regex = /\{([^|]+)\|([^|]+)\|([^}]+)\}/g;
      let match;
      while ((match = regex.exec(markup)) !== null) {
        entityIds.add(match[2]);
      }

      const blockEntities = Array.from(entityIds)
        .map(id => this.entities[id])
        .filter(e => e && e.entity && e.qid);

      if (blockEntities.length === 0) {
        console.log('No entities with QIDs found in this block');
        return;
      }

      console.log('DEBUG: Found entities:', blockEntities.length);
      console.log('DEBUG: All entity structures:');
      blockEntities.forEach((entity, i) => {
        console.log(`  Entity ${i} (${entity.entity}):`, {
          type: entity.type,
          qid: entity.qid,
          wikiQid: entity.wikiQid,
          mintAddInstanceOf: entity.mintAddInstanceOf,
          mintData: entity.mintData,
          instanceOf: entity.instanceOf
        });
      });

      // Build prompt
      let prompt = `You are a helpful tool converting relationships described in unstructured text into triple statements. You will be given a block of text and some metadata about the entities in that text and the possible relationships that may be described in it. You should look at the text and build relationships only for the entities listed and using the relationships listed. You should build your relationships as JSON objects in this format

{
  "subjectQid": "Q1234",
  "subjectLabel": "Q1234's Label",
  "propertyQid": "P1234",
  "propertyLabel": "xxxxxx",
  "objectQid": "Q4321",
  "objectLabel": "Q4321's Label",
  "source": "a small section of the text that this relationship is based on"
}

Only use the text given to build these relationships.

Entities in Block:

`;

      // Collect instance types from entity.type via classMap
      const instanceTypes = new Set();
      const instanceTypeToInfo = {};

      console.log('DEBUG: classMap:', this.classMap);
      console.log('DEBUG: classMap keys:', Object.keys(this.classMap));

      blockEntities.forEach(entity => {
        const authLabel = entity.labelSemlab || entity.entity;
        const description = entity.descriptionSemlab || '';
        const typeLabel = entity.type || '';
        const entityQid = entity.qid || '';

        console.log(`DEBUG: Entity "${authLabel}" has type: "${typeLabel}"`);

        // Map type string to QID using classMap
        // classMap format: {"person": "Q1", "city": "Q19058", ...}
        let instanceOfQid = null;
        if (typeLabel) {
          // Direct lookup - type string to QID
          instanceOfQid = this.classMap[typeLabel];
          if (instanceOfQid) {
            console.log(`  -> Matched "${typeLabel}" to ${instanceOfQid}`);
          } else {
            console.log(`  -> NO MATCH in classMap for "${typeLabel}"`);
          }
        }

        if (instanceOfQid) {
          instanceTypes.add(instanceOfQid);
          if (!instanceTypeToInfo[instanceOfQid]) {
            instanceTypeToInfo[instanceOfQid] = {
              typeLabel: typeLabel,
              entities: []
            };
          }
          instanceTypeToInfo[instanceOfQid].entities.push(authLabel);
        }

        prompt += `${authLabel}`;
        if (entityQid) {
          prompt += ` (${entityQid})`;
        }
        if (typeLabel) {
          prompt += ` [${typeLabel}]`;
        }
        if (description) {
          prompt += ` - ${description}`;
        }
        prompt += '\n';
      });

      prompt += '\n';

      console.log('DEBUG: Instance types found:', Array.from(instanceTypes));
      console.log('DEBUG: Instance type map:', instanceTypeToInfo);
      console.log('DEBUG: propertiesBySubject keys sample:', Object.keys(this.propertiesBySubject).slice(0, 10));

      // Build possible relationships based on instance types
      const instanceTypesArray = Array.from(instanceTypes);

      if (instanceTypesArray.length > 0) {
        prompt += 'Possible Relationships:\n\n';

        instanceTypesArray.forEach(subjectTypeQid => {
          const typeInfo = instanceTypeToInfo[subjectTypeQid];
          const typeLabel = typeInfo.typeLabel;

          // Get properties where this instance type appears as subject
          const subjectProperties = this.propertiesBySubject[subjectTypeQid] || [];

          console.log(`DEBUG: Properties for ${subjectTypeQid} (${typeLabel}):`, subjectProperties.length);

          if (subjectProperties.length === 0) {
            prompt += `For ${typeLabel} (${subjectTypeQid}):\n`;
            prompt += `  No properties found in dataset\n\n`;
            return;
          }

          // Filter to only show properties where the object type is also present in the block
          const relevantProperties = subjectProperties.filter(prop => {
            // Exclude properties in the exclusion list
            if (this.excludedProperties.includes(prop.pid)) {
              return false;
            }

            for (const objTypeQid of instanceTypesArray) {
              if (objTypeQid !== subjectTypeQid) {
                const pairKey = `${subjectTypeQid}|${objTypeQid}`;
                if (this.propertiesByPair[pairKey]) {
                  const pairProps = this.propertiesByPair[pairKey];
                  if (pairProps.some(p => p.pid === prop.pid)) {
                    return true;
                  }
                }
              }
            }
            return false;
          });

          console.log(`DEBUG: Relevant properties after filtering:`, relevantProperties.length);

          // If no relevant properties found after filtering, show top properties anyway (but still exclude)
          const propsToShow = relevantProperties.length > 0
            ? relevantProperties
            : subjectProperties.filter(prop => !this.excludedProperties.includes(prop.pid));

          prompt += `For ${typeLabel}:\n`;
          propsToShow.slice(0, 10).forEach(prop => {
            prompt += `  ${prop.pid} ${prop.label}\n`;
          });
          prompt += '\n';
        });
      } else {
        prompt += 'Possible Relationships:\n\n';
        prompt += 'No instance types found (entities missing type field or not in classMap)\n';
      }

      // Add the block text at the end (plain text without markup)
      // Convert markup {entity|id|type} to just entity text
      const blockText = (block.markup || '').replace(/\{([^|]+)\|[^|]+\|[^}]+\}/g, '$1');
      prompt += '\n------ TEXT START --------\n';
      prompt += blockText;
      prompt += '\n------ TEXT END --------\n';

      console.log(prompt);
      console.log('\n=== END PROMPT ===\n');

      // Send to backend
      this.extractRelationships(prompt);
    },

    async extractRelationships(prompt) {
      this.isExtractingRelationships = true;
      try {
        const response = await asyncEmit('extract_relationships', {
          prompt: prompt,
          blockId: this.focusedBlockId
        });

        console.log('=== RELATIONSHIPS RESPONSE ===');
        console.log(response);

        // Handle response format with success flag and response array
        const relationships = response?.response || response;

        if (relationships && Array.isArray(relationships)) {
          if (relationships.length === 0) {
            // No relationships found
            this.lastExtractionFoundNone = true;
            setTimeout(() => {
              this.lastExtractionFoundNone = false;
            }, 3000);
            console.log('No relationships found');
          } else {
            this.lastExtractionFoundNone = false;

            // Initialize block's triples array if it doesn't exist
            if (!this.tripleStatements[this.focusedBlockId]) {
              this.tripleStatements[this.focusedBlockId] = [];
            }

            // Add relationships to triples for this block
            relationships.forEach(rel => {
              const tripleId = `triple_${Date.now()}_${Math.random()}`;
              this.tripleStatements[this.focusedBlockId].push({
                id: tripleId,
                source: 'auto', // Mark as auto-generated
                active: false, // Auto triples inactive by default
                subjectQid: rel.subjectQid,
                subjectLabel: rel.subjectLabel,
                propertyQid: rel.propertyQid,
                propertyLabel: rel.propertyLabel,
                objectQid: rel.objectQid,
                objectLabel: rel.objectLabel,
                sourceText: rel.source
              });
            });

            console.log(`Added ${relationships.length} triples to block ${this.focusedBlockId}`);
          }
        }
      } catch (error) {
        console.error('Failed to extract relationships:', error);
      } finally {
        this.isExtractingRelationships = false;
      }
    },

    updateSearchHighlights() {
      // Update which search results are currently visible
      // This would be used to highlight the current match
    },

    // Advanced Triple Generation Modal Methods
    loadAdvancedTripleSettings() {
      try {
        const stored = localStorage.getItem('advancedTripleSettings');
        if (stored) {
          const settings = JSON.parse(stored);
          this.selectedProperties = settings.selectedProperties || [];
          this.useReconciledOnly = settings.useReconciledOnly !== undefined ? settings.useReconciledOnly : true;
          this.customPromptText = settings.customPromptText || '';
        }
      } catch (error) {
        console.error('Error loading advanced triple settings:', error);
      }
    },

    saveAdvancedTripleSettings() {
      try {
        const settings = {
          selectedProperties: this.selectedProperties,
          useReconciledOnly: this.useReconciledOnly,
          customPromptText: this.customPromptText
        };
        localStorage.setItem('advancedTripleSettings', JSON.stringify(settings));
      } catch (error) {
        console.error('Error saving advanced triple settings:', error);
      }
    },

    async openAdvancedTripleModal(blockId) {
      this.advancedTripleBlockId = blockId;
      this.showAdvancedTripleModal = true;
      this.propertySearchFilter = '';

      await this.fetchAvailableProperties();

      // Load settings after properties are fetched
      this.loadAdvancedTripleSettings();
    },

    async openAdvancedTripleModalForBatch() {
      this.advancedTripleBlockId = 'batch';
      this.showAdvancedTripleModal = true;
      this.propertySearchFilter = '';

      await this.fetchAvailableProperties();
      this.loadAdvancedTripleSettings();
    },

    closeAdvancedTripleModal() {
      this.showAdvancedTripleModal = false;
      this.advancedTripleBlockId = null;
      this.availableProperties = [];
      this.selectedProperties = [];
    },

    async fetchAvailableProperties() {
      this.loadingProperties = true;
      try {
        const query = `SELECT ?property ?propertyLabel ?propertyDescription ?selavyInstructions ?rangeLabel WHERE {
  ?property rdf:type wikibase:Property .
  optional{
    ?property wdt:P275 ?selavyInstructions.
  }
  optional{
    ?property wdt:P51 ?range.
  }
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
  }
}`;

        const url = `https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql?query=${encodeURIComponent(query)}`;
        const response = await fetch(url, {
          headers: {
            'Accept': 'application/sparql-results+json'
          }
        });

        const data = await response.json();

        // Process and deduplicate properties
        const propertyMap = new Map();

        data.results.bindings.forEach(binding => {
          const pid = binding.property.value.split('/').pop();
          const label = binding.propertyLabel?.value || '';
          const description = binding.propertyDescription?.value || '';
          const instructions = binding.selavyInstructions?.value || '';
          const range = binding.rangeLabel?.value || '';

          // Skip if instructions contain "do not use"
          if (instructions.toLowerCase().includes('do not use')) {
            return;
          }

          if (!propertyMap.has(pid)) {
            propertyMap.set(pid, {
              pid,
              label,
              description,
              instructions,
              ranges: range ? [range] : []
            });
          } else {
            // Add additional ranges
            const existing = propertyMap.get(pid);
            if (range && !existing.ranges.includes(range)) {
              existing.ranges.push(range);
            }
          }
        });

        this.availableProperties = Array.from(propertyMap.values()).sort((a, b) => {
          const aNum = parseInt(a.pid.substring(1));
          const bNum = parseInt(b.pid.substring(1));
          return aNum - bNum;
        });

      } catch (error) {
        console.error('Error fetching properties:', error);
      } finally {
        this.loadingProperties = false;
      }
    },

    toggleSelectAllProperties() {
      if (this.selectAllProperties) {
        this.selectedProperties = this.filteredProperties.map(p => p.pid);
      } else {
        this.selectedProperties = [];
      }
    },

    buildAdvancedTriplePrompt() {
      const block = this.blocks[this.advancedTripleBlockId];
      if (!block) return null;

      // Get entities for this block
      // Convert blockId to number for comparison since entity.blocks stores numbers
      const blockIdNum = Number(this.advancedTripleBlockId);
      const blockEntities = Object.values(this.entities).filter(entity => {
        if (!entity.blocks || !entity.blocks.includes(blockIdNum)) {
          return false;
        }
        // Filter by reconciled status if needed
        if (this.useReconciledOnly && !entity.qid) {
          return false;
        }
        return true;
      });

      // Build prompt
      let prompt = 'Extract relationship triples from the following text.\n\n';

      prompt += 'ENTITIES IN TEXT:\n\n';
      blockEntities.forEach(entity => {
        const type = entity.type || 'unknown';
        const qidDisplay = entity.qid || 'UNRECONCILED';
        prompt += `${entity.entity} (ID: ${entity.internal_id}, QID: ${qidDisplay}) - ${type}\n`;
      });

      prompt += '\n\nAVAILABLE PROPERTIES:\n\nNote: Look at the "How to use" notes and make sure to follow their instructions for each property if present\n\n';
      this.availableProperties
        .filter(prop => this.selectedProperties.includes(prop.pid))
        .forEach(prop => {
          prompt += `${prop.pid} - ${prop.label}`;
          if (prop.description) {
            prompt += ` - ${prop.description}`;
          }
          if (prop.ranges.length > 0) {
            prompt += ` (range: ${prop.ranges.join(', ')})`;
          }
          if (prop.instructions) {
            prompt += ` (How to use property: ${prop.instructions})`;
          }
          prompt += '\n';
        });

      if (this.customPromptText.trim()) {
        prompt += '\n\nADDITIONAL INSTRUCTIONS:\n';
        prompt += this.customPromptText.trim() + '\n';
      }

      prompt += '\n\nReturn the relationships in this exact JSON format:\n';
      prompt += '[\n';
      prompt += '  {\n';
      prompt += '    "subjectId": 123,\n';
      prompt += '    "subjectQid": "Q123",\n';
      prompt += '    "subjectLabel": "Subject Name",\n';
      prompt += '    "propertyQid": "P##",\n';
      prompt += '    "propertyLabel": "property label",\n';
      prompt += '    "objectId": 456,\n';
      prompt += '    "objectQid": "Q456",\n';
      prompt += '    "objectLabel": "Object Name",\n';
      prompt += '    "source": "relevant excerpt from text"\n';
      prompt += '  }\n';
      prompt += ']\n\n';
      prompt += 'Use the internal ID numbers from the entity list above for subjectId and objectId.\n\n';

      // Add block text
      const blockText = (block.markup || '').replace(/\{([^|]+)\|[^|]+\|[^}]+\}/g, '$1');
      prompt += '\n------ TEXT START --------\n';
      prompt += blockText;
      prompt += '\n------ TEXT END --------\n';

      return prompt;
    },

    async executeAdvancedTripleGeneration() {
      const prompt = this.buildAdvancedTriplePrompt();
      if (!prompt) {
        console.error('Failed to build prompt');
        return;
      }

      console.log('=== ADVANCED TRIPLE GENERATION PROMPT ===');
      console.log(prompt);

      this.isExtractingRelationships = true;

      try {
        const response = await asyncEmit('extract_relationships', {
          prompt: prompt,
          blockId: this.advancedTripleBlockId
        });

        console.log('=== ADVANCED RELATIONSHIPS RESPONSE ===');
        console.log(response);

        const relationships = response?.response || response;

        if (relationships && Array.isArray(relationships)) {
          if (relationships.length === 0) {
            this.lastExtractionFoundNone = true;
            setTimeout(() => {
              this.lastExtractionFoundNone = false;
            }, 3000);
            console.log('No relationships found');
          } else {
            this.lastExtractionFoundNone = false;

            if (!this.tripleStatements[this.advancedTripleBlockId]) {
              this.tripleStatements[this.advancedTripleBlockId] = [];
            }

            relationships.forEach(rel => {
              const tripleId = `triple_${Date.now()}_${Math.random()}`;

              // Convert "UNRECONCILED" to empty string for QIDs
              const subjectQid = (rel.subjectQid === 'UNRECONCILED' || !rel.subjectQid) ? '' : rel.subjectQid;
              const objectQid = (rel.objectQid === 'UNRECONCILED' || !rel.objectQid) ? '' : rel.objectQid;

              // Auto-generated triple is active only if it has property and both subject/object have QIDs
              const hasProperty = !!(rel.propertyQid);
              const hasSubjectQid = !!(subjectQid);
              const hasObjectQid = !!(objectQid);
              const isActive = hasProperty && hasSubjectQid && hasObjectQid;

              const triple = {
                id: tripleId,
                source: 'auto',
                active: isActive,
                subjectId: rel.subjectId,
                subjectQid: subjectQid,
                subjectLabel: rel.subjectLabel,
                propertyQid: rel.propertyQid,
                propertyLabel: rel.propertyLabel,
                objectId: rel.objectId,
                objectQid: objectQid,
                objectLabel: rel.objectLabel,
                sourceText: rel.source,
                contexts: [] // Array of context/qualifier statements
              };

              // Validate the triple pattern
              const validation = this.validateTriplePattern(triple);
              triple.validation = validation;

              if (!validation.valid) {
                console.warn(`⚠️  Suspicious triple: ${triple.subjectLabel} --[${triple.propertyQid}]--> ${triple.objectLabel}`);
                console.warn(`    Reason: ${validation.reason}`);
              } else if (validation.confidence < 0.5) {
                console.log(`⚠️  Low confidence triple: ${triple.subjectLabel} --[${triple.propertyQid}]--> ${triple.objectLabel}`);
                console.log(`    Confidence: ${validation.confidence}, Reason: ${validation.reason}`);
              }

              this.tripleStatements[this.advancedTripleBlockId].push(triple);
            });

            console.log(`Added ${relationships.length} triples to block ${this.advancedTripleBlockId}`);

            // Close modal on success
            this.closeAdvancedTripleModal();
          }
        }
      } catch (error) {
        console.error('Failed to extract relationships:', error);
      } finally {
        this.isExtractingRelationships = false;
      }
    },

    async startBatchAdvancedTripleGeneration() {
      // Check if we're in batch mode
      if (this.advancedTripleBlockId !== 'batch') {
        await this.executeAdvancedTripleGeneration();
        return;
      }

      // Save settings before closing modal (closeAdvancedTripleModal clears these arrays)
      const savedSelectedProperties = [...this.selectedProperties];
      const savedAvailableProperties = [...this.availableProperties];
      const savedUseReconciledOnly = this.useReconciledOnly;
      const savedCustomPromptText = this.customPromptText;

      // Close modal and start batch processing
      this.closeAdvancedTripleModal();

      // Restore settings for batch processing
      this.selectedProperties = savedSelectedProperties;
      this.availableProperties = savedAvailableProperties;
      this.useReconciledOnly = savedUseReconciledOnly;
      this.customPromptText = savedCustomPromptText;

      this.isBatchProcessing = true;
      this.batchProcessingStopped = false;
      this.batchCurrentBlockIndex = 0;
      this.batchTotalBlocks = this.blockIds.length;

      console.log(`Starting batch processing for ${this.batchTotalBlocks} blocks`);
      console.log('Batch settings:', {
        selectedProperties: this.selectedProperties.length,
        availableProperties: this.availableProperties.length,
        useReconciledOnly: this.useReconciledOnly
      });

      for (let i = 0; i < this.blockIds.length; i++) {
        if (this.batchProcessingStopped) {
          console.log('Batch processing stopped by user');
          break;
        }

        this.batchCurrentBlockIndex = i + 1;
        const blockId = this.blockIds[i];

        console.log(`Processing block ${this.batchCurrentBlockIndex}/${this.batchTotalBlocks}: ${blockId}`);

        // Generate triples for this block
        await this.executeBatchTripleForBlock(blockId);

        // Small delay between blocks to prevent overwhelming the system
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      // Clean up batch settings
      this.selectedProperties = [];
      this.availableProperties = [];
      this.isBatchProcessing = false;
      this.batchCurrentBlockIndex = 0;
      this.batchTotalBlocks = 0;
      console.log('Batch processing complete');
    },

    async executeBatchTripleForBlock(blockId) {
      const block = this.blocks[blockId];
      if (!block) return;

      console.log('=== BATCH DEBUG ===');
      console.log('blockId:', blockId, 'type:', typeof blockId);
      console.log('Total entities:', Object.keys(this.entities).length);
      console.log('useReconciledOnly:', this.useReconciledOnly);
      console.log('selectedProperties:', this.selectedProperties);
      console.log('availableProperties:', this.availableProperties.length);

      // Debug: check a few entities to see their blocks property
      const sampleEntities = Object.values(this.entities).slice(0, 5);
      console.log('Sample entities:', sampleEntities.map(e => ({
        entity: e.entity,
        blocks: e.blocks,
        blocksIncludes0: e.blocks ? e.blocks.includes(0) : 'no blocks',
        blocksIncludesStr0: e.blocks ? e.blocks.includes('0') : 'no blocks'
      })));

      // Get entities for this block
      // Convert blockId to number for comparison since entity.blocks stores numbers
      const blockIdNum = Number(blockId);
      const blockEntities = Object.values(this.entities).filter(entity => {
        if (!entity.blocks || !entity.blocks.includes(blockIdNum)) {
          return false;
        }
        if (this.useReconciledOnly && !entity.qid) {
          return false;
        }
        return true;
      });

      console.log('blockEntities found:', blockEntities.length);

      // Build prompt
      let prompt = 'Extract relationship triples from the following text.\n\n';

      prompt += 'ENTITIES IN TEXT:\n\n';
      blockEntities.forEach(entity => {
        const type = entity.type || 'unknown';
        const qidDisplay = entity.qid || 'UNRECONCILED';
        prompt += `${entity.entity} (ID: ${entity.internal_id}, QID: ${qidDisplay}) - ${type}\n`;
      });

      prompt += '\n\nAVAILABLE PROPERTIES:\n\nNote: Look at the "How to use" notes and make sure to follow their instructions for each property if present\n\n';
      this.availableProperties
        .filter(prop => this.selectedProperties.includes(prop.pid))
        .forEach(prop => {
          prompt += `${prop.pid} - ${prop.label}`;
          if (prop.description) {
            prompt += ` - ${prop.description}`;
          }
          if (prop.ranges.length > 0) {
            prompt += ` (range: ${prop.ranges.join(', ')})`;
          }
          if (prop.instructions) {
            prompt += ` (How to use property: ${prop.instructions})`;
          }
          prompt += '\n';
        });

      if (this.customPromptText.trim()) {
        prompt += '\n\nADDITIONAL INSTRUCTIONS:\n';
        prompt += this.customPromptText.trim() + '\n';
      }

      prompt += '\n\nReturn the relationships in this exact JSON format:\n';
      prompt += '[\n  {\n    "subjectId": 123,\n    "subjectQid": "Q123",\n    "subjectLabel": "Subject Name",\n    "propertyQid": "P##",\n    "propertyLabel": "property label",\n    "objectId": 456,\n    "objectQid": "Q456",\n    "objectLabel": "Object Name",\n    "source": "relevant excerpt from text"\n  }\n]\n\n';
      prompt += 'Use the internal ID numbers from the entity list above for subjectId and objectId.\n\n';

      const blockText = (block.markup || '').replace(/\{([^|]+)\|[^|]+\|[^}]+\}/g, '$1');
      prompt += '\n------ TEXT START --------\n';
      prompt += blockText;
      prompt += '\n------ TEXT END --------\n';

      console.log('=== BATCH MODE PROMPT ===');
      console.log(prompt);
      console.log('=== END PROMPT ===');

      // Execute
      try {
        const response = await asyncEmit('extract_relationships', {
          prompt: prompt,
          blockId: blockId
        });

        const relationships = response?.response || response;

        if (relationships && Array.isArray(relationships) && relationships.length > 0) {
          if (!this.tripleStatements[blockId]) {
            this.tripleStatements[blockId] = [];
          }

          relationships.forEach(rel => {
            const tripleId = `triple_${Date.now()}_${Math.random()}`;
            const subjectQid = (rel.subjectQid === 'UNRECONCILED' || !rel.subjectQid) ? '' : rel.subjectQid;
            const objectQid = (rel.objectQid === 'UNRECONCILED' || !rel.objectQid) ? '' : rel.objectQid;

            // Auto-generated triple is active only if it has property and both subject/object have QIDs
            const hasProperty = !!(rel.propertyQid);
            const hasSubjectQid = !!(subjectQid);
            const hasObjectQid = !!(objectQid);
            const isActive = hasProperty && hasSubjectQid && hasObjectQid;

            const triple = {
              id: tripleId,
              source: 'auto',
              active: isActive,
              subjectId: rel.subjectId,
              subjectQid: subjectQid,
              subjectLabel: rel.subjectLabel,
              propertyQid: rel.propertyQid,
              propertyLabel: rel.propertyLabel,
              objectId: rel.objectId,
              objectQid: objectQid,
              objectLabel: rel.objectLabel,
              sourceText: rel.source,
              contexts: [] // Array of context/qualifier statements
            };

            // Validate the triple pattern
            const validation = this.validateTriplePattern(triple);
            triple.validation = validation;

            if (!validation.valid) {
              console.warn(`⚠️  Suspicious triple: ${triple.subjectLabel} --[${triple.propertyQid}]--> ${triple.objectLabel}`);
              console.warn(`    Reason: ${validation.reason}`);
            } else if (validation.confidence < 0.5) {
              console.log(`⚠️  Low confidence triple: ${triple.subjectLabel} --[${triple.propertyQid}]--> ${triple.objectLabel}`);
              console.log(`    Confidence: ${validation.confidence}, Reason: ${validation.reason}`);
            }

            this.tripleStatements[blockId].push(triple);
          });

          console.log(`Added ${relationships.length} triples to block ${blockId}`);
        }
      } catch (error) {
        console.error(`Failed to extract relationships for block ${blockId}:`, error);
      }
    },

    stopBatchProcessing() {
      this.batchProcessingStopped = true;
    },

    // Save triples to backend
    async saveTriplesToBackend() {
      if (!this.documentId) {
        console.error('Cannot save triples: No document ID');
        return;
      }

      if (!this.user) {
        console.error('Cannot save triples: No user logged in');
        return;
      }

      // Package all triples with their block associations
      const payload = {
        documentId: this.documentId,
        user: this.user,
        blocks: []
      };

      // Iterate through all blocks that have triples
      Object.keys(this.tripleStatements).forEach(blockId => {
        const triples = this.tripleStatements[blockId];

        if (triples && triples.length > 0) {
          const blockTriples = triples.map(triple => ({
            // Triple identification
            id: triple.id,

            // Source and status
            source: triple.source, // 'auto' or 'manual'
            active: triple.active, // enabled/disabled state

            // Subject
            subjectId: triple.subjectId,
            subjectQid: triple.subjectQid || null,
            subjectLabel: triple.subjectLabel,
            blockSubject: triple.blockSubject !== null && triple.blockSubject !== undefined ? triple.blockSubject : null,

            // Property
            propertyQid: triple.propertyQid || null,
            propertyLabel: triple.propertyLabel || '',

            // Object
            objectId: triple.objectId,
            objectQid: triple.objectQid || null,
            objectLabel: triple.objectLabel,
            objectLiteral: triple.objectLiteral !== null && triple.objectLiteral !== undefined ? triple.objectLiteral : null,

            // Additional metadata
            sourceText: triple.sourceText || '',

            // Validation info (if exists)
            validation: triple.validation ? {
              valid: triple.validation.valid,
              confidence: triple.validation.confidence,
              reason: triple.validation.reason
            } : null,

            // Context/Qualifier statements
            contexts: triple.contexts || []
          }));

          payload.blocks.push({
            blockId: Number(blockId), // Ensure blockId is a number
            triples: blockTriples
          });
        }
      });

      console.log('=== SAVING TRIPLES TO BACKEND ===');
      console.log('Payload:', JSON.stringify(payload, null, 2));
      console.log('Summary:', {
        user: payload.user,
        documentId: payload.documentId,
        totalBlocks: payload.blocks.length,
        totalTriples: payload.blocks.reduce((sum, block) => sum + block.triples.length, 0),
        blockBreakdown: payload.blocks.map(b => ({ blockId: b.blockId, count: b.triples.length }))
      });

      // Emit to backend
      try {
        socket.emit('save_triples', payload, (response) => {
          if (response && response.error) {
            console.error('❌ Failed to save triples:', response.error);
          } else {
            console.log('✅ Triples saved successfully', response);
          }
        });
      } catch (error) {
        console.error('❌ Error emitting save_triples:', error);
      }
    },

    // Load triples from backend
    async loadTriplesFromBackend() {
      if (!this.documentId) {
        console.error('Cannot load triples: No document ID');
        return;
      }

      if (!this.user) {
        console.warn('Cannot load triples: No user logged in');
        return;
      }

      console.log('=== LOADING TRIPLES FROM BACKEND ===');
      console.log('Document ID:', this.documentId);
      console.log('User:', this.user);

      // Set flag to prevent watcher from triggering saves during load
      this.isLoadingTriples = true;

      try {
        const response = await asyncEmit('get_triples', {
          documentId: this.documentId,
          user: this.user
        });

        console.log('Response from get_triples:', response);

        if (response && response.error) {
          console.error('❌ Failed to load triples:', response.error);
          return;
        }

        if (response && response.success && response.triples) {
          // Clear existing triples
          this.tripleStatements = {};

          // Server sends triples as: { "blockId": [...triples], "blockId2": [...triples] }
          let totalTriples = 0;
          const blockBreakdown = [];

          Object.keys(response.triples).forEach(blockId => {
            const triples = response.triples[blockId];

            if (triples && Array.isArray(triples)) {
              this.tripleStatements[blockId] = triples.map(triple => ({
                // Restore all triple properties
                id: triple.id,
                source: triple.source,
                active: triple.active,
                subjectId: triple.subjectId,
                subjectQid: triple.subjectQid || '',
                subjectLabel: triple.subjectLabel,
                blockSubject: triple.blockSubject !== null && triple.blockSubject !== undefined ? triple.blockSubject : null,
                propertyQid: triple.propertyQid || '',
                propertyLabel: triple.propertyLabel || '',
                objectId: triple.objectId,
                objectQid: triple.objectQid || '',
                objectLabel: triple.objectLabel,
                objectLiteral: triple.objectLiteral !== null && triple.objectLiteral !== undefined ? triple.objectLiteral : null,
                sourceText: triple.sourceText || '',
                validation: triple.validation || null,
                contexts: triple.contexts || [] // Restore contexts/qualifiers
              }));

              totalTriples += triples.length;
              blockBreakdown.push({ blockId, count: triples.length });
            }
          });

          console.log('✅ Triples loaded successfully');
          console.log('Summary:', {
            totalBlocks: Object.keys(response.triples).length,
            totalTriples: totalTriples,
            blockBreakdown: blockBreakdown
          });
        } else {
          console.log('No triples found for this document');
        }
      } catch (error) {
        console.error('❌ Error loading triples:', error);
      } finally {
        // Reset the flag after loading is complete
        this.isLoadingTriples = false;
      }
    },

    focusBlock(blockId) {
      if (this.focusedBlockId !== blockId) {
        this.focusedBlockId = blockId;
        this.showAllEntities = false; // Reset when focusing a new block
      }
      // If already focused, do nothing (keep focus)
    },

    toggleShowAllEntities() {
      this.showAllEntities = !this.showAllEntities;
    },

    onEntityMouseDown(event, entityId, entityData, blockId) {
      event.preventDefault();
      event.stopPropagation();

      // Focus the block if not already focused (without interrupting the drag)
      if (this.focusedBlockId !== blockId) {
        this.focusedBlockId = blockId;
        this.showAllEntities = false;
      }

      this.isDragging = false; // Don't set to true until actual movement
      this.dragStartEntity = { id: entityId, ...entityData };
      this.dragStartElement = event.target;

      // Add glow class directly to the clicked element
      event.target.classList.add('dragging-origin');

      const rect = event.target.getBoundingClientRect();
      this.dragLineX = rect.left + rect.width / 2;
      this.dragLineY = rect.top + rect.height / 2;

      document.addEventListener('mousemove', this.onMouseMove);
      document.addEventListener('mouseup', this.onMouseUp);
      document.addEventListener('wheel', this.onDragScroll, { passive: true });
    },

    onDragScroll() {
      // Update drag line origin when scrolling during drag
      if (this.dragStartElement && (this.isDragging || this.dragStartEntity)) {
        const rect = this.dragStartElement.getBoundingClientRect();
        this.dragLineX = rect.left + rect.width / 2;
        this.dragLineY = rect.top + rect.height / 2;
      }
    },

    onMouseMove(event) {
      // Set dragging to true only when mouse actually moves
      if (!this.isDragging && this.dragStartEntity) {
        this.isDragging = true;
        console.log('Started dragging');
      }

      if (!this.isDragging) return;

      this.dragLine = {
        x1: this.dragLineX,
        y1: this.dragLineY,
        x2: event.clientX,
        y2: event.clientY
      };

      // Check if hovering over an entity (regular or convenience) and add target glow
      const hoveredElement = document.elementFromPoint(event.clientX, event.clientY);
      const isEntity = hoveredElement && (
        hoveredElement.classList.contains('block-entity') ||
        hoveredElement.classList.contains('block-entity-no-qid') ||
        hoveredElement.classList.contains('convenience-entity')
      );

      if (isEntity) {
        // Remove glow from previous hover element
        if (this.dragHoverElement && this.dragHoverElement !== hoveredElement) {
          this.dragHoverElement.classList.remove('dragging-target');
        }
        // Add glow to current hover element (if different from drag start)
        if (hoveredElement !== this.dragStartElement) {
          hoveredElement.classList.add('dragging-target');
          this.dragHoverElement = hoveredElement;
        }
      } else {
        // Not hovering over an entity, remove glow from previous hover
        if (this.dragHoverElement) {
          this.dragHoverElement.classList.remove('dragging-target');
          this.dragHoverElement = null;
        }
      }
    },

    onMouseUp(event) {
      console.log('Mouse up - isDragging:', this.isDragging);

      // Clean up event listeners regardless
      document.removeEventListener('mousemove', this.onMouseMove);
      document.removeEventListener('mouseup', this.onMouseUp);
      document.removeEventListener('wheel', this.onDragScroll);

      // Remove glow class from drag start element
      if (this.dragStartElement) {
        this.dragStartElement.classList.remove('dragging-origin');
      }

      // Remove glow class from hover target element
      if (this.dragHoverElement) {
        this.dragHoverElement.classList.remove('dragging-target');
        this.dragHoverElement = null;
      }

      // Only create triple if actually dragging occurred
      if (!this.isDragging) {
        console.log('Not dragging, skipping triple creation');
        // Reset state
        this.dragStartEntity = null;
        return;
      }

      console.log('Creating triple...');

      // Find the element under the cursor
      const targetElement = document.elementFromPoint(event.clientX, event.clientY);

      if (targetElement && (targetElement.classList.contains('block-entity') ||
                            targetElement.classList.contains('block-entity-no-qid') ||
                            targetElement.classList.contains('convenience-entity') ||
                            targetElement.classList.contains('block-word'))) {

        let releaseText = targetElement.textContent;
        let releaseEntityId = null;
        let releaseEntityData = null;
        let releaseIsConvenience = false;

        // Check if it's a convenience entity
        if (targetElement.classList.contains('convenience-entity')) {
          const qid = targetElement.getAttribute('data-qid');
          const label = targetElement.getAttribute('data-label');
          releaseEntityId = `convenience_${qid}`;
          releaseEntityData = { qid, entity: label, isConvenience: true };
          releaseText = label;
          releaseIsConvenience = true;
        }
        // Check if it's a regular entity
        else if (targetElement.classList.contains('block-entity') || targetElement.classList.contains('block-entity-no-qid')) {
          releaseEntityId = targetElement.getAttribute('data-id');
          releaseEntityData = this.entities[releaseEntityId];

          // Use entity label if available
          if (releaseEntityData && releaseEntityData.labelSemlab) {
            releaseText = releaseEntityData.labelSemlab;
          } else if (releaseEntityData && releaseEntityData.entity) {
            releaseText = releaseEntityData.entity;
          }
        }

        // Check if trying to connect entity to itself
        if (releaseEntityId && this.dragStartEntity.id === releaseEntityId) {
          console.log('Cannot create triple: subject and object are the same entity');
          this.isDragging = false;
          this.dragStartEntity = null;
          this.dragLine = null;
          return;
        }

        // Create triple statement (manual)
        // Triple starts inactive - will be activated when property is set and both entities have QIDs
        this.addTripleStatement({
          source: 'manual', // Mark as manually created
          active: false, // Starts inactive until property is set
          subjectId: this.dragStartEntity.isConvenience ? null : this.dragStartEntity.internal_id,
          subjectQid: this.dragStartEntity.qid || '',
          subjectLabel: this.dragStartEntity.labelSemlab || this.dragStartEntity.entity,
          subjectIsConvenience: this.dragStartEntity.isConvenience || false,
          propertyQid: '', // Empty, will be filled by user
          propertyLabel: '',
          objectId: releaseIsConvenience ? null : releaseEntityId,
          objectQid: releaseEntityData?.qid || '',
          objectLabel: releaseText,
          objectIsConvenience: releaseIsConvenience,
          objectLiteral: null, // Will be set if property is literal type
          sourceText: '', // No source text for manual triples
          contexts: [], // Array of context/qualifier statements
          // Keep old format for compatibility during editing
          subject: this.dragStartEntity,
          object: {
            text: releaseText,
            entityId: releaseEntityId,
            entityData: releaseEntityData,
            isEntity: !!releaseEntityId,
            hasQid: releaseEntityData && releaseEntityData.qid
          }
        });

        // Fade out the line
        setTimeout(() => {
          this.dragLine = null;
        }, 1000);
      } else {
        // No valid target, just remove the line
        this.dragLine = null;
      }

      this.isDragging = false;
      this.dragStartEntity = null;
    },

    addTripleStatement(triple) {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined) return;

      if (!this.tripleStatements[this.focusedBlockId]) {
        this.tripleStatements[this.focusedBlockId] = [];
      }

      this.tripleStatements[this.focusedBlockId].push({
        ...triple,
        id: Date.now() + Math.random() // Unique ID
      });
    },

    deleteTriple(tripleId) {
      if (this.focusedBlockId === null || this.focusedBlockId === undefined) return;

      const blockTriples = this.tripleStatements[this.focusedBlockId];
      if (!blockTriples) return;

      const index = blockTriples.findIndex(t => t.id === tripleId);
      if (index !== -1) {
        blockTriples.splice(index, 1);
      }

      // Clean up property search state for this triple
      delete this.propertySearchQuery[tripleId];
      delete this.propertySearchResults[tripleId];
      delete this.propertySearchActive[tripleId];
      delete this.propertySearchSelectedIndex[tripleId];
    },

    onPropertyInput(triple, event) {
      const query = event.target.value;
      triple.propertyLabel = query;

      // Hide recent properties when user starts typing
      this.showRecentProperties[triple.id] = false;

      if (!query || query.trim() === '') {
        this.propertySearchActive[triple.id] = false;
        this.propertySearchResults[triple.id] = [];
        // Show recent properties again if input is cleared
        this.showRecentProperties[triple.id] = true;
        return;
      }

      // Filter properties by PID or label
      const lowerQuery = query.toLowerCase();
      const results = this.allProperties.filter(prop => {
        const pidMatch = prop.pid.toLowerCase().includes(lowerQuery);
        const labelMatch = prop.label.toLowerCase().includes(lowerQuery);
        return pidMatch || labelMatch;
      }).slice(0, 10); // Limit to 10 results

      this.propertySearchResults[triple.id] = results;
      this.propertySearchActive[triple.id] = results.length > 0;
      this.propertySearchSelectedIndex[triple.id] = -1;
    },

    onPropertyKeydown(triple, event) {
      const results = this.propertySearchResults[triple.id] || [];
      if (!this.propertySearchActive[triple.id] || results.length === 0) return;

      let currentIndex = this.propertySearchSelectedIndex[triple.id];
      if (currentIndex === null || currentIndex === undefined) {
        currentIndex = -1;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        currentIndex = Math.min(currentIndex + 1, results.length - 1);
        this.propertySearchSelectedIndex[triple.id] = currentIndex;
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        currentIndex = Math.max(currentIndex - 1, -1);
        this.propertySearchSelectedIndex[triple.id] = currentIndex;
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (currentIndex >= 0 && results[currentIndex]) {
          this.selectProperty(triple, results[currentIndex]);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        this.cancelPropertyEdit(triple);
      }
    },

    selectProperty(triple, property) {
      // Check if trying to convert literal triple to entity triple
      const isLiteralType = ['monolingualtext', 'string', 'time', 'quantity', 'url', 'globe-coordinate', 'external-id'].includes(property.type);
      const isQidType = property.type === 'wikibase-item' || property.type === 'wikibase-property';

      if (triple.objectLiteral !== null && triple.objectLiteral !== undefined && isQidType) {
        alert('You are trying to convert a literal triple into an entity triple, please delete the triple and add it again');
        return;
      }

      triple.propertyLabel = property.label;
      triple.propertyQid = property.pid;
      this.propertySearchActive[triple.id] = false;
      this.propertySearchResults[triple.id] = [];
      this.propertySearchSelectedIndex[triple.id] = -1;
      // Clear original values after successful selection
      delete this.originalPropertyValues[triple.id];

      // Add to recent triple properties
      this.addToRecentTripleProperties(property);
      // Hide recent properties popup
      this.showRecentProperties[triple.id] = false;

      // If this is a literal-type property and this is a manual triple, convert object to literal
      if (isLiteralType && triple.source === 'manual') {
        // Convert object to literal value
        triple.objectLiteral = triple.objectLabel || '';

        // Clear object entity data to avoid confusion
        triple.objectQid = '';
        triple.objectId = null;

        console.log('🔄 Converted object to literal:', triple.objectLiteral);
      } else if (isQidType && triple.objectLiteral) {
        // This case is already handled above with the alert, but just in case
        triple.objectLiteral = null;
      }

      // Auto-activate triple based on type
      // For block-subject triples: just need property + object
      // For entity-subject triples: need subject QID + property + object
      const hasValidSubject = triple.subjectQid || (triple.blockSubject !== null && triple.blockSubject !== undefined);

      if (triple.propertyQid && hasValidSubject) {
        if (isLiteralType && triple.objectLiteral && triple.objectLiteral.trim() !== '') {
          // Literal triple: needs valid subject + non-empty literal
          triple.active = true;
          console.log('✅ Literal triple auto-activated:', {
            subject: triple.subjectLabel,
            blockSubject: triple.blockSubject,
            property: triple.propertyLabel,
            objectLiteral: triple.objectLiteral
          });
        } else if (isQidType && triple.objectQid) {
          // Entity triple: needs valid subject + object QID
          triple.active = true;
          console.log('✅ Entity triple auto-activated:', {
            subject: triple.subjectLabel,
            blockSubject: triple.blockSubject,
            property: triple.propertyLabel,
            object: triple.objectLabel
          });
        }
      }
    },

    clearProperty(triple) {
      // Save original values before clearing
      this.originalPropertyValues[triple.id] = {
        label: triple.propertyLabel,
        qid: triple.propertyQid
      };

      triple.propertyLabel = '';
      triple.propertyQid = '';

      // Deactivate triple when property is cleared
      triple.active = false;

      this.$nextTick(() => {
        const inputRef = this.$refs[`propertyInput_${triple.id}`];
        const inputEl = Array.isArray(inputRef) ? inputRef[0] : inputRef;
        if (inputEl) {
          inputEl.focus();
        }
      });
    },

    cancelPropertyEdit(triple) {
      // Restore original values if they exist
      if (this.originalPropertyValues[triple.id]) {
        triple.propertyLabel = this.originalPropertyValues[triple.id].label;
        triple.propertyQid = this.originalPropertyValues[triple.id].qid;
        delete this.originalPropertyValues[triple.id];
      }
      this.propertySearchActive[triple.id] = false;
      this.propertySearchResults[triple.id] = [];
      this.propertySearchSelectedIndex[triple.id] = -1;
    },

    onPropertyFocus(triple, event) {
      // Show recent properties if available and input is empty
      if (!triple.propertyLabel || triple.propertyLabel.trim() === '') {
        this.showRecentProperties[triple.id] = true;
      }

      // Re-trigger search if there's existing text
      if (triple.propertyLabel && triple.propertyLabel.trim() !== '') {
        const syntheticEvent = { target: { value: triple.propertyLabel } };
        this.onPropertyInput(triple, syntheticEvent);
      }
    },

    onPropertyBlur(triple) {
      // Delay to allow click on dropdown
      setTimeout(() => {
        // If still empty and no selection made, restore original value
        if (!triple.propertyQid && this.originalPropertyValues[triple.id]) {
          this.cancelPropertyEdit(triple);
        } else {
          this.propertySearchActive[triple.id] = false;
        }
        // Hide recent properties
        this.showRecentProperties[triple.id] = false;
      }, 200);
    },

    getDropdownPosition(tripleId) {
      const inputRef = this.$refs[`propertyInput_${tripleId}`];
      if (!inputRef) return {};

      // Handle both single element and array refs
      const inputEl = Array.isArray(inputRef) ? inputRef[0] : inputRef;
      if (!inputEl) return {};

      const rect = inputEl.getBoundingClientRect();
      return {
        position: 'fixed',
        top: `${rect.bottom + 2}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`
      };
    },

    getRecentPropertiesPosition(tripleId) {
      const inputRef = this.$refs[`propertyInput_${tripleId}`];
      if (!inputRef) return {};

      // Handle both single element and array refs
      const inputEl = Array.isArray(inputRef) ? inputRef[0] : inputRef;
      if (!inputEl) return {};

      const rect = inputEl.getBoundingClientRect();
      return {
        position: 'fixed',
        bottom: `${window.innerHeight - rect.top + 5}px`,
        left: `${rect.left}px`,
        minWidth: '300px'
      };
    },

    // Context/Qualifier Methods
    onContextPropertyInput(triple, event) {
      const query = event.target.value;
      console.log('Context property input:', query, 'for triple:', triple.id);
      this.contextPropertySearchQuery[triple.id] = query;

      // Hide recent properties when user starts typing
      this.showRecentQualifierProperties[triple.id] = false;

      if (!query || query.trim() === '') {
        this.contextPropertySearchActive[triple.id] = false;
        this.contextPropertySearchResults[triple.id] = [];
        // Show recent properties again if input is cleared
        this.showRecentQualifierProperties[triple.id] = true;
        return;
      }

      // Filter properties by PID or label
      const lowerQuery = query.toLowerCase();
      const results = this.allProperties.filter(prop => {
        const pidMatch = prop.pid.toLowerCase().includes(lowerQuery);
        const labelMatch = prop.label.toLowerCase().includes(lowerQuery);
        return pidMatch || labelMatch;
      }).slice(0, 10); // Limit to 10 results

      console.log('Context property results:', results.length, 'matches');
      this.contextPropertySearchResults[triple.id] = results;
      this.contextPropertySearchActive[triple.id] = results.length > 0;
      this.contextPropertySearchSelectedIndex[triple.id] = -1;
    },

    onContextPropertyFocus(triple, event) {
      // Show recent qualifier properties if available and input is empty
      if (!this.contextPropertySearchQuery[triple.id] || this.contextPropertySearchQuery[triple.id].trim() === '') {
        this.showRecentQualifierProperties[triple.id] = true;
      }

      // Re-trigger search if there's existing text
      if (this.contextPropertySearchQuery[triple.id] && this.contextPropertySearchQuery[triple.id].trim() !== '') {
        const syntheticEvent = { target: { value: this.contextPropertySearchQuery[triple.id] } };
        this.onContextPropertyInput(triple, syntheticEvent);
      }
    },

    onContextPropertyKeydown(triple, event) {
      const results = this.contextPropertySearchResults[triple.id] || [];
      if (!this.contextPropertySearchActive[triple.id] || results.length === 0) {
        // Handle ESC to cancel cursor mode
        if (event.key === 'Escape' && this.contextCursorMode) {
          this.contextCursorMode = null;
          document.body.classList.remove('context-selecting-mode');
          event.preventDefault();
        }
        return;
      }

      let currentIndex = this.contextPropertySearchSelectedIndex[triple.id];
      if (currentIndex === null || currentIndex === undefined) {
        currentIndex = -1;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        currentIndex = Math.min(currentIndex + 1, results.length - 1);
        this.contextPropertySearchSelectedIndex[triple.id] = currentIndex;
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        currentIndex = Math.max(currentIndex - 1, -1);
        this.contextPropertySearchSelectedIndex[triple.id] = currentIndex;
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (currentIndex >= 0 && results[currentIndex]) {
          this.selectContextProperty(triple, results[currentIndex]);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        this.contextPropertySearchActive[triple.id] = false;
        this.contextPropertySearchResults[triple.id] = [];
        this.contextPropertySearchQuery[triple.id] = '';
      }
    },

    onContextPropertyBlur(triple) {
      // Delay to allow click on dropdown
      setTimeout(() => {
        this.contextPropertySearchActive[triple.id] = false;
        this.contextPropertySearchQuery[triple.id] = '';
        // Hide recent properties
        this.showRecentQualifierProperties[triple.id] = false;
      }, 200);
    },

    selectContextProperty(triple, property) {
      console.log('selectContextProperty called', triple.id, property);

      // Clear the search
      this.contextPropertySearchActive[triple.id] = false;
      this.contextPropertySearchResults[triple.id] = [];
      this.contextPropertySearchQuery[triple.id] = '';

      // Add to recent qualifier properties
      this.addToRecentQualifierProperties(property);
      // Hide recent properties popup
      this.showRecentQualifierProperties[triple.id] = false;

      // Enter cursor mode
      this.contextCursorMode = {
        tripleId: triple.id,
        propertyQid: property.pid,
        propertyLabel: property.label,
        propertyType: property.type
      };

      // Add class to change cursor
      document.body.classList.add('context-selecting-mode');

      console.log('👆 Entered context cursor mode:', this.contextCursorMode);
      console.log('Click on text in any block to add qualifier value');
      console.log('Body classes:', document.body.className);
    },

    // Block-subject triple selection
    startBlockSubjectSelection(blockId) {
      console.log('🟦 Starting block-subject selection for block:', blockId);

      this.blockSubjectSelectionMode = {
        blockId: blockId,
        blockLabel: `Block ${blockId}`
      };

      // Add cursor class
      document.body.classList.add('context-selecting-mode');

      console.log('👆 Click on text or entity in the block to create triple with block as subject');
    },

    handleBlockSubjectSelection(entityId, text) {
      if (!this.blockSubjectSelectionMode) return;

      const { blockId, blockLabel } = this.blockSubjectSelectionMode;

      console.log('🟦 Creating block-subject triple:', {
        blockId,
        blockLabel,
        objectEntityId: entityId,
        objectText: text
      });

      // Focus the block first to ensure addTripleStatement works
      if (this.focusedBlockId !== blockId) {
        console.log('🟦 Focusing block:', blockId);
        this.focusedBlockId = blockId;
        this.showAllEntities = false;
      }

      // Determine if object is entity or literal
      const entity = entityId ? this.entities[entityId] : null;

      console.log('🟦 Entity data:', entity);
      console.log('🟦 Entity QID:', entity?.qid);
      console.log('🟦 Text:', text);

      // Create the triple
      this.addTripleStatement({
        source: 'manual',
        active: false, // Will be activated when property is set

        // Subject is the block
        blockSubject: blockId,
        subjectId: null,
        subjectQid: null,
        subjectLabel: blockLabel,

        // Property (empty, to be filled)
        propertyQid: '',
        propertyLabel: '',

        // Object (entity or literal)
        objectId: entityId || null,
        objectQid: entity?.qid || '',
        objectLabel: text || (entity?.labelSemlab || entity?.entity) || '',
        objectLiteral: null,

        sourceText: '',
        contexts: []
      });

      console.log('🟦 Triple created with objectQid:', entity?.qid || '');

      // Exit selection mode
      this.blockSubjectSelectionMode = null;
      document.body.classList.remove('context-selecting-mode');

      console.log('✅ Block-subject triple created');
    },

    getContextDropdownPosition(tripleId) {
      const inputRef = this.$refs[`contextPropertyInput_${tripleId}`];
      if (!inputRef) return {};

      const inputEl = Array.isArray(inputRef) ? inputRef[0] : inputRef;
      if (!inputEl) return {};

      const rect = inputEl.getBoundingClientRect();
      return {
        position: 'fixed',
        top: `${rect.bottom + 2}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`
      };
    },

    deleteContext(triple, contextIndex) {
      if (!triple.contexts) return;
      triple.contexts.splice(contextIndex, 1);
    },

    handleContextValueSelection(event, entityId) {
      if (!this.contextCursorMode) return;

      const { tripleId, propertyQid, propertyLabel, propertyType } = this.contextCursorMode;

      // Find the triple
      const triple = this.currentBlockTriples.find(t => t.id === tripleId);
      if (!triple) {
        console.error('Triple not found');
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
        return;
      }

      // Get the entity data
      const entity = this.entities[entityId];
      if (!entity) {
        console.error('Entity not found');
        return;
      }

      console.log('🔍 Context selection - Entity:', entityId, entity);
      console.log('🔍 Property type:', propertyType);
      console.log('🔍 Entity QID:', entity.qid);

      // Determine if this is a QID-based or literal value
      const isQidType = propertyType === 'wikibase-item' || propertyType === 'wikibase-property';
      const isLiteralType = ['monolingualtext', 'string', 'time', 'quantity', 'url', 'globe-coordinate', 'external-id'].includes(propertyType);

      if (!triple.contexts) {
        triple.contexts = [];
      }

      if (isQidType && entity.qid) {
        // Add QID-based context
        triple.contexts.push({
          propertyQid,
          propertyLabel,
          propertyType,
          valueQid: entity.qid,
          valueLabel: entity.labelSemlab || entity.entity,
          valueLiteral: null
        });
        console.log('✅ Added QID context:', propertyLabel, '→', entity.labelSemlab || entity.entity, entity.qid);

        // Exit cursor mode after successful addition
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
      } else if (isLiteralType) {
        // Add literal context with the text that was clicked
        let clickedText = event && event.target ? event.target.textContent : (entity.labelSemlab || entity.entity);
        // Remove terminal punctuation
        clickedText = clickedText.replace(/[.,;:!?]+$/, '').trim();
        triple.contexts.push({
          propertyQid,
          propertyLabel,
          propertyType,
          valueQid: null,
          valueLabel: null,
          valueLiteral: clickedText
        });
        console.log('✅ Added literal context:', propertyLabel, '→', clickedText);

        // Exit cursor mode after successful addition
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
      } else if (isQidType && !entity.qid) {
        console.warn('⚠️  This property requires a QID. The entity you clicked is not reconciled yet.');

        // Show error message in the UI
        this.contextErrorMessage = 'This property requires a QID. Please click on a reconciled entity (highlighted text with QID).';

        // Clear error message after 2 seconds
        setTimeout(() => {
          this.contextErrorMessage = null;
        }, 2000);

        // Don't exit cursor mode - let them try again
      } else {
        console.warn('⚠️  Cannot add context: property type mismatch');

        // Show error message in the UI
        this.contextErrorMessage = 'Property type mismatch. Please select the correct type of value.';

        // Clear error message after 2 seconds
        setTimeout(() => {
          this.contextErrorMessage = null;
        }, 2000);

        // Don't exit cursor mode - let them try again
      }
    },

    handleContextTextSelection(text, event) {
      if (!this.contextCursorMode) return;

      const { tripleId, propertyQid, propertyLabel, propertyType } = this.contextCursorMode;

      // Find the triple
      const triple = this.currentBlockTriples.find(t => t.id === tripleId);
      if (!triple) {
        console.error('Triple not found');
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
        return;
      }

      if (!triple.contexts) {
        triple.contexts = [];
      }

      // Check if this is a literal type property
      const isLiteralType = ['monolingualtext', 'string', 'time', 'quantity', 'url', 'globe-coordinate', 'external-id'].includes(propertyType);
      const isQidType = propertyType === 'wikibase-item' || propertyType === 'wikibase-property';

      if (isLiteralType) {
        // Add literal context - remove terminal punctuation
        const cleanedText = text.replace(/[.,;:!?]+$/, '').trim();
        triple.contexts.push({
          propertyQid,
          propertyLabel,
          propertyType,
          valueQid: null,
          valueLabel: null,
          valueLiteral: cleanedText
        });
        console.log('✅ Added literal context:', propertyLabel, '→', cleanedText);

        // Exit cursor mode
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
      } else if (isQidType) {
        console.warn('⚠️  This property requires a QID. Please click on a recognized entity (highlighted text).');

        // Show error message in the UI
        this.contextErrorMessage = 'This property requires a QID. Please click on a reconciled entity (highlighted text with QID).';

        // Clear error message after 2 seconds
        setTimeout(() => {
          this.contextErrorMessage = null;
        }, 2000);

        // Don't exit cursor mode - let them try again
      }
    },

    onTripleEntityClick(triple, entityType, event) {
      const qid = entityType === 'subject' ? triple.subjectQid : triple.objectQid;

      // Don't open reconcile if already has QID
      if (qid) return;

      // Get entity ID directly from triple
      const entityId = entityType === 'subject' ? triple.subjectId : triple.objectId;

      if (!entityId) {
        // No entity ID - show entification tooltip to let user create an entity
        const label = entityType === 'subject' ? triple.subjectLabel : triple.objectLabel;
        const blockId = triple.blockId || this.focusedBlockId;

        console.log('No entity ID in triple - showing entification tooltip for:', label);

        // Get click position for tooltip
        const rect = event?.target?.getBoundingClientRect();
        const x = rect ? rect.left : 100;
        const y = rect ? rect.bottom + window.scrollY + 5 : 100;

        // Set up tooltip
        this.selectionTooltip = {
          show: true,
          x: x,
          y: y,
          selectedText: label,
          selectedClass: this.recentClasses[0] || Object.keys(this.classMap)[0] || '',
          blockId: blockId,
          selectionStart: 0,
          selectionEnd: 0,
          hasEntityOverlap: false
        };

        // Store pending triple info for after entification
        this.pendingTripleEntification = {
          triple: triple,
          entityType: entityType
        };

        return;
      }

      // Check if entity exists and doesn't have QID
      const entity = this.entities[entityId];
      if (!entity) {
        console.warn('Entity not found for ID:', entityId);
        return;
      }

      if (entity.qid) return;

      // Open reconciliation for this entity
      this.onEntityClick(null, entityId, this.focusedBlockId);

      // Scroll to the reconcile interface after it opens
      this.$nextTick(() => {
        const reconcileInterface = document.querySelector('.reconcile-interface');
        if (reconcileInterface) {
          reconcileInterface.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    },

    startEditingBlock(blockId, markup) {
      this.editingBlockId = blockId;
      this.editingMarkup = markup || '';
    },

    cancelBlockEdit() {
      this.editingBlockId = null;
      this.editingMarkup = '';
    },

    async saveBlockEdit(blockId) {
      console.log('=== SAVE BLOCK EDIT ===');
      console.log('Block ID:', blockId);
      console.log('Editing markup:', this.editingMarkup);

      // Update local block data
      if (this.blocks[blockId]) {
        this.blocks[blockId].markup = this.editingMarkup;
        console.log('Updated block markup');
      } else {
        console.error('Block not found:', blockId);
        return;
      }

      // Compile all blocks into a single text string with block breaks
      const fullText = this.blockIds
        .map(id => {
          const block = this.blocks[id];
          // Keep the markup format with entities
          return block.markup || '';
        })
        .join('<BLOCKBREAK/>');

      console.log('Compiled full text length:', fullText.length);
      console.log('Full text preview:', fullText.substring(0, 200));

      // Send to backend
      try {
        console.log('Sending update to backend...');
        const response = await asyncEmit('update_text_markup', {
          doc: this.documentId,
          job_id: this.documentId,
          text: fullText,
          user: this.user
        });
        console.log('Backend response:', response);
        console.log('Document text updated successfully');
      } catch (error) {
        console.error('Failed to update document text:', error);
      }

      // Exit edit mode
      console.log('Exiting edit mode');
      this.editingBlockId = null;
      this.editingMarkup = '';
    },

    handleKeydown(event) {
      // Handle ESC to exit context cursor mode
      if (event.key === 'Escape' && this.contextCursorMode) {
        event.preventDefault();
        this.contextCursorMode = null;
        document.body.classList.remove('context-selecting-mode');
        console.log('🚫 Exited context cursor mode (ESC pressed)');
        return;
      }

      // Handle ESC to exit block-subject selection mode
      if (event.key === 'Escape' && this.blockSubjectSelectionMode) {
        event.preventDefault();
        this.blockSubjectSelectionMode = null;
        document.body.classList.remove('context-selecting-mode');
        console.log('🚫 Exited block-subject selection mode (ESC pressed)');
        return;
      }

      // Handle reconcile dropdown navigation
      if (this.reconcilingEntityId && this.reconcileSearchResults.length > 0) {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          this.reconcileSelectedIndex = Math.min(
            this.reconcileSelectedIndex + 1,
            this.reconcileSearchResults.length - 1
          );
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          this.reconcileSelectedIndex = Math.max(this.reconcileSelectedIndex - 1, -1);
          return;
        }
        if (event.key === 'Enter' && this.reconcileSelectedIndex >= 0) {
          event.preventDefault();
          this.selectReconcileResult(this.reconcileSearchResults[this.reconcileSelectedIndex]);
          return;
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          this.closeReconcile();
          return;
        }
      }

      // Override Ctrl+F / Cmd+F
      if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
        event.preventDefault();
        this.openSearch();
      }

      // Escape to close search
      if (event.key === 'Escape' && this.searchActive) {
        this.closeSearch();
      }

      // Enter to go to next result
      if (event.key === 'Enter' && this.searchActive) {
        event.preventDefault();
        if (event.shiftKey) {
          this.prevSearchResult();
        } else {
          this.nextSearchResult();
        }
      }
    },

    onEntityClick(event, entityId, blockId) {
      // Check if we're in context cursor mode
      if (this.contextCursorMode) {
        console.log('🎯 Entity clicked in cursor mode:', entityId);
        this.handleContextValueSelection(event, entityId);
        return;
      }

      // Check if we're in block-subject selection mode
      if (this.blockSubjectSelectionMode) {
        const entity = this.entities[entityId];
        const text = entity?.labelSemlab || entity?.entity || '';
        console.log('🟦 Entity clicked in block-subject mode:', entityId, text);
        this.handleBlockSubjectSelection(entityId, text);
        return;
      }

      console.log('=== ENTITY CLICK ===');
      console.log('Entity ID:', entityId);
      console.log('Block ID:', blockId);

      const entity = this.entities[entityId];
      console.log('Entity:', entity);
      console.log('Has QID?', entity?.qid);

      // Only open reconcile for entities without QID
      if (!entity || entity.qid) {
        console.log('Skipping reconcile - no entity or already has QID');
        return;
      }

      // Focus the block first if not already focused
      if (this.focusedBlockId !== blockId) {
        console.log('Focusing block:', blockId);
        this.focusedBlockId = blockId;
        this.showAllEntities = false;
      }

      // Store the clicked element for positioning
      if (event && event.target) {
        this.reconcilingEntityElement = event.target;

        // Find which occurrence of this entity was clicked
        const blockElement = event.target.closest('[data-block-id]');
        if (blockElement) {
          const allEntityElements = blockElement.querySelectorAll(`[data-id="${entityId}"]`);
          let occurrence = 0;
          for (let i = 0; i < allEntityElements.length; i++) {
            if (allEntityElements[i] === event.target) {
              occurrence = i;
              break;
            }
          }
          this.reconcilingEntityOccurrence = occurrence;
          console.log('Clicked occurrence:', occurrence, 'of', allEntityElements.length);
        }
      }

      // Show reconciliation interface for this specific block
      console.log('Setting reconciling state...');
      this.reconcilingEntityId = entityId;
      this.reconcilingBlockId = blockId;
      console.log('reconcilingEntityId:', this.reconcilingEntityId);
      console.log('reconcilingBlockId:', this.reconcilingBlockId);

      this.reconcileSearchQuery = entity.entity || '';
      this.wikidataSearchQuery = entity.entity || '';

      // Set default project to last used project
      this.wikidataImportProject = this.lastUsedProject;

      // Find project label for lastUsedProject
      const lastProject = this.lastUsedProject ? this.projects.find(p => p.id === this.lastUsedProject) : null;

      // Find instance label for entity type
      const instanceQid = entity.type ? this.classMap[entity.type] : null;

      this.mintData = {
        authLabel: entity.entity || '',
        description: '',
        variantLabel: [],
        project: lastProject ? [{ qid: lastProject.id, label: lastProject.label }] : [],
        instanceOf: instanceQid ? [{ qid: instanceQid, label: entity.type }] : []
      };
      this.mintValidationError = '';

      // Trigger initial searches and focus input
      this.$nextTick(() => {
        this.searchReconcile(this.reconcileSearchQuery);
        this.searchWikidata(this.wikidataSearchQuery);
        const inputEl = this.$refs.reconcileSearchInput;
        if (inputEl && typeof inputEl.focus === 'function') {
          inputEl.focus();
        }
      });
    },

    searchReconcile(query) {
      if (this.reconcileSearchTimer) {
        clearTimeout(this.reconcileSearchTimer);
      }

      if (!query || query.trim() === '') {
        this.reconcileSearchResults = [];
        this.reconcileSearchLoading = false;
        return;
      }

      this.reconcileSearchLoading = true;
      this.reconcileSearchTimer = setTimeout(() => {
        socket.emit('search_semlab_autocomplete', query, (response) => {
          console.log('Reconcile search response:', response);
          try {
            if (response.success && response.data && response.data.search) {
              this.reconcileSearchResults = response.data.search.map(item => ({
                id: item.id,
                label: item.label || item.id,
                description: item.description || ''
              }));
              this.reconcileSelectedIndex = -1;
            } else {
              this.reconcileSearchResults = [];
              this.reconcileSelectedIndex = -1;
            }
          } catch (error) {
            console.error('Error processing reconcile search:', error);
            this.reconcileSearchResults = [];
            this.reconcileSelectedIndex = -1;
          } finally {
            this.reconcileSearchLoading = false;
          }
        });
      }, 300);
    },

    selectReconcileResult(result) {
      const entity = this.entities[this.reconcilingEntityId];
      if (entity) {
        entity.qid = result.id;
        entity.labelSemlab = result.label;
        entity.descriptionSemlab = result.description;

        // Save entity changes
        this.saveEntity(entity);

        // Update any triples that reference this entity as subject or object
        if (this.tripleStatements) {
          console.log('🔍 Checking triples for entity ID:', this.reconcilingEntityId);
          Object.values(this.tripleStatements).forEach(blockTriples => {
            if (Array.isArray(blockTriples)) {
              blockTriples.forEach(triple => {
                console.log('  Triple:', triple.subjectLabel, '→', triple.objectLabel,
                  'subjectId:', triple.subjectId, 'objectId:', triple.objectId);
                let updated = false;
                if (triple.subjectId === this.reconcilingEntityId) {
                  triple.subjectQid = result.id;
                  updated = true;
                  console.log('  ✅ Updated subjectQid to:', result.id);
                }
                if (triple.objectId === this.reconcilingEntityId) {
                  triple.objectQid = result.id;
                  updated = true;
                  console.log('  ✅ Updated objectQid to:', result.id);
                }

                // Auto-activate triple if it now has all requirements
                if (updated && !triple.active && triple.propertyQid) {
                  const hasValidSubject = triple.subjectQid || (triple.blockSubject !== null && triple.blockSubject !== undefined);
                  const hasValidObject = triple.objectQid || (triple.objectLiteral && triple.objectLiteral.trim() !== '');

                  if (hasValidSubject && hasValidObject) {
                    triple.active = true;
                    console.log('✅ Triple auto-activated after reconciliation:', triple.subjectLabel, '→', triple.objectLabel);
                  }
                }
              });
            }
          });
        }
      }

      this.closeReconcile();
    },

    closeReconcile() {
      this.reconcilingEntityId = null;
      this.reconcilingBlockId = null;
      this.reconcilingEntityElement = null;
      this.reconcilingEntityOccurrence = 0;
      this.reconcileSearchQuery = '';
      this.reconcileSearchResults = [];
      this.reconcileSelectedIndex = -1;
      this.wikidataSearchQuery = '';
      this.wikidataSearchResults = [];
      this.wikidataSelectedIndex = -1;
      this.wikidataImportProject = null;
      if (this.reconcileSearchTimer) {
        clearTimeout(this.reconcileSearchTimer);
      }
      if (this.wikidataSearchTimer) {
        clearTimeout(this.wikidataSearchTimer);
      }
    },

    async searchWikidata(query) {
      if (this.wikidataSearchTimer) {
        clearTimeout(this.wikidataSearchTimer);
      }

      if (!query || query.trim() === '') {
        this.wikidataSearchResults = [];
        this.wikidataSearchLoading = false;
        return;
      }

      this.wikidataSearchLoading = true;
      this.wikidataSearchTimer = setTimeout(async () => {
        try {
          const searchUrl = `https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&limit=10&language=en&uselang=en&type=item&origin=*&search=${encodeURIComponent(query)}`;
          const response = await fetch(searchUrl);
          const data = await response.json();

          if (data.search) {
            this.wikidataSearchResults = data.search.map(item => ({
              id: item.id,
              label: item.label || item.id,
              description: item.description || ''
            }));
            this.wikidataSelectedIndex = -1;
          } else {
            this.wikidataSearchResults = [];
            this.wikidataSelectedIndex = -1;
          }
        } catch (error) {
          console.error('Error searching Wikidata:', error);
          this.wikidataSearchResults = [];
          this.wikidataSelectedIndex = -1;
        } finally {
          this.wikidataSearchLoading = false;
        }
      }, 300);
    },

    async importFromWikidata(wikidataItem) {
      const entity = this.entities[this.reconcilingEntityId];
      if (!entity) return;

      // Validate project is selected
      if (!this.wikidataImportProject) {
        alert('Please select a project before importing from Wikidata');
        return;
      }

      try {
        // Save the project selection for next time
        this.saveLastUsedProject(this.wikidataImportProject);

        // Mint entity from Wikidata
        const response = await asyncEmit('wikibase_mint_entity', {
          entity: {
            internal_id: this.reconcilingEntityId,
            entity: entity.entity,
            wikiQid: wikidataItem.id,
            wikiLabel: wikidataItem.label,
            wikiDescription: wikidataItem.description,
            mintData: {
              authLabel: wikidataItem.label,
              description: wikidataItem.description,
              variantLabel: [],
              project: [this.wikidataImportProject],
              instanceOf: entity.type ? [this.classMap[entity.type]] : [],
              wikidataQid: wikidataItem.id
            }
          },
          login_token: this.login_token
        });

        if (response && response.success) {
          // Update entity with new QID
          entity.qid = response.qid;
          entity.labelSemlab = wikidataItem.label;
          entity.descriptionSemlab = wikidataItem.description;
          entity.wikiQid = wikidataItem.id;

          // Save entity changes
          this.saveEntity(entity);

          // Update any triples that reference this entity as subject or object
          if (this.tripleStatements) {
            console.log('🔍 [Wikidata Import] Checking triples for entity ID:', this.reconcilingEntityId);
            Object.values(this.tripleStatements).forEach(blockTriples => {
              if (Array.isArray(blockTriples)) {
                blockTriples.forEach(triple => {
                  let updated = false;
                  if (triple.subjectId === this.reconcilingEntityId) {
                    triple.subjectQid = response.qid;
                    updated = true;
                    console.log('  ✅ Updated subjectQid to:', response.qid);
                  }
                  if (triple.objectId === this.reconcilingEntityId) {
                    triple.objectQid = response.qid;
                    updated = true;
                    console.log('  ✅ Updated objectQid to:', response.qid);
                  }

                  // Auto-activate triple if it now has all requirements
                  if (updated && !triple.active && triple.propertyQid) {
                    const hasValidSubject = triple.subjectQid || (triple.blockSubject !== null && triple.blockSubject !== undefined);
                    const hasValidObject = triple.objectQid || (triple.objectLiteral && triple.objectLiteral.trim() !== '');

                    if (hasValidSubject && hasValidObject) {
                      triple.active = true;
                      console.log('✅ Triple auto-activated after Wikidata import:', triple.subjectLabel, '→', triple.objectLabel);
                    }
                  }
                });
              }
            });
          }

          this.closeReconcile();
        } else {
          console.error('Failed to import from Wikidata:', response?.error);
          alert('Failed to import from Wikidata: ' + (response?.error || 'Unknown error'));
        }
      } catch (error) {
        console.error('Import error:', error);
        alert('An error occurred during import');
      }
    },

    // Mint typeahead methods
    onMintProjectInput(event) {
      const query = event.target.value.toLowerCase();
      this.mintProjectQuery = event.target.value;

      if (!query || query.trim() === '') {
        this.mintProjectSearchActive = false;
        this.mintProjectResults = [];
        return;
      }

      // Filter projects by ID or label
      this.mintProjectResults = this.projects.filter(proj => {
        return proj.id.toLowerCase().includes(query) || proj.label.toLowerCase().includes(query);
      }).slice(0, 8);

      this.mintProjectSearchActive = this.mintProjectResults.length > 0;
      this.mintProjectSelectedIndex = -1;
    },

    onMintProjectKeydown(event) {
      if (!this.mintProjectSearchActive || this.mintProjectResults.length === 0) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        this.mintProjectSelectedIndex = Math.min(this.mintProjectSelectedIndex + 1, this.mintProjectResults.length - 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        this.mintProjectSelectedIndex = Math.max(this.mintProjectSelectedIndex - 1, -1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (this.mintProjectSelectedIndex >= 0 && this.mintProjectResults[this.mintProjectSelectedIndex]) {
          this.selectMintProject(this.mintProjectResults[this.mintProjectSelectedIndex]);
        }
      } else if (event.key === 'Escape') {
        this.mintProjectSearchActive = false;
        this.mintProjectSelectedIndex = -1;
      }
    },

    selectMintProject(project) {
      // Add project to mintData (avoid duplicates)
      if (!this.mintData.project.some(p => p.qid === project.id)) {
        this.mintData.project.push({ qid: project.id, label: project.label });
      }
      // Clear search
      this.mintProjectQuery = '';
      this.mintProjectSearchActive = false;
      this.mintProjectResults = [];
      this.mintProjectSelectedIndex = -1;
    },

    removeMintProject(index) {
      this.mintData.project.splice(index, 1);
    },

    onMintProjectBlur() {
      setTimeout(() => {
        this.mintProjectSearchActive = false;
        this.mintProjectSelectedIndex = -1;
      }, 200);
    },

    onMintInstanceInput(event) {
      const query = event.target.value.toLowerCase();
      this.mintInstanceQuery = event.target.value;

      if (!query || query.trim() === '') {
        this.mintInstanceSearchActive = false;
        this.mintInstanceResults = [];
        return;
      }

      // Filter classMap by class name or QID
      // classMap format: {'person': 'Q1', 'city': 'Q19058', ...}
      this.mintInstanceResults = Object.entries(this.classMap)
        .filter(([className, qid]) => {
          return className.toLowerCase().includes(query) || qid.toLowerCase().includes(query);
        })
        .map(([className, qid]) => ({ label: className, qid }))
        .slice(0, 8);

      this.mintInstanceSearchActive = this.mintInstanceResults.length > 0;
      this.mintInstanceSelectedIndex = -1;
    },

    onMintInstanceKeydown(event) {
      if (!this.mintInstanceSearchActive || this.mintInstanceResults.length === 0) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        this.mintInstanceSelectedIndex = Math.min(this.mintInstanceSelectedIndex + 1, this.mintInstanceResults.length - 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        this.mintInstanceSelectedIndex = Math.max(this.mintInstanceSelectedIndex - 1, -1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (this.mintInstanceSelectedIndex >= 0 && this.mintInstanceResults[this.mintInstanceSelectedIndex]) {
          this.selectMintInstance(this.mintInstanceResults[this.mintInstanceSelectedIndex]);
        }
      } else if (event.key === 'Escape') {
        this.mintInstanceSearchActive = false;
        this.mintInstanceSelectedIndex = -1;
      }
    },

    selectMintInstance(instance) {
      // Add instance to mintData (avoid duplicates)
      if (!this.mintData.instanceOf.some(i => i.qid === instance.qid)) {
        this.mintData.instanceOf.push({ qid: instance.qid, label: instance.label });
      }
      // Clear search
      this.mintInstanceQuery = '';
      this.mintInstanceSearchActive = false;
      this.mintInstanceResults = [];
      this.mintInstanceSelectedIndex = -1;
    },

    removeMintInstance(index) {
      this.mintData.instanceOf.splice(index, 1);
    },

    onMintInstanceBlur() {
      setTimeout(() => {
        this.mintInstanceSearchActive = false;
        this.mintInstanceSelectedIndex = -1;
      }, 200);
    },

    // Convenience Entity methods
    closeConvenienceEntityModal() {
      this.showConvenienceEntityModal = false;
      this.convenienceEntitySearchQuery = '';
      this.convenienceEntitySearchResults = [];
      this.convenienceEntitySelectedIndex = -1;
    },

    searchConvenienceEntity() {
      const query = this.convenienceEntitySearchQuery;

      if (!query || query.trim() === '') {
        this.convenienceEntitySearchResults = [];
        this.convenienceEntitySearchLoading = false;
        return;
      }

      this.convenienceEntitySearchLoading = true;
      this.convenienceEntitySelectedIndex = -1;

      // Search Wikibase (semlab)
      const searchUrl = `https://base.semlab.io/w/api.php?action=wbsearchentities&format=json&limit=10&language=en&uselang=en&type=item&origin=*&search=${encodeURIComponent(query)}`;

      fetch(searchUrl)
        .then(response => response.json())
        .then(data => {
          this.convenienceEntitySearchResults = data.search || [];
          this.convenienceEntitySearchLoading = false;
        })
        .catch(error => {
          console.error('Convenience entity search error:', error);
          this.convenienceEntitySearchResults = [];
          this.convenienceEntitySearchLoading = false;
        });
    },

    onConvenienceEntityKeydown(event) {
      if (this.convenienceEntitySearchResults.length === 0) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        this.convenienceEntitySelectedIndex = Math.min(
          this.convenienceEntitySelectedIndex + 1,
          this.convenienceEntitySearchResults.length - 1
        );
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        this.convenienceEntitySelectedIndex = Math.max(this.convenienceEntitySelectedIndex - 1, -1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (this.convenienceEntitySelectedIndex >= 0) {
          this.addConvenienceEntity(this.convenienceEntitySearchResults[this.convenienceEntitySelectedIndex]);
        }
      } else if (event.key === 'Escape') {
        this.closeConvenienceEntityModal();
      }
    },

    addConvenienceEntity(result) {
      // Check for duplicates
      if (this.convenienceEntities.some(e => e.qid === result.id)) {
        alert('This entity is already added as a convenience entity.');
        return;
      }

      this.convenienceEntities.push({
        qid: result.id,
        label: result.label
      });

      // Clear search
      this.convenienceEntitySearchQuery = '';
      this.convenienceEntitySearchResults = [];
      this.convenienceEntitySelectedIndex = -1;

      // Save to backend
      this.saveConvenienceEntities();

      // Focus input for next search
      this.$nextTick(() => {
        if (this.$refs.convenienceEntitySearchInput) {
          this.$refs.convenienceEntitySearchInput.focus();
        }
      });
    },

    removeConvenienceEntity(index) {
      this.convenienceEntities.splice(index, 1);
      this.saveConvenienceEntities();
    },

    saveConvenienceEntities() {
      console.log('Saving convenience entities:', {
        user: this.user,
        doc: this.documentId,
        convenience_entities: this.convenienceEntities
      });
      socket.emit('save_convenience_entities', {
        user: this.user,
        doc: this.documentId,
        convenience_entities: this.convenienceEntities
      }, (response) => {
        console.log('Save convenience entities response:', response);
        if (!response || !response.success) {
          console.error('Failed to save convenience entities:', response?.error);
        }
      });
    },

    loadConvenienceEntities() {
      console.log('Loading convenience entities via get_convenience_entities...');
      socket.emit('get_convenience_entities', {
        user: this.user,
        doc: this.documentId
      }, (response) => {
        console.log('Get convenience entities response:', response);
        if (response && response.success && response.convenience_entities) {
          this.convenienceEntities = response.convenience_entities;
          console.log('Loaded convenience entities:', this.convenienceEntities.length);
        }
      });
    },

    onConvenienceEntityMouseDown(event, convenienceEntity, blockId) {
      event.preventDefault();
      event.stopPropagation();

      // Focus the block if not already focused
      if (this.focusedBlockId !== blockId) {
        this.focusedBlockId = blockId;
        this.showAllEntities = false;
      }

      this.isDragging = false;
      // Create entity data structure similar to regular entities
      this.dragStartEntity = {
        id: `convenience_${convenienceEntity.qid}`,
        qid: convenienceEntity.qid,
        entity: convenienceEntity.label,
        isConvenience: true
      };
      this.dragStartElement = event.target;

      // Add glow class
      event.target.classList.add('dragging-origin');

      const rect = event.target.getBoundingClientRect();
      this.dragLineX = rect.left + rect.width / 2;
      this.dragLineY = rect.top + rect.height / 2;

      document.addEventListener('mousemove', this.onMouseMove);
      document.addEventListener('mouseup', this.onMouseUp);
      document.addEventListener('wheel', this.onDragScroll, { passive: true });
    },

    async mintEntity() {
      const entity = this.entities[this.reconcilingEntityId];
      if (!entity) return;

      // Validate
      const errors = [];
      if (!this.mintData.authLabel || this.mintData.authLabel.trim() === '') {
        errors.push('Auth Label is required');
      }
      if (!this.mintData.project || this.mintData.project.length === 0) {
        errors.push('At least one Project is required');
      }
      if (!this.mintData.instanceOf || this.mintData.instanceOf.length === 0) {
        errors.push('At least one Instance Of is required');
      }

      if (errors.length > 0) {
        this.mintValidationError = errors.join(', ');
        return;
      }

      this.mintValidationError = '';

      // Save the project selection for next time (use first project in array)
      if (this.mintData.project && this.mintData.project.length > 0) {
        this.saveLastUsedProject(this.mintData.project[0].qid);
      }

      try {
        // Prepare mintData for backend - extract just QIDs from objects
        const backendMintData = {
          authLabel: this.mintData.authLabel,
          description: this.mintData.description,
          variantLabel: this.mintData.variantLabel,
          project: this.mintData.project.map(p => p.qid),
          instanceOf: this.mintData.instanceOf.map(i => i.qid)
        };

        const response = await asyncEmit('wikibase_mint_entity', {
          entity: {
            internal_id: this.reconcilingEntityId,
            entity: entity.entity,
            mintData: backendMintData
          },
          login_token: this.login_token
        });

        if (response && response.success) {
          // Update entity with new QID
          entity.qid = response.qid;
          entity.labelSemlab = this.mintData.authLabel;
          entity.descriptionSemlab = this.mintData.description;

          // Save entity changes
          this.saveEntity(entity);
          this.closeReconcile();
        } else {
          this.mintValidationError = response?.error || 'Failed to mint entity';
        }
      } catch (error) {
        console.error('Mint error:', error);
        this.mintValidationError = 'An error occurred during minting';
      }
    },

    async saveEntity(entity) {
      try {
        // Update the entity in the entities object
        this.entities[entity.internal_id] = entity;

        // Update any triples that reference this entity
        this.updateTriplesForEntity(entity);

        // Save all entities back to server
        await this.sendFilteredEntities();

        console.log('Entity saved:', entity);
      } catch (error) {
        console.error('Failed to save entity:', error);
      }
    },

    updateTriplesForEntity(entity) {
      // Update all triples across all blocks that reference this entity by ID
      Object.keys(this.tripleStatements).forEach(blockId => {
        const triples = this.tripleStatements[blockId];
        if (!triples) return;

        triples.forEach(triple => {
          // Update subject if it matches this entity ID
          if (triple.subjectId === entity.internal_id) {
            triple.subjectQid = entity.qid || '';
            triple.subjectLabel = entity.entity;
          }
          // Update object if it matches this entity ID
          if (triple.objectId === entity.internal_id) {
            triple.objectQid = entity.qid || '';
            triple.objectLabel = entity.entity;
          }
          // Update active status - triple is active if both subject and object have QIDs
          if (triple.subjectQid && triple.objectQid && triple.propertyQid) {
            triple.active = true;
          }
        });
      });
    },

    async sendFilteredEntities() {
      // Filter entities to only include allowed keys (same as WorkNER)
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
        'wikiThumbnail',
        'todoMint',
        'minted',
        'mintAddAuthLabel',
        'mintAddDescription',
        'mintAddVariantLabel',
        'mintAddProject',
        'mintAddInstanceOf'
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
        const response = await asyncEmit('save_ner_entities', {
          user: this.user,
          job_id: this.documentId,
          entities: filteredEntities
        });

        if (response && response.success) {
          console.log('Entities saved successfully');
          return response;
        } else {
          console.error('Failed to save entities:', response?.error);
          return null;
        }
      } catch (error) {
        console.error('Error sending entities to backend:', error);
        return null;
      }
    },

    onTextSelection(event) {
      // Check if we're in context cursor mode - handle click on text for context
      if (this.contextCursorMode) {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        // If they clicked (no selection) or selected text, use it for context
        const textToUse = selectedText || event.target?.textContent?.trim() || '';

        if (textToUse) {
          this.handleContextTextSelection(textToUse, event);
        }
        return;
      }

      // Check if we're in block-subject selection mode
      if (this.blockSubjectSelectionMode) {
        // Check if clicking on an entity element - if so, let the entity click handler deal with it
        if (event.target?.classList.contains('block-entity') ||
            event.target?.classList.contains('block-entity-no-qid')) {
          console.log('🟦 Clicked on entity in block-subject mode, skipping text selection handler');
          return;
        }

        const selection = window.getSelection();
        const selectedText = selection.toString().trim();
        const textToUse = selectedText || event.target?.textContent?.trim() || '';

        if (textToUse) {
          console.log('🟦 Text selected in block-subject mode:', textToUse);
          this.handleBlockSubjectSelection(null, textToUse);
        }
        return;
      }

      // Don't process selections while we're creating an entity
      if (this.isProcessingEntification) {
        console.log('Skipping text selection - still processing entification');
        return;
      }

      const selection = window.getSelection();
      const selectedText = selection.toString().trim();
      console.log('onTextSelection called, selectedText:', selectedText);

      // Hide tooltip if no text selected
      if (!selectedText) {
        this.selectionTooltip.show = false;
        return;
      }

      // Check if selection is within a block-content element
      const anchorNode = selection.anchorNode;
      const blockContent = anchorNode?.parentElement?.closest('.block-content');
      if (!blockContent) {
        this.selectionTooltip.show = false;
        return;
      }

      // Get block ID
      const blockElement = blockContent.closest('[data-block-id]');
      if (!blockElement) {
        this.selectionTooltip.show = false;
        return;
      }
      const blockId = parseInt(blockElement.getAttribute('data-block-id'));

      // Check if selection overlaps with existing entity
      const range = selection.getRangeAt(0);
      const hasEntityOverlap = this.checkEntityOverlap(range);

      // Get selection position for tooltip with smart positioning
      const rect = range.getBoundingClientRect();
      const tooltipWidth = 300; // Approximate tooltip width
      const tooltipHeight = 80; // Approximate tooltip height

      let x = rect.left + rect.width / 2;
      let y = rect.top - 10;

      // Keep tooltip within viewport horizontally
      if (x - tooltipWidth / 2 < 10) {
        x = tooltipWidth / 2 + 10;
      } else if (x + tooltipWidth / 2 > window.innerWidth - 10) {
        x = window.innerWidth - tooltipWidth / 2 - 10;
      }

      // If tooltip would go above viewport, show below selection instead
      if (y - tooltipHeight < 10) {
        y = rect.bottom + 10 + tooltipHeight; // Position below and account for transform
      }

      // Show tooltip - update properties to maintain reactivity
      this.selectionTooltip.show = true;
      this.selectionTooltip.x = x;
      this.selectionTooltip.y = y;
      this.selectionTooltip.selectedText = selectedText;
      this.selectionTooltip.selectedClass = Object.keys(this.classMap)[0] || '';
      this.selectionTooltip.blockId = blockId;
      this.selectionTooltip.selectionStart = 0;
      this.selectionTooltip.selectionEnd = 0;
      this.selectionTooltip.hasEntityOverlap = hasEntityOverlap;
    },

    checkEntityOverlap(range) {
      // Check if the selection range contains any entity elements
      const container = range.commonAncestorContainer;
      const parentElement = container.nodeType === Node.TEXT_NODE ? container.parentElement : container;

      // Check if we're inside an entity
      if (parentElement.classList?.contains('block-entity') ||
          parentElement.classList?.contains('block-entity-no-qid')) {
        return true;
      }

      // Check if selection contains any entity elements
      const fragment = range.cloneContents();
      const entities = fragment.querySelectorAll('.block-entity, .block-entity-no-qid');
      return entities.length > 0;
    },

    async entifySelectedText() {
      if (!this.selectionTooltip.show || this.selectionTooltip.hasEntityOverlap) {
        return;
      }

      // Set processing flag to prevent onTextSelection from interfering
      console.log('[ENTIFY START] Setting isProcessingEntification = true');
      this.isProcessingEntification = true;

      try {
        // Capture values before hiding tooltip
        const blockId = this.selectionTooltip.blockId;
        const selectedText = this.selectionTooltip.selectedText;
        const selectedClass = this.selectionTooltip.selectedClass;

        console.log('[ENTIFY] Entifying text:', selectedText, 'with class:', selectedClass);
        console.log('[ENTIFY] isProcessingEntification =', this.isProcessingEntification);

        // Hide tooltip and clear selection immediately
        this.selectionTooltip.show = false;
        window.getSelection().removeAllRanges();

        const block = this.blocks[blockId];
        if (!block) {
          return;
        }

      // Find the next available entity ID
      const existingIds = Object.keys(this.entities).map(id => parseInt(id));
      const maxId = existingIds.length > 0 ? Math.max(...existingIds) : 0;
      const newEntityId = maxId + 1;

      // Find and replace the text in the markup
      const markup = block.markup;
      const textToFind = selectedText;

      // Make sure we're not replacing text that's already inside an entity
      const entityPattern = /\{[^}]+\}/g;
      let safeMarkup = markup;
      let replacementMade = false;

      // Find first occurrence of the text that's NOT inside an entity
      let searchIndex = 0;
      while (searchIndex < safeMarkup.length) {
        const textIndex = safeMarkup.indexOf(textToFind, searchIndex);
        if (textIndex === -1) break;

        // Check if this occurrence is inside an entity markup
        let insideEntity = false;
        const beforeText = safeMarkup.substring(0, textIndex);
        const openBraces = (beforeText.match(/\{/g) || []).length;
        const closeBraces = (beforeText.match(/\}/g) || []).length;

        if (openBraces > closeBraces) {
          // We're inside an entity, skip this occurrence
          searchIndex = textIndex + 1;
          continue;
        }

        // This is a safe replacement
        const before = safeMarkup.substring(0, textIndex);
        const after = safeMarkup.substring(textIndex + textToFind.length);
        const newMarkup = `${before}{${textToFind}|${newEntityId}|${selectedClass}}${after}`;

        // Update block markup
        block.markup = newMarkup;
        replacementMade = true;
        break;
      }

      if (replacementMade) {
        // Create new entity entry
        this.entities[newEntityId] = {
          entity: selectedText,
          internal_id: newEntityId,
          type: selectedClass,
          blocks: [blockId],
          count: 1,
          labels: [selectedText]
        };

        console.log('[ENTIFY] Created entity object:', newEntityId);

        // Add class to recent classes
        this.addToRecentClasses(selectedClass);

        // Save block and entities in the background (don't await to avoid blocking)
        console.log('[ENTIFY] Starting background save...');
        this.saveBlockMarkup(blockId, block.markup).catch(err => {
          console.error('[ENTIFY] Error saving block:', err);
        });
        this.sendFilteredEntities().catch(err => {
          console.error('[ENTIFY] Error saving entities:', err);
        });

        console.log('[ENTIFY] Created new entity:', newEntityId, selectedText, selectedClass);

        // Check if this was from a pending triple entification
        if (this.pendingTripleEntification) {
          const { triple, entityType } = this.pendingTripleEntification;

          // Update the triple with the new entity ID
          if (entityType === 'subject') {
            triple.subjectId = newEntityId;
          } else {
            triple.objectId = newEntityId;
          }

          console.log('[ENTIFY] Updated triple with new entity ID:', newEntityId);

          // Clear pending entification
          this.pendingTripleEntification = null;

          // Open reconciliation for the new entity
          this.$nextTick(() => {
            this.onEntityClick(null, newEntityId, blockId);

            // Scroll to the reconcile interface after it opens
            this.$nextTick(() => {
              const reconcileInterface = document.querySelector('.reconcile-interface');
              if (reconcileInterface) {
                reconcileInterface.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
          });
        }
      } else {
        console.log('[ENTIFY] No replacement made');
        // Clear pending entification if failed
        this.pendingTripleEntification = null;
      }
      } catch (error) {
        console.error('[ENTIFY ERROR]', error);
        // Clear pending entification on error
        this.pendingTripleEntification = null;
      } finally {
        // Always reset processing flag, even if there was an error
        console.log('[ENTIFY END] Resetting isProcessingEntification = false');
        this.isProcessingEntification = false;
        console.log('[ENTIFY END] Flag is now:', this.isProcessingEntification);
      }
    },

    async saveBlockMarkup(blockId, markup) {
      try {
        const response = await asyncEmit('update_block_markup', {
          user: this.user,
          job_id: this.documentId,
          block_id: blockId,
          markup: markup
        });

        if (response && response.success) {
          console.log('Block markup saved successfully');
          return response;
        } else {
          console.error('Failed to save block markup:', response?.error);
          return null;
        }
      } catch (error) {
        console.error('Error saving block markup:', error);
        return null;
      }
    },

    loadRecentClasses() {
      try {
        const stored = localStorage.getItem('recentClasses');
        if (stored) {
          this.recentClasses = JSON.parse(stored);
        }
      } catch (error) {
        console.error('Error loading recent classes:', error);
        this.recentClasses = [];
      }
    },

    addToRecentClasses(className) {
      // Remove if already exists
      this.recentClasses = this.recentClasses.filter(c => c !== className);
      // Add to beginning
      this.recentClasses.unshift(className);
      // Keep only last 5
      this.recentClasses = this.recentClasses.slice(0, 5);
      // Save to localStorage
      try {
        localStorage.setItem('recentClasses', JSON.stringify(this.recentClasses));
      } catch (error) {
        console.error('Error saving recent classes:', error);
      }
    },

    loadLastUsedProject() {
      try {
        const stored = localStorage.getItem('lastUsedProject');
        if (stored) {
          this.lastUsedProject = JSON.parse(stored);
        }
      } catch (error) {
        console.error('Error loading last used project:', error);
        this.lastUsedProject = null;
      }
    },

    saveLastUsedProject(projectId) {
      this.lastUsedProject = projectId;
      try {
        localStorage.setItem('lastUsedProject', JSON.stringify(projectId));
      } catch (error) {
        console.error('Error saving last used project:', error);
      }
    },

    loadRecentProperties() {
      try {
        // Load recent triple properties
        const storedTriple = localStorage.getItem('recentTripleProperties');
        if (storedTriple) {
          this.recentTripleProperties = JSON.parse(storedTriple);
        }

        // Load recent qualifier properties
        const storedQualifier = localStorage.getItem('recentQualifierProperties');
        if (storedQualifier) {
          this.recentQualifierProperties = JSON.parse(storedQualifier);
        }
      } catch (error) {
        console.error('Error loading recent properties:', error);
        this.recentTripleProperties = [];
        this.recentQualifierProperties = [];
      }
    },

    addToRecentTripleProperties(property) {
      // Remove if already exists (by PID)
      this.recentTripleProperties = this.recentTripleProperties.filter(p => p.pid !== property.pid);
      // Add to beginning
      this.recentTripleProperties.unshift({
        pid: property.pid,
        label: property.label,
        type: property.type
      });
      // Keep only last 10
      this.recentTripleProperties = this.recentTripleProperties.slice(0, 10);
      // Save to localStorage
      try {
        localStorage.setItem('recentTripleProperties', JSON.stringify(this.recentTripleProperties));
      } catch (error) {
        console.error('Error saving recent triple properties:', error);
      }
    },

    addToRecentQualifierProperties(property) {
      // Remove if already exists (by PID)
      this.recentQualifierProperties = this.recentQualifierProperties.filter(p => p.pid !== property.pid);
      // Add to beginning
      this.recentQualifierProperties.unshift({
        pid: property.pid,
        label: property.label,
        type: property.type
      });
      // Keep only last 10
      this.recentQualifierProperties = this.recentQualifierProperties.slice(0, 10);
      // Save to localStorage
      try {
        localStorage.setItem('recentQualifierProperties', JSON.stringify(this.recentQualifierProperties));
      } catch (error) {
        console.error('Error saving recent qualifier properties:', error);
      }
    }
  },

  mounted() {
    if (this.user) {
      this.initialize();
    }

    // Load recent classes from localStorage
    this.loadRecentClasses();

    // Load last used project from localStorage
    this.loadLastUsedProject();

    // Load recent properties from localStorage
    this.loadRecentProperties();

    // Fetch property patterns for validation
    this.fetchPropertyPatterns();

    // Set up keyboard shortcuts
    window.addEventListener('keydown', this.handleKeydown);

    // Set up text selection listener
    document.addEventListener('mouseup', this.onTextSelection);

    // Measure container height
    if (this.$refs.scrollContainer) {
      this.containerHeight = this.$refs.scrollContainer.clientHeight;
    }
  },

  beforeUnmount() {
    window.removeEventListener('keydown', this.handleKeydown);
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mouseup', this.onMouseUp);
    document.removeEventListener('wheel', this.onDragScroll);
    document.removeEventListener('mouseup', this.onTextSelection);
  },

  updated() {
    // Attach handlers to entities in all blocks
    this.$nextTick(() => {
      const allBlocks = document.querySelectorAll('[data-block-id]');
      allBlocks.forEach(blockElement => {
        const blockId = parseInt(blockElement.getAttribute('data-block-id'));
        // Query ALL block-content elements (there may be multiple when reconcile interface splits content)
        const contentElements = blockElement.querySelectorAll('.block-content');

        contentElements.forEach(contentElement => {
          const entityElements = contentElement.querySelectorAll('.block-entity, .block-entity-no-qid');
          entityElements.forEach(el => {
            const entityId = el.getAttribute('data-id');
            const entityData = this.entities[entityId];

            // Remove old listeners if exist
            el.onmousedown = null;
            el.onclick = null;
            el.ondblclick = null;

            // Add mousedown for drag-and-drop
            el.onmousedown = (event) => this.onEntityMouseDown(event, entityId, entityData, blockId);

            // Add click handler for ALL entities (for context selection and reconciliation)
            if (el.classList.contains('block-entity') || el.classList.contains('block-entity-no-qid')) {
              el.onclick = (event) => {
                // Only trigger if not dragging
                if (!this.isDragging) {
                  event.stopPropagation();
                  this.onEntityClick(event, entityId, blockId);
                }
              };
            }

            // Add double-click handler for entities with QID (only for block-entity)
            if (el.classList.contains('block-entity') && entityData?.qid) {
              el.ondblclick = (event) => {
                event.stopPropagation();
                event.preventDefault();
                const url = `https://base.semlab.io/entity/${entityData.qid}`;
                window.open(url, '_blank');
              };
            }
          });
        });
      });
    });
  }
};
</script>

<template>
  <div>
    <LoginModal v-if="!isAuthenticated"/>
    <div v-else class="work-blocks">
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="toolbar-left">
          <h1 class="toolbar-title">Document Blocks</h1>
        </div>
        <div class="toolbar-right">
          <button
            class="button is-primary is-small"
            @click="showConvenienceEntityModal = true"
            style="margin-right: 10px;"
          >
            <font-awesome-icon :icon="['fas', 'star']" />
            <span style="margin-left: 5px;">Add Convenience Entity</span>
          </button>
          <button
            class="button is-info is-small"
            @click="openAdvancedTripleModalForBatch"
            :disabled="isBatchProcessing"
            style="margin-right: 10px;"
          >
            <font-awesome-icon :icon="['fas', 'circle-nodes']" />
            <span style="margin-left: 5px;">Run Advanced Triple Generation for All Blocks</span>
          </button>
          <button
            class="job-status-toggle"
            @click="jobStatusExpanded = !jobStatusExpanded"
            :class="{ 'expanded': jobStatusExpanded }"
          >
            <font-awesome-icon :icon="['fas', jobStatusExpanded ? 'times' : 'circle-info']" />
            <span>Job Status</span>
          </button>
        </div>
      </div>

      <!-- Batch Processing Progress -->
      <transition name="slide-down">
        <div v-if="isBatchProcessing" class="batch-progress-bar">
          <div class="batch-progress-content">
            <span class="batch-progress-text">
              Processing block {{ batchCurrentBlockIndex }} of {{ batchTotalBlocks }}
            </span>
            <button class="button is-danger is-small" @click="stopBatchProcessing">
              Stop
            </button>
          </div>
        </div>
      </transition>

      <!-- Job Status Panel -->
      <transition name="slide-in">
        <div v-if="jobStatusExpanded" class="job-status-panel">
          <JobStatus v-if="documentId" :jobId="documentId" />
        </div>
      </transition>

      <!-- Custom Search Bar -->
      <transition name="slide-down">
        <div v-if="searchActive" class="search-bar">
          <div class="search-container">
            <input
              ref="searchInput"
              v-model="searchQuery"
              @input="performSearch"
              @keydown.esc="closeSearch"
              type="text"
              class="input"
              placeholder="Search in document..."
            />
            <div class="search-controls">
              <span class="search-count">
                {{ searchResults.length > 0 ? `${currentSearchIndex + 1} / ${searchResults.length}` : 'No results' }}
              </span>
              <button class="button is-small" @click="prevSearchResult" :disabled="searchResults.length === 0">
                <font-awesome-icon :icon="['fas', 'chevron-up']" />
              </button>
              <button class="button is-small" @click="nextSearchResult" :disabled="searchResults.length === 0">
                <font-awesome-icon :icon="['fas', 'chevron-down']" />
              </button>
              <button class="button is-small" @click="closeSearch">
                <font-awesome-icon :icon="['fas', 'times']" />
              </button>
            </div>
          </div>
        </div>
      </transition>

      <!-- Loading State -->
      <div v-if="isLoading" class="loading">
        <font-awesome-icon :icon="['fas', 'spinner']" spin size="2x" />
        <p>Loading blocks...</p>
      </div>

      <!-- Virtual Scrolling Container -->
      <div
        v-else
        ref="scrollContainer"
        class="scroll-container"
        @scroll="onScroll"
      >
        <div class="scroll-content">
          <div
            v-for="item in visibleBlocks"
            :key="item.id"
            class="block-item"
            :class="{ 'focused': focusedBlockId === item.id }"
            :data-block-id="item.id"
            @click="focusBlock(item.id)"
          >
            <div class="block-header">
              <span class="block-id" @click.stop="startBlockSubjectSelection(item.id)">Block {{ item.id }}</span>
              <button
                class="button is-small is-ghost"
                @click.stop="startEditingBlock(item.id, item.block.markup)"
                title="Edit block markup"
              >
                <font-awesome-icon :icon="['fas', 'pencil']" />
              </button>
            </div>

            <!-- Convenience Entities -->
            <div v-if="convenienceEntities.length > 0" class="convenience-entities-row">
              <span
                v-for="ce in convenienceEntities"
                :key="ce.qid"
                class="convenience-entity"
                :data-qid="ce.qid"
                :data-label="ce.label"
                :data-block-id="item.id"
                @mousedown="onConvenienceEntityMouseDown($event, ce, item.id)"
              >
                {{ ce.label }}
              </span>
            </div>

            <!-- Edit mode: textarea -->
            <div v-if="editingBlockId === item.id" class="block-edit-mode">
              <textarea
                class="textarea"
                v-model="editingMarkup"
                rows="10"
                @click.stop
              ></textarea>
              <div class="block-edit-actions">
                <button class="button is-success is-small" @click.stop="saveBlockEdit(item.id)">
                  <font-awesome-icon :icon="['fas', 'circle-check']" />
                  <span>Save</span>
                </button>
                <button class="button is-light is-small" @click.stop="cancelBlockEdit">
                  <font-awesome-icon :icon="['fas', 'times']" />
                  <span>Cancel</span>
                </button>
              </div>
            </div>

            <!-- Display mode: rendered HTML (shown when not editing) -->
            <template v-if="editingBlockId !== item.id">
              <template v-if="reconcilingEntityId && reconcilingBlockId === item.id">
                <!-- Split content: before entity -->
                <div
                  class="block-content"
                  v-html="markupToHTML(splitMarkupForReconcile(item.block.markup, reconcilingEntityId, reconcilingEntityOccurrence).before)"
                ></div>

                <!-- Reconciliation Interface - appears inline after entity -->
                <div class="reconcile-interface">
              <div class="reconcile-header">
                <strong>Reconciling: {{ entities[reconcilingEntityId]?.entity }}</strong>
                <button class="delete is-small" @click="closeReconcile"></button>
              </div>

              <div class="reconcile-content">
                <!-- Left: Wikibase Search -->
                <div class="reconcile-search">
                  <label class="label is-small">Wikibase</label>
                  <input
                    ref="reconcileSearchInput"
                    class="input is-small"
                    type="text"
                    v-model="reconcileSearchQuery"
                    @input="searchReconcile(reconcileSearchQuery)"
                    placeholder="Search..."
                  />

                  <div v-if="reconcileSearchLoading" class="has-text-centered mt-1">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin size="sm" />
                  </div>

                  <div v-if="reconcileSearchResults.length > 0" class="reconcile-results">
                    <div
                      v-for="(result, index) in reconcileSearchResults"
                      :key="result.id"
                      class="reconcile-result-item"
                      :class="{ 'is-active': index === reconcileSelectedIndex }"
                      @click="selectReconcileResult(result)"
                    >
                      <div class="result-label">{{ result.label }} <span class="result-id">{{ result.id }}</span></div>
                      <div v-if="result.description" class="result-description">{{ result.description }}</div>
                    </div>
                  </div>
                </div>

                <!-- Middle: Wikidata Search -->
                <div class="reconcile-search">
                  <label class="label is-small">Wikidata</label>

                  <div class="select is-small is-fullwidth mb-1">
                    <select v-model="wikidataImportProject">
                      <option :value="null">Select Project *</option>
                      <option v-for="project in projects" :key="project.id" :value="project.id">
                        {{ project.label }}
                      </option>
                    </select>
                  </div>

                  <input
                    class="input is-small"
                    type="text"
                    v-model="wikidataSearchQuery"
                    @input="searchWikidata(wikidataSearchQuery)"
                    placeholder="Search Wikidata..."
                  />

                  <div v-if="wikidataSearchLoading" class="has-text-centered mt-1">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin size="sm" />
                  </div>

                  <div v-if="wikidataSearchResults.length > 0" class="reconcile-results">
                    <div
                      v-for="(result, index) in wikidataSearchResults"
                      :key="result.id"
                      class="reconcile-result-item wikidata-result-item"
                      :class="{ 'is-active': index === wikidataSelectedIndex }"
                    >
                      <div class="result-content" @click="importFromWikidata(result)">
                        <div class="result-label">{{ result.label }}</div>
                        <div v-if="result.description" class="result-description">{{ result.description }}</div>
                      </div>
                      <a
                        :href="`https://www.wikidata.org/wiki/${result.id}`"
                        target="_blank"
                        class="result-id-link"
                        @click.stop
                      >
                        {{ result.id }}
                      </a>
                    </div>
                  </div>
                </div>

                <!-- Right: Mint -->
                <div class="reconcile-mint">
                  <label class="label is-small">Mint New</label>

                  <div v-if="mintValidationError" class="notification is-danger is-light is-small py-1 px-2">
                    {{ mintValidationError }}
                  </div>

                  <input class="input is-small mb-1" type="text" v-model="mintData.authLabel" placeholder="Label *" />
                  <textarea class="textarea is-small mb-1" v-model="mintData.description" rows="1" placeholder="Description"></textarea>

                  <div class="compact-tags mint-typeahead-container">
                    <input
                      class="input is-small mb-1"
                      type="text"
                      placeholder="Search projects..."
                      v-model="mintProjectQuery"
                      @input="onMintProjectInput($event)"
                      @keydown="onMintProjectKeydown($event)"
                      @blur="onMintProjectBlur()"
                      @click.stop
                    />
                    <div
                      v-if="mintProjectSearchActive && mintProjectResults.length > 0"
                      class="mint-typeahead-dropdown"
                      @mousedown.prevent
                    >
                      <div
                        v-for="(proj, idx) in mintProjectResults"
                        :key="proj.id"
                        class="mint-typeahead-item"
                        :class="{ 'is-selected': mintProjectSelectedIndex === idx }"
                        @click="selectMintProject(proj)"
                      >
                        <span class="mint-qid">{{ proj.id }}</span>
                        <span class="mint-label">{{ proj.label }}</span>
                      </div>
                    </div>
                    <div v-if="mintData.project.length" class="tags are-small">
                      <span v-for="(proj, idx) in mintData.project" :key="idx" class="tag is-info">
                        {{ proj.label }} <span class="mint-tag-qid">({{ proj.qid }})</span>
                        <button class="delete is-small" @click="removeMintProject(idx)"></button>
                      </span>
                    </div>
                  </div>

                  <div class="compact-tags mint-typeahead-container">
                    <input
                      class="input is-small mb-1"
                      type="text"
                      placeholder="Search instance types..."
                      v-model="mintInstanceQuery"
                      @input="onMintInstanceInput($event)"
                      @keydown="onMintInstanceKeydown($event)"
                      @blur="onMintInstanceBlur()"
                      @click.stop
                    />
                    <div
                      v-if="mintInstanceSearchActive && mintInstanceResults.length > 0"
                      class="mint-typeahead-dropdown"
                      @mousedown.prevent
                    >
                      <div
                        v-for="(inst, idx) in mintInstanceResults"
                        :key="inst.qid"
                        class="mint-typeahead-item"
                        :class="{ 'is-selected': mintInstanceSelectedIndex === idx }"
                        @click="selectMintInstance(inst)"
                      >
                        <span class="mint-qid">{{ inst.qid }}</span>
                        <span class="mint-label">{{ inst.label }}</span>
                      </div>
                    </div>
                    <div v-if="mintData.instanceOf.length" class="tags are-small">
                      <span v-for="(inst, idx) in mintData.instanceOf" :key="idx" class="tag is-primary">
                        {{ inst.label }} <span class="mint-tag-qid">({{ inst.qid }})</span>
                        <button class="delete is-small" @click="removeMintInstance(idx)"></button>
                      </span>
                    </div>
                  </div>

                  <button class="button is-success is-small is-fullwidth" @click="mintEntity">
                    <font-awesome-icon :icon="['fas', 'plus']" />
                    <span>Mint</span>
                  </button>
                </div>
              </div>
                </div>

                <!-- Split content: after entity -->
                <div
                  class="block-content"
                  v-html="markupToHTML(splitMarkupForReconcile(item.block.markup, reconcilingEntityId, reconcilingEntityOccurrence).after)"
                ></div>
              </template>

              <!-- Normal rendering when not reconciling -->
              <div
                v-else
                class="block-content"
                v-html="markupToHTML(item.block.markup)"
              ></div>
            </template>

            <!-- Compact triples display when NOT focused -->
            <div v-if="focusedBlockId !== item.id && (tripleStatements[item.id] && tripleStatements[item.id].length > 0)" class="block-triples-compact">
              <div
                v-for="triple in tripleStatements[item.id]"
                :key="triple.id"
                class="triple-compact-item"
                :class="{ 'triple-compact-inactive': !triple.active }"
              >
                <span
                  class="triple-compact-subject"
                  :class="{ 'triple-compact-block-subject': triple.blockSubject !== null && triple.blockSubject !== undefined }"
                >
                  <template v-if="triple.blockSubject !== null && triple.blockSubject !== undefined">📦 </template>{{ triple.subjectLabel }}
                </span>
                <span class="triple-compact-arrow">→</span>
                <span class="triple-compact-predicate">{{ triple.propertyLabel || '?' }}</span>
                <span class="triple-compact-arrow">→</span>
                <span
                  class="triple-compact-object"
                  :class="{ 'triple-compact-literal': triple.objectLiteral !== null && triple.objectLiteral !== undefined }"
                >
                  {{ triple.objectLiteral !== null && triple.objectLiteral !== undefined ? triple.objectLiteral : triple.objectLabel }}
                </span>
              </div>
            </div>

            <!-- Workspace when block is focused -->
            <div v-if="focusedBlockId === item.id" class="block-workspace">
              <div class="workspace-header">
                <h3>Triples</h3>
                <div style="display: flex; gap: 0.5rem;">
                  <button
                    class="button is-primary is-small"
                    :class="{ 'is-loading': isExtractingRelationships, 'is-warning': lastExtractionFoundNone }"
                    @click.stop="startAutoRelationships"
                    :disabled="isExtractingRelationships"
                  >
                    <font-awesome-icon v-if="!isExtractingRelationships" :icon="['fas', 'circle-nodes']" />
                    <span>{{ lastExtractionFoundNone ? 'None Found' : 'Generate Relationships' }}</span>
                  </button>
                  <button
                    class="button is-info is-small"
                    @click.stop="openAdvancedTripleModal(focusedBlockId)"
                    :disabled="isExtractingRelationships"
                  >
                    <font-awesome-icon :icon="['fas', 'shapes']" />
                    <span>Advanced</span>
                  </button>
                </div>
              </div>
              <div class="triples-list">
                <div
                  v-for="triple in currentBlockTriples"
                  :key="triple.id"
                  class="triple-item"
                  :class="{ 'triple-auto': triple.source === 'auto', 'triple-inactive': !triple.active }"
                >
                  <input
                    type="checkbox"
                    class="triple-checkbox"
                    v-model="triple.active"
                    :disabled="(!triple.subjectQid && !triple.blockSubject) || (!triple.objectQid && !triple.objectLiteral)"
                    @click.stop
                    :title="((!triple.subjectQid && !triple.blockSubject) || (!triple.objectQid && !triple.objectLiteral)) ? 'Subject and object must have values' : ''"
                  />
                  <div class="triple-subject" :class="{ 'unreconciled': !triple.subjectQid && !triple.blockSubject, 'block-subject': triple.blockSubject !== null && triple.blockSubject !== undefined }">
                    <!-- Block subject -->
                    <span v-if="triple.blockSubject !== null && triple.blockSubject !== undefined" class="triple-label block-subject-label">
                      📦 {{ triple.subjectLabel }}
                    </span>

                    <!-- Entity subject -->
                    <template v-else>
                      <span
                        class="triple-label"
                        :class="{ 'clickable': !triple.subjectQid }"
                        @click="!triple.subjectQid ? onTripleEntityClick(triple, 'subject', $event) : null"
                      >
                        {{ triple.subjectLabel }}
                      </span>
                      <span v-if="triple.subjectQid" class="qid-badge">{{ triple.subjectQid }}</span>
                      <span v-else class="unreconciled-warning" title="Unreconciled entity - click to reconcile">
                        <font-awesome-icon :icon="['fas', 'exclamation-triangle']" />
                        unreconciled
                      </span>
                    </template>
                  </div>
                  <div class="triple-predicate">
                    <template v-if="triple.propertyQid">
                      <span class="triple-label">{{ triple.propertyLabel }}</span>
                      <span
                        class="qid-badge clickable"
                        @click="clearProperty(triple)"
                      >
                        {{ triple.propertyQid }}
                      </span>
                    </template>
                    <div v-else class="property-typeahead">
                      <input
                        :ref="`propertyInput_${triple.id}`"
                        type="text"
                        class="input is-small"
                        placeholder="Type P## or property name..."
                        v-model="triple.propertyLabel"
                        @input="onPropertyInput(triple, $event)"
                        @keydown="onPropertyKeydown(triple, $event)"
                        @focus="onPropertyFocus(triple, $event)"
                        @blur="onPropertyBlur(triple)"
                        @click.stop
                      />

                      <!-- Recent properties popup -->
                      <div
                        v-if="showRecentProperties[triple.id] && recentTripleProperties.length > 0"
                        class="recent-properties-popup"
                        :style="getRecentPropertiesPosition(triple.id)"
                        @mousedown.prevent
                      >
                        <div
                          v-for="prop in recentTripleProperties.slice().sort((a, b) => a.pid.localeCompare(b.pid))"
                          :key="prop.pid"
                          class="recent-property-item"
                          @click="selectProperty(triple, prop)"
                        >
                          <span class="property-pid">{{ prop.pid }}</span>
                          <span class="property-label">{{ prop.label }}</span>
                        </div>
                      </div>

                      <div
                        v-if="propertySearchActive[triple.id] && propertySearchResults[triple.id] && propertySearchResults[triple.id].length > 0"
                        class="property-dropdown"
                        :style="getDropdownPosition(triple.id)"
                        @mousedown.prevent
                      >
                        <div
                          v-for="(prop, idx) in propertySearchResults[triple.id]"
                          :key="prop.pid"
                          class="property-dropdown-item"
                          :class="{ 'is-selected': propertySearchSelectedIndex[triple.id] === idx }"
                          @click="selectProperty(triple, prop)"
                        >
                          <span class="property-pid">{{ prop.pid }}</span>
                          <span class="property-label">{{ prop.label }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="triple-object" :class="{ 'unreconciled': !triple.objectQid && !triple.objectLiteral }">
                    <!-- Literal value input (for literal-type properties) -->
                    <input
                      v-if="triple.objectLiteral !== null && triple.objectLiteral !== undefined"
                      type="text"
                      class="input is-small literal-input"
                      v-model="triple.objectLiteral"
                      placeholder="Enter literal value..."
                      @click.stop
                    />

                    <!-- Entity reference (for QID-type properties) -->
                    <template v-else>
                      <span
                        class="triple-label"
                        :class="{ 'clickable': !triple.objectQid || triple.objectQid === '' }"
                        @click="!triple.objectQid || triple.objectQid === '' ? onTripleEntityClick(triple, 'object', $event) : null"
                      >
                        {{ triple.objectLabel }}
                      </span>
                      <span v-if="triple.objectQid && triple.objectQid !== ''" class="qid-badge">{{ triple.objectQid }}</span>
                      <span v-else class="unreconciled-warning" title="Unreconciled entity - click to reconcile">
                        <font-awesome-icon :icon="['fas', 'exclamation-triangle']" />
                        unreconciled
                      </span>
                    </template>
                  </div>

                  <!-- Context/Qualifier Section -->
                  <div class="triple-contexts">
                    <!-- Add context button (only for complete triples) -->
                    <div
                      v-if="triple.subjectQid && triple.propertyQid && triple.objectQid"
                      class="context-add-section"
                    >
                      <!-- Show error message when there's an error -->
                      <div
                        v-if="contextCursorMode && contextCursorMode.tripleId === triple.id && contextErrorMessage"
                        class="context-error-status"
                      >
                        ⚠️ {{ contextErrorMessage }}
                      </div>

                      <!-- Show selection status when in cursor mode for this triple (no error) -->
                      <div
                        v-else-if="contextCursorMode && contextCursorMode.tripleId === triple.id"
                        class="context-selection-status"
                      >
                        👆 Selecting for property
                        <strong>{{ contextCursorMode.propertyLabel }}</strong>
                        <span class="property-type-badge">({{ contextCursorMode.propertyType }})</span>
                        <span class="context-help-text">— press ESC to exit</span>
                      </div>

                      <!-- Show input when NOT in cursor mode for this triple -->
                      <div
                        v-else
                        class="context-property-typeahead"
                      >
                        <input
                          :ref="`contextPropertyInput_${triple.id}`"
                          type="text"
                          class="input is-small context-input"
                          placeholder="+ Add qualifier..."
                          v-model="contextPropertySearchQuery[triple.id]"
                          @input="onContextPropertyInput(triple, $event)"
                          @keydown="onContextPropertyKeydown(triple, $event)"
                          @focus="onContextPropertyFocus(triple, $event)"
                          @blur="onContextPropertyBlur(triple)"
                          @click.stop
                        />

                        <!-- Recent qualifier properties popup -->
                        <div
                          v-if="showRecentQualifierProperties[triple.id] && recentQualifierProperties.length > 0"
                          class="recent-properties-popup"
                          @mousedown.prevent
                        >
                          <div
                            v-for="prop in recentQualifierProperties.slice().sort((a, b) => a.pid.localeCompare(b.pid))"
                            :key="prop.pid"
                            class="recent-property-item"
                            @click="selectContextProperty(triple, prop)"
                          >
                            <span class="property-pid">{{ prop.pid }}</span>
                            <span class="property-label">{{ prop.label }}</span>
                          </div>
                        </div>

                        <div
                          v-if="contextPropertySearchActive[triple.id] && contextPropertySearchResults[triple.id] && contextPropertySearchResults[triple.id].length > 0"
                          class="property-dropdown context-dropdown"
                          :style="getContextDropdownPosition(triple.id)"
                          @mousedown.prevent
                        >
                          <div
                            v-for="(prop, idx) in contextPropertySearchResults[triple.id]"
                            :key="prop.pid"
                            class="property-dropdown-item"
                            :class="{ 'is-selected': contextPropertySearchSelectedIndex[triple.id] === idx }"
                            @click="selectContextProperty(triple, prop)"
                          >
                            <span class="property-pid">{{ prop.pid }}</span>
                            <span class="property-label">{{ prop.label }}</span>
                            <span class="property-type">[{{ prop.type }}]</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Display existing contexts -->
                    <div v-if="triple.contexts && triple.contexts.length > 0" class="context-list">
                      <div
                        v-for="(ctx, ctxIdx) in triple.contexts"
                        :key="`ctx_${triple.id}_${ctxIdx}`"
                        class="context-item"
                      >
                        <span class="context-property">
                          {{ ctx.propertyLabel }}
                          <span class="qid-badge-small">{{ ctx.propertyQid }}</span>
                        </span>
                        <span class="context-separator">→</span>

                        <!-- QID-based context value -->
                        <span v-if="ctx.valueQid" class="context-value-qid">
                          {{ ctx.valueLabel }}
                          <span class="qid-badge-small">{{ ctx.valueQid }}</span>
                        </span>

                        <!-- Literal context value -->
                        <input
                          v-else
                          type="text"
                          class="input is-small context-value-input"
                          v-model="ctx.valueLiteral"
                          @click.stop
                          placeholder="Enter value..."
                        />

                        <button
                          class="delete is-small context-delete"
                          @click.stop="deleteContext(triple, ctxIdx)"
                          title="Delete qualifier"
                        ></button>
                      </div>
                    </div>
                  </div>

                  <div v-if="triple.sourceText" class="triple-source">
                    <small>"{{ triple.sourceText }}"</small>
                  </div>
                  <button
                    class="delete is-small triple-delete"
                    @click.stop="deleteTriple(triple.id)"
                    title="Delete triple"
                  ></button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SVG overlay for drag line -->
      <svg
        v-if="dragLine"
        class="drag-line-svg"
        :class="{ 'fading': !isDragging }"
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        <!-- Outer glow -->
        <line
          :x1="dragLine.x1"
          :y1="dragLine.y1"
          :x2="dragLine.x2"
          :y2="dragLine.y2"
          stroke="#ff6b6b"
          stroke-width="8"
          opacity="0.4"
          filter="url(#glow)"
        />
        <!-- Middle glow -->
        <line
          :x1="dragLine.x1"
          :y1="dragLine.y1"
          :x2="dragLine.x2"
          :y2="dragLine.y2"
          stroke="#ff8787"
          stroke-width="4"
          opacity="0.6"
        />
        <!-- Core beam -->
        <line
          :x1="dragLine.x1"
          :y1="dragLine.y1"
          :x2="dragLine.x2"
          :y2="dragLine.y2"
          stroke="#ffe0e0"
          stroke-width="2"
        />
      </svg>
    </div>

    <!-- Text Selection Tooltip for Entification -->
    <div
      v-if="selectionTooltip.show"
      class="selection-tooltip"
      :style="{
        left: selectionTooltip.x + 'px',
        top: selectionTooltip.y + 'px'
      }"
    >
      <div v-if="selectionTooltip.hasEntityOverlap" class="tooltip-warning">
        <font-awesome-icon :icon="['fas', 'exclamation-triangle']" />
        Selection contains an entity
      </div>
      <div v-else class="tooltip-content">
        <div class="tooltip-header">Entify: "{{ selectionTooltip.selectedText }}"</div>
        <div style="font-size: 0.7rem; color: #999; margin-bottom: 0.25rem;">
          Selected: {{ selectionTooltip.selectedClass }}
        </div>
        <div class="tooltip-controls">
          <div class="select is-small">
            <select v-model="selectionTooltip.selectedClass" @change="console.log('Select changed to:', $event.target.value)">
              <option v-for="(qid, className) in sortedClassMap" :key="className" :value="className">
                {{ className }}
              </option>
            </select>
          </div>
          <button class="button is-success is-small" @mousedown.stop="entifySelectedText" @click.stop>
            <font-awesome-icon :icon="['fas', 'circle-check']" />
          </button>
          <button class="button is-light is-small" @mousedown.stop="selectionTooltip.show = false; isProcessingEntification = false" @click.stop>
            <font-awesome-icon :icon="['fas', 'times']" />
          </button>
        </div>
        <div v-if="recentClasses.length > 0" class="recent-classes">
          <div style="font-size: 0.65rem; color: #999; margin-bottom: 0.25rem;">Recent:</div>
          <div class="recent-classes-buttons">
            <button
              v-for="className in recentClasses"
              :key="className"
              class="button is-small recent-class-btn"
              :class="{ 'is-primary': selectionTooltip.selectedClass === className }"
              @mousedown.stop="selectionTooltip.selectedClass = className"
              @click.stop
            >
              {{ className }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Convenience Entity Modal -->
    <div v-if="showConvenienceEntityModal" class="modal is-active">
      <div class="modal-background" @click="closeConvenienceEntityModal"></div>
      <div class="modal-card" style="width: 500px; max-width: 95vw;">
        <header class="modal-card-head">
          <p class="modal-card-title">Add Convenience Entity</p>
          <button class="delete" @click="closeConvenienceEntityModal"></button>
        </header>
        <section class="modal-card-body">
          <div class="field">
            <label class="label">Search Wikibase</label>
            <div class="control">
              <input
                class="input"
                type="text"
                placeholder="Search for entity..."
                v-model="convenienceEntitySearchQuery"
                @input="searchConvenienceEntity"
                @keydown="onConvenienceEntityKeydown"
                ref="convenienceEntitySearchInput"
              />
            </div>
          </div>

          <div class="convenience-entity-search-area">
            <div v-if="convenienceEntitySearchLoading" class="has-text-centered py-3">
              <font-awesome-icon :icon="['fas', 'spinner']" spin />
              <span class="ml-2">Searching...</span>
            </div>

            <div v-else-if="convenienceEntitySearchResults.length > 0" class="convenience-entity-results">
              <div
                v-for="(result, idx) in convenienceEntitySearchResults"
                :key="result.id"
                class="convenience-entity-result-item"
                :class="{ 'is-selected': convenienceEntitySelectedIndex === idx }"
                @click="addConvenienceEntity(result)"
              >
                <div class="result-main">
                  <span class="result-label">{{ result.label }}</span>
                  <span class="result-qid">{{ result.id }}</span>
                </div>
                <div v-if="result.description" class="result-description">{{ result.description }}</div>
              </div>
            </div>

            <div v-else class="has-text-centered py-4 has-text-grey">
              Type to search for entities...
            </div>
          </div>

          <!-- Current convenience entities -->
          <div v-if="convenienceEntities.length > 0" class="mt-4">
            <label class="label">Current Convenience Entities</label>
            <div class="tags">
              <span v-for="(entity, idx) in convenienceEntities" :key="entity.qid" class="tag is-primary is-medium">
                {{ entity.label }}
                <span class="convenience-tag-qid">({{ entity.qid }})</span>
                <button class="delete is-small" @click="removeConvenienceEntity(idx)"></button>
              </span>
            </div>
          </div>
        </section>
        <footer class="modal-card-foot">
          <button class="button" @click="closeConvenienceEntityModal">Close</button>
        </footer>
      </div>
    </div>

    <!-- Advanced Triple Generation Modal -->
    <div v-if="showAdvancedTripleModal" class="modal is-active">
      <div class="modal-background" @click="closeAdvancedTripleModal"></div>
      <div class="modal-card" style="width: 1200px; max-width: 95vw; max-height: 90vh;">
        <header class="modal-card-head" style="padding: 0.75rem 1rem;">
          <button class="delete" @click="closeAdvancedTripleModal"></button>
        </header>
        <section class="modal-card-body" style="max-height: calc(90vh - 120px); overflow-y: auto;">
          <div v-if="loadingProperties" class="has-text-centered" style="padding: 2rem;">
            <font-awesome-icon :icon="['fas', 'spinner']" spin size="2x" />
            <p class="mt-2">Loading properties...</p>
          </div>

          <div v-else>
            <!-- Entity Filter -->
            <div class="field">
              <label class="label">Entity Filter</label>
              <div class="control radio-columns">
                <label class="radio radio-column">
                  <input type="radio" v-model="useReconciledOnly" :value="true" />
                  <span>Reconciled only (with QID)</span>
                </label>
                <label class="radio radio-column">
                  <input type="radio" v-model="useReconciledOnly" :value="false" />
                  <span>All entities</span>
                </label>
              </div>
            </div>

            <!-- Property Selection -->
            <div class="field">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <label class="label" style="margin-bottom: 0;">
                  Properties to Include
                  <span class="has-text-grey-light">({{ selectedProperties.length }} selected)</span>
                </label>
                <label class="checkbox">
                  <input type="checkbox" v-model="selectAllProperties" @change="toggleSelectAllProperties" />
                  Select All
                </label>
              </div>

              <!-- Property Search -->
              <div class="control mb-2">
                <input
                  class="input is-small"
                  type="text"
                  v-model="propertySearchFilter"
                  placeholder="Search properties by PID, label, description, or range..."
                />
              </div>

              <div class="properties-table">
                <div
                  v-for="prop in filteredProperties"
                  :key="prop.pid"
                  class="property-row"
                >
                  <label class="checkbox property-checkbox">
                    <input type="checkbox" :value="prop.pid" v-model="selectedProperties" />
                    <span class="property-pid">{{ prop.pid }}</span>
                    <span class="property-label">{{ prop.label }}</span>
                  </label>
                  <div class="property-details">
                    <span v-if="prop.description" class="property-description">{{ prop.description }}</span>
                    <span v-if="prop.ranges.length > 0" class="property-range">Range: {{ prop.ranges.join(', ') }}</span>
                    <span v-if="prop.instructions" class="property-instructions">{{ prop.instructions }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Custom Instructions -->
            <div class="field">
              <label class="label">Additional Instructions (optional)</label>
              <div class="control">
                <textarea
                  class="textarea"
                  v-model="customPromptText"
                  placeholder="Add any additional instructions for the LLM..."
                  rows="3"
                ></textarea>
              </div>
            </div>
          </div>
        </section>
        <footer class="modal-card-foot">
          <button
            class="button is-success"
            @click="startBatchAdvancedTripleGeneration"
            :disabled="loadingProperties || selectedProperties.length === 0 || isExtractingRelationships"
            :class="{ 'is-loading': isExtractingRelationships }"
          >
            Generate Triples
          </button>
          <button class="button" @click="closeAdvancedTripleModal">Cancel</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.work-blocks {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
}

/* Toolbar */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  flex-shrink: 0;
  height: 3rem;
  position: relative;
  z-index: 1000;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
  color: #333;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

/* Job Status Toggle Button */
.job-status-toggle {
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s;
}

.job-status-toggle:hover {
  background: #0056b3;
}

.job-status-toggle.expanded {
  background: #dc3545;
}

.job-status-toggle.expanded:hover {
  background: #c82333;
}

/* Job Status Panel */
.job-status-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 450px;
  max-width: 90vw;
  height: 100vh;
  background: white;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
  z-index: 999;
  overflow-y: auto;
  padding: 1rem;
}

.job-status-panel :deep(.card) {
  margin: 0;
  box-shadow: none;
}

/* Slide-in animation */
.slide-in-enter-active,
.slide-in-leave-active {
  transition: transform 0.3s ease;
}

.slide-in-enter-from,
.slide-in-leave-to {
  transform: translateX(100%);
}

.batch-progress-bar {
  background: #3298dc;
  color: white;
  padding: 0.75rem 2rem;
  border-bottom: 1px solid #2980b9;
  flex-shrink: 0;
}

.batch-progress-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-progress-text {
  font-weight: 600;
  font-size: 1rem;
}

.search-bar {
  background: #f5f5f5;
  padding: 1rem 2rem;
  border-bottom: 1px solid #dee2e6;
  flex-shrink: 0;
}

.search-container {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.search-container input {
  flex: 1;
}

.search-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.search-count {
  font-size: 0.9rem;
  color: #666;
  min-width: 100px;
  text-align: right;
}

.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from, .slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 1rem;
  flex: 1;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: white;
  position: relative;
}

.scroll-content {
  width: 100%;
  padding-bottom: 100px;
}

.block-item {
  padding: 1.5rem 2rem;
  border-bottom: 1px solid #eee;
  background: white;
  cursor: pointer;
  transition: background 0.2s;
  position: relative;
}

.block-item.focused {
  background: #f0f8ff;
}

.block-header {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 0.5rem;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.block-id {
  background: #e0e0e0;
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.2s;
}

.block-id:hover {
  background: #c0c0c0;
}

.block-edit-mode {
  margin-bottom: 1rem;
}

.block-edit-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.block-content {
  line-height: 1.9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
  font-size: 1.2rem;
  color: #2c3e50;
  position: relative;
}

/* Block content styles */
.block-content :deep(.block-word) {
  display: inline;
}

.block-content :deep(.search-highlight) {
  background-color: #ffeb3b;
  color: #000;
  font-weight: 600;
  padding: 2px 0;
  border-radius: 2px;
}

.block-content :deep(.block-entity-no-qid) {
  display: inline;
  background: none;
  border: 1px solid transparent;
  padding: 2px 4px;
  cursor: grab;
  border-radius: 3px;
  transition: background 0.2s, border-color 0.2s;
}

.block-content :deep(.block-entity-no-qid:hover) {
  background: rgba(150, 150, 150, 0.15);
  border-color: rgba(150, 150, 150, 0.4);
  border-style: dashed;
}

.block-content :deep(.block-entity-no-qid:active) {
  cursor: grabbing;
}

.block-content :deep(.block-entity) {
  background: rgba(255, 250, 205, 0.3);
  padding: 2px 4px;
  border-radius: 3px;
  border: 1px solid rgba(240, 230, 140, 0.3);
  cursor: grab;
  transition: background 0.2s;
}

.block-content :deep(.block-entity:active) {
  cursor: grabbing;
}


/* Entity type colors based on instance type QID */
.block-content :deep(.entity-type-Q1) { /* person */
  background: rgba(255, 235, 238, 0.4);
  border-color: rgba(239, 154, 154, 0.3);
}

.block-content :deep(.entity-type-Q19058) { /* city */
  background: rgba(227, 242, 253, 0.4);
  border-color: rgba(144, 202, 249, 0.3);
}

.block-content :deep(.entity-type-Q33506) { /* museum */
  background: rgba(243, 229, 245, 0.4);
  border-color: rgba(206, 147, 216, 0.3);
}

.block-content :deep(.entity-type-Q3305213) { /* painting */
  background: rgba(255, 249, 196, 0.3);
  border-color: rgba(255, 245, 157, 0.3);
}

.block-content :deep(.entity-type-Q618123) { /* geographical object */
  background: rgba(200, 230, 201, 0.4);
  border-color: rgba(129, 199, 132, 0.3);
}

.block-content :deep(.entity-type-Q43229) { /* organization */
  background: rgba(255, 224, 178, 0.4);
  border-color: rgba(255, 183, 77, 0.3);
}

.block-content :deep(.entity-type-Q5) { /* human */
  background: rgba(255, 235, 238, 0.4);
  border-color: rgba(239, 154, 154, 0.3);
}

.block-newline {
  display: block;
  content: "";
  margin: 0.5rem 0;
}

/* Block Workspace */
.block-workspace {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 2px solid #d0e8ff;
  background: #f8f9fa;
  padding: 0.75rem;
  border-radius: 4px;
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.workspace-header h3 {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0;
  color: #333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Drag Line SVG */
.drag-line-svg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 9999;
  opacity: 1;
  transition: opacity 1s;
}

.drag-line-svg.fading {
  opacity: 0;
}

/* Triples List */
.triples-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
}

.triple-item {
  padding: 0.5rem 0.75rem;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  display: grid;
  grid-template-columns: auto 1fr auto 1fr auto auto;
  gap: 0.75rem;
  align-items: center;
  position: relative;
  font-size: 0.875rem;
  overflow: visible;
}

.triple-item.triple-inactive {
  background: #f5f5f5;
}

.triple-item.triple-auto {
  border-left: 3px solid #17a2b8;
}

.triple-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  margin: 0;
}

.triple-subject,
.triple-predicate,
.triple-object {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.literal-input {
  flex: 1;
  max-width: 300px;
  font-size: 0.85rem;
  padding: 0.35rem 0.5rem;
  border: 1px solid #8b5cf6;
  background: #f3f0ff;
}

.literal-input:focus {
  border-color: #7c3aed;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.1);
}

.triple-subject {
  color: #007bff;
  font-weight: 600;
}

.triple-subject.block-subject {
  color: #ff6b6b;
  font-weight: 700;
}

.block-subject-label {
  background: #ffe3e3;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.triple-predicate {
  color: #28a745;
  font-weight: 500;
  position: relative;
}

.property-typeahead {
  position: relative;
  width: 200px;
  z-index: 100;
}

.property-typeahead input {
  width: 100%;
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
}

.property-dropdown {
  /* Position will be set via inline style using fixed positioning */
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-height: 250px;
  overflow-y: auto;
  z-index: 10000;
}

.property-dropdown-item {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  display: flex;
  gap: 0.5rem;
  align-items: center;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.85rem;
}

.property-dropdown-item:last-child {
  border-bottom: none;
}

.property-dropdown-item:hover,
.property-dropdown-item.is-selected {
  background: #e8f4fd;
}

.property-pid {
  font-weight: 600;
  color: #28a745;
  min-width: 45px;
}

.property-label {
  color: #333;
  flex: 1;
}

/* Recent properties popup */
.recent-properties-popup {
  /* Position set via inline style using fixed positioning */
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-height: 200px;
  overflow-y: auto;
  z-index: 10000;
}

.recent-property-item {
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  display: flex;
  gap: 0.4rem;
  align-items: center;
  border-bottom: 1px solid #e9ecef;
  font-size: 0.8rem;
  transition: background 0.15s;
}

.recent-property-item:last-child {
  border-bottom: none;
}

.recent-property-item:hover {
  background: #e7f1ff;
}

.triple-object {
  color: #333;
}

.triple-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.triple-label.clickable {
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
}

.triple-label.clickable:hover {
  text-decoration-style: solid;
  color: #0056b3;
}

.unreconciled-warning {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: #dc3545;
  font-size: 0.75rem;
  font-weight: 500;
  margin-left: 0.5rem;
}

.unreconciled-warning svg {
  width: 12px;
  height: 12px;
}

.triple-checkbox:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.triple-source {
  grid-column: 2 / -2;
  color: #6c757d;
  font-style: italic;
  margin-top: -0.25rem;
  padding-left: 1.5rem;
}

.triple-delete {
  margin-left: 0.5rem;
}

/* Context/Qualifier Styles */
.triple-contexts {
  grid-column: 2 / -1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-left: 1.5rem;
}

.context-add-section {
  display: flex;
  align-items: center;
}

.context-property-typeahead {
  position: relative;
  width: 250px;
}

.context-input {
  width: 100%;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  border: 1px dashed #ccc;
}

/* Context selection status message */
.context-selection-status {
  padding: 0.5rem 0.75rem;
  background: #fff3cd;
  border: 2px solid #ffc107;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #856404;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.context-selection-status strong {
  color: #6f42c1;
}

.context-help-text {
  color: #6c757d;
  font-size: 0.75rem;
  font-style: italic;
  margin-left: auto;
}

.context-error-status {
  padding: 0.5rem 0.75rem;
  background: #f8d7da;
  border: 2px solid #dc3545;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #721c24;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.property-type-badge {
  color: #6c757d;
  font-size: 0.75rem;
  font-style: italic;
}

.context-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.context-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 0.85rem;
}

.context-property {
  color: #6f42c1;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.context-separator {
  color: #6c757d;
}

.context-value-qid {
  color: #007bff;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.context-value-input {
  flex: 1;
  max-width: 300px;
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
}

.qid-badge-small {
  background: #e7f3ff;
  color: #0066cc;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-family: monospace;
}

.context-delete {
  margin-left: auto;
}

.property-type {
  color: #6c757d;
  font-size: 0.7rem;
  font-style: italic;
  margin-left: 0.25rem;
}

/* Dragging Origin Glow Effect */
.block-content :deep(.block-entity.dragging-origin) {
  animation: drag-glow 0.6s ease-in-out infinite alternate !important;
  filter: drop-shadow(0 0 8px rgba(255, 107, 107, 0.9))
          drop-shadow(0 0 16px rgba(255, 107, 107, 0.6)) !important;
  position: relative !important;
  z-index: 100 !important;
  border: 2px solid rgba(255, 107, 107, 0.8) !important;
  border-radius: 4px !important;
  padding: 2px 4px !important;
  background: rgba(255, 107, 107, 0.1) !important;
}

/* Dragging Target Glow Effect */
.block-content :deep(.block-entity.dragging-target) {
  animation: drag-glow 0.6s ease-in-out infinite alternate !important;
  filter: drop-shadow(0 0 8px rgba(255, 107, 107, 0.9))
          drop-shadow(0 0 16px rgba(255, 107, 107, 0.6)) !important;
  position: relative !important;
  z-index: 100 !important;
  border: 2px solid rgba(255, 107, 107, 0.8) !important;
  border-radius: 4px !important;
  padding: 2px 4px !important;
  background: rgba(255, 107, 107, 0.1) !important;
}

@keyframes drag-glow {
  from {
    filter: drop-shadow(0 0 8px rgba(255, 107, 107, 0.9))
            drop-shadow(0 0 16px rgba(255, 107, 107, 0.6));
    border-color: rgba(255, 107, 107, 0.8);
  }
  to {
    filter: drop-shadow(0 0 12px rgba(255, 107, 107, 1))
            drop-shadow(0 0 24px rgba(255, 107, 107, 0.8));
    border-color: rgba(255, 107, 107, 1);
  }
}

/* Compact Triples Display (unfocused blocks) */
.block-triples-compact {
  margin-top: 0.5rem;
  padding: 0.25rem 0.5rem;
  background: #f8f9fa;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.75rem;
  border-left: 2px solid #dee2e6;
}

.triple-compact-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.15rem 0.25rem;
  background: white;
  border-radius: 2px;
  line-height: 1.2;
}

.triple-compact-item.triple-compact-inactive {
  text-decoration: line-through;
}

.triple-compact-subject {
  color: #007bff;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.triple-compact-block-subject {
  color: #ff6b6b;
  font-weight: 700;
}

.triple-compact-predicate {
  color: #28a745;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.triple-compact-object {
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.triple-compact-literal {
  color: #8b5cf6;
  font-style: italic;
}

.triple-compact-arrow {
  color: #6c757d;
  font-size: 0.7rem;
  flex-shrink: 0;
}

.reconcile-btn {
  margin-left: auto;
}

.triple-auto {
  background: #e8f5e9;
  border-color: #81c784;
}

.qid-badge {
  display: inline-block;
  background: #e3f2fd;
  color: #1976d2;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.75rem;
  font-family: monospace;
  margin-left: 0.5rem;
}

.qid-badge.clickable {
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.qid-badge.clickable:hover {
  background: #1976d2;
  color: white;
}

.triple-source {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #f5f5f5;
  border-left: 3px solid #81c784;
  font-style: italic;
  color: #666;
}

/* Convenience Entities */
.convenience-entities-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.4rem 0.5rem;
  margin: 0 -0.5rem;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.convenience-entity {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: white;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: grab;
  user-select: none;
  transition: all 0.15s;
}

.convenience-entity:hover {
  background: #f5f5f5;
  border-color: #bbb;
}

.convenience-entity:active {
  cursor: grabbing;
}

.convenience-entity.dragging-origin {
  animation: glow-pulse-convenience 0.6s ease-in-out infinite alternate;
}

.convenience-entity.dragging-target {
  animation: glow-pulse-target-convenience 0.6s ease-in-out infinite alternate;
}

@keyframes glow-pulse-convenience {
  from {
    box-shadow: 0 0 6px rgba(100, 149, 237, 0.5);
  }
  to {
    box-shadow: 0 0 12px rgba(100, 149, 237, 0.8);
  }
}

@keyframes glow-pulse-target-convenience {
  from {
    box-shadow: 0 0 8px rgba(255, 107, 107, 0.6);
  }
  to {
    box-shadow: 0 0 16px rgba(255, 107, 107, 1);
  }
}

/* Convenience Entity Modal */
.convenience-entity-search-area {
  min-height: 280px;
}

.convenience-entity-results {
  height: 250px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.convenience-entity-result-item {
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.convenience-entity-result-item:last-child {
  border-bottom: none;
}

.convenience-entity-result-item:hover,
.convenience-entity-result-item.is-selected {
  background: #e8f4fd;
}

.convenience-entity-result-item .result-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.convenience-entity-result-item .result-label {
  font-weight: 500;
}

.convenience-entity-result-item .result-qid {
  color: #28a745;
  font-size: 0.85rem;
  font-weight: 600;
}

.convenience-entity-result-item .result-description {
  font-size: 0.8rem;
  color: #666;
  margin-top: 0.25rem;
}

.convenience-tag-qid {
  font-size: 0.75rem;
  opacity: 0.8;
  margin-left: 3px;
}

/* Reconciliation Interface */
.reconcile-marker {
  display: block;
  width: 100%;
}

.reconcile-interface {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #f9f9f9;
  border: 1px solid #3273dc;
  border-radius: 4px;
  font-size: 0.875rem;
}

.reconcile-location-hint {
  background: #e8f4fd;
  padding: 0.25rem 0.5rem;
  margin-bottom: 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
  color: #1a73e8;
}

.reconcile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid #ddd;
}

.reconcile-header strong {
  font-size: 0.875rem;
  color: #363636;
}

.reconcile-content {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

.reconcile-search .label,
.reconcile-mint .label {
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.reconcile-results {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #dbdbdb;
  border-radius: 3px;
  margin-top: 0.25rem;
}

.reconcile-result-item {
  padding: 0.4rem;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
  transition: background 0.1s;
  font-size: 0.8rem;
}

.reconcile-result-item:hover,
.reconcile-result-item.is-active {
  background: #e8f4fd;
}

.reconcile-result-item:last-child {
  border-bottom: none;
}

.result-label {
  font-weight: 600;
  color: #363636;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-id {
  font-size: 0.7rem;
  color: #3273dc;
  font-family: monospace;
  margin-left: 0.5rem;
}

.result-description {
  font-size: 0.75rem;
  color: #7a7a7a;
  margin-top: 0.15rem;
  line-height: 1.2;
}

.wikidata-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem;
  cursor: default;
}

.wikidata-result-item .result-content {
  flex: 1;
  cursor: pointer;
}

.wikidata-result-item .result-label {
  justify-content: flex-start;
}

.result-id-link {
  font-size: 0.7rem;
  color: #3273dc;
  font-family: monospace;
  text-decoration: none;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  background: #f0f0f0;
  white-space: nowrap;
  transition: background 0.2s, color 0.2s;
}

.result-id-link:hover {
  background: #3273dc;
  color: white;
}

.compact-tags {
  margin-bottom: 0.25rem;
}

.compact-tags .tags {
  margin-top: 0.25rem;
  margin-bottom: 0;
}

/* Mint typeahead styles */
.mint-typeahead-container {
  position: relative;
}

.mint-typeahead-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-height: 150px;
  overflow-y: auto;
  z-index: 1001;
}

.mint-typeahead-item {
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  display: flex;
  gap: 0.5rem;
  align-items: center;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.8rem;
}

.mint-typeahead-item:last-child {
  border-bottom: none;
}

.mint-typeahead-item:hover,
.mint-typeahead-item.is-selected {
  background: #e8f4fd;
}

.mint-qid {
  font-weight: 600;
  color: #28a745;
  min-width: 50px;
  font-size: 0.75rem;
}

.mint-label {
  color: #333;
  flex: 1;
}

.mint-tag-qid {
  font-size: 0.7rem;
  opacity: 0.7;
  margin-left: 2px;
}

/* Text Selection Tooltip */
.selection-tooltip {
  position: fixed;
  transform: translate(-50%, -100%);
  background: white;
  border: 2px solid #3273dc;
  border-radius: 6px;
  padding: 0.75rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  min-width: 300px;
}

.tooltip-warning {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #ff9800;
  font-size: 0.875rem;
}

.tooltip-header {
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: #363636;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tooltip-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.tooltip-controls select {
  flex: 1;
  font-size: 0.875rem;
}

.tooltip-controls .button {
  padding: 0.25rem 0.5rem;
}

.recent-classes {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e8e8e8;
}

.recent-classes-buttons {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.recent-class-btn {
  font-size: 0.75rem !important;
  padding: 0.25rem 0.5rem !important;
  height: auto !important;
  line-height: 1.2 !important;
}

/* Advanced Triple Modal */
.radio-columns {
  display: flex;
  gap: 1.5rem;
}

.radio-column {
  flex: 0 0 auto;
  padding: 0.5rem 1rem;
  border: 2px solid #e0e0e0;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.radio-column:hover {
  border-color: #3273dc;
  background: #f0f7ff;
}

.radio-column input[type="radio"]:checked + span {
  font-weight: 600;
}

.radio-column input[type="radio"]:checked {
  accent-color: #3273dc;
}

.properties-table {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 0.5rem;
  background: #fafafa;
}

.property-row {
  padding: 0.5rem;
  border-bottom: 1px solid #e8e8e8;
  transition: background 0.2s;
}

.property-row:hover {
  background: #f0f0f0;
}

.property-row:last-child {
  border-bottom: none;
}

.property-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}

.property-pid {
  font-family: monospace;
  font-weight: 600;
  color: #3273dc;
  min-width: 50px;
}

.property-label {
  font-weight: 500;
  color: #363636;
}

.property-details {
  margin-left: 2rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.property-description {
  font-size: 0.85rem;
  color: #666;
}

.property-range {
  font-size: 0.8rem;
  color: #888;
  font-style: italic;
}

.property-instructions {
  font-size: 0.8rem;
  color: #ff9800;
  font-weight: 500;
}
</style>

<style>
/* Non-scoped styles for body cursor changes */
body.context-selecting-mode,
body.context-selecting-mode * {
  cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='50' height='60' viewport='0 0 100 100' style='fill:black;font-size:30px;'><text y='50%'>👆</text></svg>") 16 0, auto !important;
}
</style>
