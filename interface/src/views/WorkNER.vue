<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/LoginModal.vue'
import { mapWritableState } from "pinia";
import JobStatus from '@/components/JobStatus.vue'


function asyncEmit(eventName, data) {
  return new Promise(function (resolve, reject) {
    socket.emit(eventName, data, (response) => {
      resolve(response);
    })
    setTimeout(reject, 1000 * 120);
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

      semlabClasses: [],

      showMoreBlocks: {}, // used to track which entities have "show more blocks" expanded

      useProjectBulkAlign: null, // used to track which project is selected for bulk alignment

      activeEntity: { 
        internal_id: null, // used to track which entity is active for details view
     
      },

      bulkInstanceOfBase: null,
      bulkInstanceOfDoc: null, // used to track which type is selected for bulk alignment

      blocks: [],
      entities: {},
      entitiesByType: {},
      projects: [], // list of SemLab projects


      statusProjectReconcile:null,

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
 
 
   },
   
   watch: {
    // don't intialize until we have a user
    user(newUser, oldUser) {
      this.initialize()
    }
  },
   
   
  methods: {
    // Add methods here
    async initialize() {

     
      socket.emit('get_ner', {doc:this.documentId, user:this.user}, (response) => {
        // console.log("get_ner response", response)
        if (response.success) {
          // console.log("ner", response.ner)

          // populate the lookup tables by type
          this.blocks = response.ner.blocks
          this.entities = response.ner.entities
          // console.log("this.entities", this.entities)

          this.buildEntitesByType()

        } else {
          console.error("Error fetching document diffs:", response.error);
        }
      });

      this.getSemlabProjects()

      this.setSemlabClasses()

      
    },


    async retriveWikidataEntity(entity){

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
              entity.wikiThumbnail = binding.image.value;
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
              this.entities[e].wikiThumbnail = entity.wikiThumbnail;
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


    async workEntity(internal_id){

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


      let sortOrderPrompt = await this.buildCompareOrderPrompt(entity);
      
      // entity.wikiSortOrderPrompt = sortOrderPrompt.prompt;

      entity.wikiCheckedStatus = 'SEARCHING';
      let newSortOrder
      if (sortOrderPrompt.compareList && sortOrderPrompt.compareList.length == 1){
        // we don't need to sort because ther is only one result
        newSortOrder = sortOrderPrompt.compareList
        newSortOrder[0].order = 1

        newSortOrder = {success: true, error:null, response: newSortOrder}

      }else{
        newSortOrder = await asyncEmit('ask_llm_reconcile_build_search_order', sortOrderPrompt.prompt);

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
                entity.wikiThumbnail = d.o;
                break
              }
            }


            delete entity.wikiCheckedStatus 
            break
          }         
        }
      }else{

        // error in the sort order request
        entity.wikiCheckedStatus = 'ERROR';
        entity.wikiError = true
      }


      for (let queue of [this.workQueue1, this.workQueue2, this.workQueue3]){
        let index = queue.indexOf(internal_id);
        if (index > -1) {
          queue.splice(index, 1); // Remove the entity from the queue
        }
      }
      entity.wikiChecked = true
      delete entity.wikiCheckedStatus



      
    },

    
    async workBaseEntity(internal_id){

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

      for (let queue of [this.baseWorkQueue1, this.baseWorkQueue2, this.baseWorkQueue3]){
        let index = queue.indexOf(internal_id);
        if (index > -1) {
          queue.splice(index, 1); // Remove the entity from the queue
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
        }
        this.entitiesByType[entity.type].push(entity)
      }
      // console.log("entitiesByType", this.entitiesByType)



    },

    details(entity) {
      // Set the active entity for details view
      this.activeEntity = entity;
      // console.log("activeEntity", this.activeEntity)
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
              let searchUrl = `https://www.wikidata.org/w/api.php?action=query&format=json&list=search&srsearch=${encodeURIComponent(entity.entity)}&utf8=&srprop=snippet|titlesnippet|redirecttitle|sectiontitle&origin=*&srlimit=10`;
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

              let prompt = `The ${entity.type}: "${entity.entity}" described in this text:\n`
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

              let prompt = `The ${entity.type}: "${entity.entity}" described in this text:\n`
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
      this.statusProjectReconcile = true;

      let sparql = `

        SELECT ?entity ?entityLabel ?entityDesc
        WHERE 
        {
          ?entity wdt:P1 wd:${this.bulkInstanceOfBase}.
          optional{
            ?entity schema:description ?entityDesc .
          }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }                    
        }
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
          description: (binding.entityDesc) ? binding.entityDesc.value : null
        }
      });


      let prompt = `The following is a list of entities that need to be matched to the data in the JSON structure. Modify the JSON stucture to change the qid value to the for the most likely match. Only make high confidece matches.\n\n`

      for (let i = 0; i < allLabels.length; i++) {
        let entity = allLabels[i];
        prompt += `- ${entity.label} ${entity.description ? `(${entity.description})` : ''} - ID: ${entity.id}\n`;
      }
      let promptEntities = []
      for (let type of Object.keys(this.entitiesByType).sort()){
        if (type == this.bulkInstanceOfDoc){
          // only include entities of the selected class
          for (let entity of this.entitiesByType[type]){
            if (entity.blocks.length > 0){
              promptEntities.push({
                entity: entity.entity,
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
              if (this.entities[entity.internal_id]){
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

    async buildPromptAllSemlab(){

      if (!this.useProjectBulkAlign) {
        alert("Please select a project to align with");
        return;
      }
      this.statusProjectReconcile = true;
      // Fetch the list of SemLab projects
      let sparql = `
        SELECT ?entity ?entityLabel ?instanceOf ?instanceOfLabel
        WHERE 
        {
          
          ?entity wdt:P11 wd:${this.useProjectBulkAlign}.
          ?entity wdt:P1 ?instanceOf.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
          
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q20664 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q2013 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19069 } 
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q23572 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q27513 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19069 }   
          FILTER NOT EXISTS {?entity wdt:P1 wd:Q19063 }   

          
        }



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
        }
      });

      
      let prompt = `The following is a list of entities that need to be matched to the data in the JSON structure. Modify the JSON stucture to change the qid value to the for the most likely match. Only make high confidece matches.\n\n`

      for (let i = 0; i < allLabels.length; i++) {
        let entity = allLabels[i];
        prompt += `- ${entity.label} (${entity.instanceOfLabel}) - ID: ${entity.id}\n`;
      }
      let promptEntities = []
      for (let type of Object.keys(this.entitiesByType).sort()){
        for (let entity of this.entitiesByType[type]){
          if (entity.blocks.length > 0){
            promptEntities.push({
              entity: entity.entity,
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
              if (this.entities[entity.internal_id]){
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

      let prompt = `Is the ${entity.type}: "${unescapeHtmlEntities(entity.entity)}" described in this text:\n`
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
              <div v-for="type in Object.keys(entitiesByType).sort()">
                <a :href="'#type-'+type" >{{ type }} <span class="lite-text">[{{ entitiesByType[type].length }}]</span></a>
              </div>
            </div>
          </div>
          <div class="column">
            <div class="a-diff">
              <h3 class="title is-4">All Entities Actions</h3>
              <div>
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
                <button v-if="!statusProjectReconcile" class="button" @click="buildPromptByClass" style="height: 1.5em;">Go</button>


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

        <table class="table is-striped is-hoverable is-fullwidth">
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
                </td>
              </tr>
              <template v-for="entity in entitiesByType[index]">
                <tr>
                  <td>{{ entity.entity }}</td>
                  <td v-if="!entity.qid">



                    <font-awesome-icon v-if="entity.wikiBaseCheckedStatus" class="spin" style="font-size: 1em;" :icon="['fas', 'hourglass-half']" />
                    <span v-if="entity.wikiBaseCheckedStatus === 'SEARCHING'" class="tag is-info">Searching...</span>
                    <span v-if="entity.wikiBaseCheckedStatus === 'RECONCILING'" class="tag is-warning">Reconciling...</span>
                    <span v-if="entity.wikiBaseCheckedStatus === 'ERROR' || entity.wikiBaseError" class="tag is-danger">Error</span>
                    <span v-if="entity.wikiBaseNoMatch" class="tag is-warning">No Search Results</span>
                    <span v-if="entity.wikiBaseNoGoodMatch" class="tag is-warning">No Good Match Found</span>


                    
                    <template v-if="entity.wikiBaseChecked && entity.qid">
                      <span class="tag is-success matched-tag">Matched</span>

                      <div class="hint--top hint--large" :aria-label="entity.wikiBaseReason">
                        <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />


                        <a  :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank">{{ entity.labelSemlab }}</a>
                        <span class="lite-text">({{ entity.wikiBaseDescription }})[{{ entity.wikiBaseConfidence }}%]</span>
                        <!-- <font-awesome-icon class="match-info" :aria-label="entity.wikiReason"  :icon="['fas', 'circle-info']" /> -->

                      </div>
                    </template>



                  </td>
                  <td v-else>


                    <template v-if="entity.wikiBaseChecked && entity.qid">
                      <span class="tag is-success matched-tag">Matched</span>

                      <div class="hint--top hint--large" :aria-label="entity.wikiBaseReason">
                        <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />


                        <a  :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank">{{ entity.labelSemlab }}</a>
                        <span class="lite-text">[{{ entity.wikiBaseConfidence }}%]</span>
                        <!-- <font-awesome-icon class="match-info" :aria-label="entity.wikiReason"  :icon="['fas', 'circle-info']" /> -->

                      </div>

                    
                    </template>
                    <template v-else>
                    <a :href="'https://base.semlab.io/wiki/Item:' + entity.qid" target="_blank" class="thumbnail-semlab-link">
                      <img v-if="entity.thumbnail" :src="entity.thumbnail" alt="Thumbnail" class="thumbnail-semlab" />
                      <span v-if="entity.labelSemlab" class="thumbnail-label">{{ entity.labelSemlab }}</span>

                      <span v-else>{{ entity.qid }}</span>
                    </a>
                    </template>

                  </td>

                  <td>
                    

                    <font-awesome-icon v-if="entity.wikiCheckedStatus" class="spin" style="font-size: 1em;" :icon="['fas', 'hourglass-half']" />
                    <span v-if="entity.wikiCheckedStatus === 'SEARCHING'" class="tag is-info">Searching...</span>
                    <span v-if="entity.wikiCheckedStatus === 'RECONCILING'" class="tag is-warning">Reconciling...</span>
                    <span v-if="entity.wikiCheckedStatus === 'ERROR' || entity.wikiError" class="tag is-danger">Error</span>
                    <span v-if="entity.wikiNoMatch" class="tag is-warning">No Search Results</span>


                    


                    <template v-if="entity.wikiChecked && entity.wikiQid">
                      <span class="tag is-success matched-tag">Matched</span>
                      
                      <div class="hint--top hint--large" :aria-label="entity.wikiReason">
                        <img v-if="entity.wikiThumbnail" :src="entity.wikiThumbnail" alt="Thumbnail" class="thumbnail-wikidata" />


                        <a  :href="'https://www.wikidata.org/wiki/' + entity.wikiQid" target="_blank">{{ entity.wikiLabel }}</a>
                        <span class="lite-text">({{ entity.wikiDescription }})[{{ entity.wikiConfidence }}%]</span>
                        <!-- <font-awesome-icon class="match-info" :aria-label="entity.wikiReason"  :icon="['fas', 'circle-info']" /> -->
                        <span>
                          
                        </span>

                      </div>
                    </template>
                    <template v-else="entity.wikiQid">
                      
                      <div>
                        <img v-if="entity.wikiThumbnail" :src="entity.wikiThumbnail" alt="Thumbnail" class="thumbnail-wikidata" />


                        <a  :href="'https://www.wikidata.org/wiki/' + entity.wikiQid" target="_blank">{{ entity.wikiLabel }}</a>
                        <span class="lite-text" v-if="entity.wikiDescription">({{ entity.wikiDescription }})</span>
                      </div>
                    </template>                    

                  </td>
                  <td>{{ entity.blocks.join(', ') }}</td>
                  <td><button class="button" @click="details(entity)">Details</button></td>
                </tr>
                <tr v-if="activeEntity.internal_id == entity.internal_id">
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

.a-diff{
  padding: 1em;
  margin: 1em;
  background-color: whitesmoke;
}
.diff-example{
  font-family: 'Courier New', Courier, monospace;
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

.judgement-text{
  font-style: italic;
}

.toolbar{
  padding: 1em;
}





</style>