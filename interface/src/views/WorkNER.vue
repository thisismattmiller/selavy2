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

      statusClassReconcile: null,

      statusLabelNormalize:null,


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
          }else{

            let badMatchType
            for (let d of compareData){
              if (d.p == 'instance of') {
                badMatchType = d.o;
                break
              }
            }

            console.log("No match found for entity", entity.entity, "with qid", toReconcile.qid, badMatchType, compareResult)


          }         
        }
      }else{

        // error in the sort order request
        entity.wikiCheckedStatus = 'ERROR';
        entity.wikiError = true
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

      this.statusLabelNormalize = true;

      let sendList = []
      let sendBlocks = []
      console.log(this.entities)
      for (let eId in this.entities){
        let entity = this.entities[eId];
        sendList.push({
          internal_id: entity.internal_id,
          labels: entity.labels,
          normalizedLabels: []
        });
        if (sendBlocks.indexOf(entity.blocks[0]) == -1){
          sendBlocks.push(entity.blocks[0]);
        }
      }

      let allBlockText = sendBlocks.map(b => this.blocks[b].clean).join(" ");


      let prompt = `Normalize the words in this list of objects, normalize the labels in the key "labels", if they have honorifics remove them, if they are a shortened version of the entity make it the fuller form, make the term more search friendly if you were searching Wikipedia for the term. Do not invent names or expand the word without strong evidence, if you cannot expand it return it as it is. After the JSON below is the text the names are found in, use this text to help expand the name. Return JSON Only.`
      prompt += `\n\nJSON:\n`
      prompt += JSON.stringify(sendList, null, 2);
      prompt += `\n\nText:\n"${allBlockText}"\n\n`
      console.log(prompt)


      // let response = await asyncEmit('ask_llm_normalize_labels', prompt);

      let response = {"success":true,"response":[{"internal_id":"1","labels":["Art Albiston"],"normalizedLabels":["Art Albiston"]},{"internal_id":"2","labels":["Alexander Offset Co."],"normalizedLabels":["Alexander Offset Company"]},{"internal_id":"3","labels":["W. Barry"],"normalizedLabels":["W. Barry"]},{"internal_id":"4","labels":["Genie Productions, Inc."],"normalizedLabels":["Genie Productions Incorporated"]},{"internal_id":"5","labels":["Mr. Botz"],"normalizedLabels":["Botz"]},{"internal_id":"6","labels":["Sam Kass"],"normalizedLabels":["Sam Kass"]},{"internal_id":"7","labels":["Olga Kluver"],"normalizedLabels":["Olga Kluver"]},{"internal_id":"8","labels":["Suzanne Konigsberg"],"normalizedLabels":["Suzanne Konigsberg"]},{"internal_id":"9","labels":["Joel Lucas"],"normalizedLabels":["Joel Lucas"]},{"internal_id":"10","labels":["Colonel Lutz"],"normalizedLabels":["Lutz"]},{"internal_id":"11","labels":["Howard Marks Advertising"],"normalizedLabels":["Howard Marks Advertising"]},{"internal_id":"12","labels":["Norman Craig & Kummel, Inc."],"normalizedLabels":["Norman Craig & Kummel Incorporated"]},{"internal_id":"13","labels":["Maury Oren"],"normalizedLabels":["Maury Oren"]},{"internal_id":"14","labels":["Ruder and Finn, Inc."],"normalizedLabels":["Ruder and Finn Incorporated"]},{"internal_id":"15","labels":["Alice Schwebke"],"normalizedLabels":["Alice Schwebke"]},{"internal_id":"16","labels":["Jeff Strickler"],"normalizedLabels":["Jeff Strickler"]},{"internal_id":"17","labels":["Nancy Rose Chandler"],"normalizedLabels":["Nancy Rose Chandler"]},{"internal_id":"18","labels":["Barbara Jarvis"],"normalizedLabels":["Barbara Jarvis"]},{"internal_id":"19","labels":["Jim Brady"],"normalizedLabels":["Jim Brady"]},{"internal_id":"20","labels":["Gloria Bryant"],"normalizedLabels":["Gloria Bryant"]},{"internal_id":"21","labels":["Howard Marks"],"normalizedLabels":["Howard Marks"]},{"internal_id":"22","labels":["Mount Sinai Sleep Laboratory"],"normalizedLabels":["Mount Sinai Sleep Laboratory"]},{"internal_id":"23","labels":["Peter Moore"],"normalizedLabels":["Peter Moore"]},{"internal_id":"24","labels":["David Long"],"normalizedLabels":["David Long"]},{"internal_id":"25","labels":["Coltronics"],"normalizedLabels":["Coltronics"]},{"internal_id":"26","labels":["Ditta Agrippa"],"normalizedLabels":["Ditta Agrippa"]},{"internal_id":"27","labels":["Rome"],"normalizedLabels":["Rome"]},{"internal_id":"28","labels":["Downtown Community School"],"normalizedLabels":["Downtown Community School"]},{"internal_id":"29","labels":["Joseph M. Fallica"],"normalizedLabels":["Joseph M. Fallica"]},{"internal_id":"30","labels":["Federated Electronics"],"normalizedLabels":["Federated Electronics"]},{"internal_id":"31","labels":["Flexi-Optics"],"normalizedLabels":["Flexi-Optics"]},{"internal_id":"32","labels":["Rubin Gorowitz"],"normalizedLabels":["Rubin Gorowitz"]},{"internal_id":"33","labels":["Linda Perlman"],"normalizedLabels":["Linda Perlman"]},{"internal_id":"34","labels":["Conrad Pologe"],"normalizedLabels":["Conrad Pologe"]},{"internal_id":"35","labels":["John Powers"],"normalizedLabels":["John Powers"]},{"internal_id":"36","labels":["Ralsen-Grocraft-Andors Press Corp."],"normalizedLabels":["Ralsen-Grocraft-Andors Press Corporation"]},{"internal_id":"37","labels":["Suzan Rolfe"],"normalizedLabels":["Suzan Rolfe"]},{"internal_id":"38","labels":["Robert Rauschenberg","Robert Rauschenberg's","Rauschenberg's","Bob"],"normalizedLabels":["Robert Rauschenberg"]},{"internal_id":"39","labels":["RGA Press"],"normalizedLabels":["RGA Press"]},{"internal_id":"40","labels":["Pontus Hulten"],"normalizedLabels":["Pontus Hulten"]},{"internal_id":"41","labels":["Frank Konigsberg"],"normalizedLabels":["Frank Konigsberg"]},{"internal_id":"42","labels":["Herb Schneider","Herb"],"normalizedLabels":["Herb Schneider"]},{"internal_id":"43","labels":["Ronald Hobbs"],"normalizedLabels":["Ronald Hobbs"]},{"internal_id":"44","labels":["Tom Slater"],"normalizedLabels":["Tom Slater"]},{"internal_id":"45","labels":["Jennifer Tipton"],"normalizedLabels":["Jennifer Tipton"]},{"internal_id":"46","labels":["Beverly Emmonds"],"normalizedLabels":["Beverly Emmonds"]},{"internal_id":"47","labels":["Jey Bell"],"normalizedLabels":["Jey Bell"]},{"internal_id":"48","labels":["Alphonse Schilling"],"normalizedLabels":["Alphonse Schilling"]},{"internal_id":"49","labels":["Sid Gross"],"normalizedLabels":["Sid Gross"]},{"internal_id":"50","labels":["Hartig and Sons"],"normalizedLabels":["Hartig and Sons"]},{"internal_id":"51","labels":["Joanne Santo"],"normalizedLabels":["Joanne Santo"]},{"internal_id":"52","labels":["Thelma Schoonmacher"],"normalizedLabels":["Thelma Schoonmacher"]},{"internal_id":"53","labels":["Philip Idoni"],"normalizedLabels":["Philip Idoni"]},{"internal_id":"54","labels":["Sue Hartnett"],"normalizedLabels":["Sue Hartnett"]},{"internal_id":"55","labels":["Eleanor Howard"],"normalizedLabels":["Eleanor Howard"]},{"internal_id":"56","labels":["I. F. Jackson Electric Co."],"normalizedLabels":["I. F. Jackson Electric Company"]},{"internal_id":"57","labels":["Nina Kaiden"],"normalizedLabels":["Nina Kaiden"]},{"internal_id":"58","labels":["Weltz Ad Service Typography Co."],"normalizedLabels":["Weltz Ad Service Typography Company"]},{"internal_id":"59","labels":["Simone Whitman"],"normalizedLabels":["Simone Whitman"]},{"internal_id":"60","labels":["Georgelle Williams"],"normalizedLabels":["Georgelle Williams"]},{"internal_id":"61","labels":["Per Biorn"],"normalizedLabels":["Per Biorn"]},{"internal_id":"62","labels":["Copenhagen"],"normalizedLabels":["Copenhagen"]},{"internal_id":"63","labels":["Lucinda Childs","Lucinda"],"normalizedLabels":["Lucinda Childs"]},{"internal_id":"64","labels":["TEEM","TEEM system"],"normalizedLabels":["TEEM system"]},{"internal_id":"65","labels":["Yvonne Rainer","Rainer","Yvonne"],"normalizedLabels":["Yvonne Rainer"]},{"internal_id":"66","labels":["John Cage","John Cage's","Cage's"],"normalizedLabels":["John Cage"]},{"internal_id":"67","labels":["Los Angeles"],"normalizedLabels":["Los Angeles"]},{"internal_id":"68","labels":["Merce Cunningham Dance Company","Cunningham Dance Company"],"normalizedLabels":["Merce Cunningham Dance Company"]},{"internal_id":"69","labels":["Silence"],"normalizedLabels":["Silence"]},{"internal_id":"70","labels":["Irfan Camlibel"],"normalizedLabels":["Irfan Camlibel"]},{"internal_id":"71","labels":["Istanbul"],"normalizedLabels":["Istanbul"]},{"internal_id":"72","labels":["Judson Dance Theater"],"normalizedLabels":["Judson Dance Theater"]},{"internal_id":"73","labels":["Sarah Lawrence Cortese"],"normalizedLabels":["Sarah Lawrence Cortese"]},{"internal_id":"74","labels":["Mia Slavenska"],"normalizedLabels":["Mia Slavenska"]},{"internal_id":"75","labels":["Merce Cunningham","Merce Cunningham's","Cunningham"],"normalizedLabels":["Merce Cunningham"]},{"internal_id":"76","labels":["Cecil Coker","Cecil"],"normalizedLabels":["Cecil Coker"]},{"internal_id":"77","labels":["Kewanee"],"normalizedLabels":["Kewanee"]},{"internal_id":"78","labels":["Mississippi"],"normalizedLabels":["Mississippi"]},{"internal_id":"79","labels":["Philharmonic Hall"],"normalizedLabels":["Philharmonic Hall"]},{"internal_id":"80","labels":["Linoleum"],"normalizedLabels":["Linoleum"]},{"internal_id":"81","labels":["Pete Cumminski","Pete"],"normalizedLabels":["Pete Cumminski"]},{"internal_id":"82","labels":["Hasbrouch Heights"],"normalizedLabels":["Hasbrouch Heights"]},{"internal_id":"83","labels":["N.J."],"normalizedLabels":["New Jersey"]},{"internal_id":"84","labels":["Alex Hay","Hay","Alex"],"normalizedLabels":["Alex Hay"]},{"internal_id":"85","labels":["Oyvind Fahlstrom","Oyvind"],"normalizedLabels":["Oyvind Fahlstrom"]},{"internal_id":"86","labels":["Brazil"],"normalizedLabels":["Brazil"]},{"internal_id":"87","labels":["Sweden"],"normalizedLabels":["Sweden"]},{"internal_id":"88","labels":["Italy"],"normalizedLabels":["Italy"]},{"internal_id":"89","labels":["France"],"normalizedLabels":["France"]},{"internal_id":"90","labels":["U.S.A.","U. S."],"normalizedLabels":["United States of America"]},{"internal_id":"91","labels":["Venice Biennale"],"normalizedLabels":["Venice Biennale"]},{"internal_id":"92","labels":["Stockholm"],"normalizedLabels":["Stockholm"]},{"internal_id":"93","labels":["Kisses Sweeter than Wine"],"normalizedLabels":["Kisses Sweeter than Wine"]},{"internal_id":"94","labels":["America"],"normalizedLabels":["America"]},{"internal_id":"95","labels":["Janis Gallery"],"normalizedLabels":["Janis Gallery"]},{"internal_id":"96","labels":["Ralph Flynn"],"normalizedLabels":["Ralph Flynn"]},{"internal_id":"97","labels":["Andover"],"normalizedLabels":["Andover"]},{"internal_id":"98","labels":["Massachusetts"],"normalizedLabels":["Massachusetts"]},{"internal_id":"99","labels":["Boston"],"normalizedLabels":["Boston"]},{"internal_id":"100","labels":["Fred Waldhauer","Fred"],"normalizedLabels":["Fred Waldhauer"]},{"internal_id":"101","labels":["Florida"],"normalizedLabels":["Florida"]},{"internal_id":"102","labels":["Leo Castelli"],"normalizedLabels":["Leo Castelli"]},{"internal_id":"103","labels":["Deborah Hay","Deborah Hay's"],"normalizedLabels":["Deborah Hay"]},{"internal_id":"104","labels":["Brooklyn"],"normalizedLabels":["Brooklyn"]},{"internal_id":"105","labels":["Europe"],"normalizedLabels":["Europe"]},{"internal_id":"106","labels":["Asia"],"normalizedLabels":["Asia"]},{"internal_id":"107","labels":["Summer 1965"],"normalizedLabels":["Summer 1965"]},{"internal_id":"108","labels":["Ken Harsell"],"normalizedLabels":["Ken Harsell"]},{"internal_id":"109","labels":["Elizabeth"],"normalizedLabels":["Elizabeth"]},{"internal_id":"110","labels":["Larry Heilos","Larry"],"normalizedLabels":["Larry Heilos"]},{"internal_id":"111","labels":["Japan"],"normalizedLabels":["Japan"]},{"internal_id":"112","labels":["Peter Hirsch","Peter"],"normalizedLabels":["Peter Hirsch"]},{"internal_id":"113","labels":["Germany"],"normalizedLabels":["Germany"]},{"internal_id":"114","labels":["Harold Hodges","Harold"],"normalizedLabels":["Harold Hodges"]},{"internal_id":"115","labels":["Jean Tingueley's"],"normalizedLabels":["Jean Tinguely"]},{"internal_id":"116","labels":["self-destructive machine"],"normalizedLabels":["self-destructive machine"]},{"internal_id":"117","labels":["1960"],"normalizedLabels":["1960"]},{"internal_id":"118","labels":["Oracle"],"normalizedLabels":["Oracle"]},{"internal_id":"119","labels":["Bela Julesz"],"normalizedLabels":["Bela Julesz"]},{"internal_id":"120","labels":["Budapest"],"normalizedLabels":["Budapest"]},{"internal_id":"121","labels":["Sensory and Perceptual Processes Department"],"normalizedLabels":["Sensory and Perceptual Processes Department"]},{"internal_id":"122","labels":["Bell Labs","Bell"],"normalizedLabels":["Bell Labs"]},{"internal_id":"123","labels":["Bill Kaminski","Bill"],"normalizedLabels":["Bill Kaminski"]},{"internal_id":"124","labels":["FCC"],"normalizedLabels":["Federal Communications Commission"]},{"internal_id":"125","labels":["Rudy Kerl"],"normalizedLabels":["Rudy Kerl"]},{"internal_id":"126","labels":["Bob Kieronski"],"normalizedLabels":["Bob Kieronski"]},{"internal_id":"127","labels":["Philadelphia"],"normalizedLabels":["Philadelphia"]},{"internal_id":"128","labels":["Vochrome"],"normalizedLabels":["Vochrome"]},{"internal_id":"129","labels":["David Tudor","David's"],"normalizedLabels":["David Tudor"]},{"internal_id":"130","labels":["Louis Maggi","Louis"],"normalizedLabels":["Louis Maggi"]},{"internal_id":"131","labels":["Max Matthews"],"normalizedLabels":["Max Matthews"]},{"internal_id":"132","labels":["Columbus"],"normalizedLabels":["Columbus"]},{"internal_id":"133","labels":["Nebraska"],"normalizedLabels":["Nebraska"]},{"internal_id":"134","labels":["Behaviorial Research Laboratory"],"normalizedLabels":["Behavioral Research Laboratory"]},{"internal_id":"135","labels":["Jim McGee"],"normalizedLabels":["Jim McGee"]},{"internal_id":"136","labels":["Illinois"],"normalizedLabels":["Illinois"]},{"internal_id":"137","labels":["Steve Paxton","Steve","Steve Paxton's"],"normalizedLabels":["Steve Paxton"]},{"internal_id":"138","labels":["Surplus Dance Theater"],"normalizedLabels":["Surplus Dance Theater"]},{"internal_id":"139","labels":["1964"],"normalizedLabels":["1964"]},{"internal_id":"140","labels":["First New York Theater Rally"],"normalizedLabels":["First New York Theater Rally"]},{"internal_id":"141","labels":["1965"],"normalizedLabels":["1965"]},{"internal_id":"142","labels":["John Pierce"],"normalizedLabels":["John Pierce"]},{"internal_id":"143","labels":["Stretch Winslow","Stretch"],"normalizedLabels":["Stretch Winslow"]},{"internal_id":"144","labels":["1925"],"normalizedLabels":["1925"]},{"internal_id":"145","labels":["Port Arthur"],"normalizedLabels":["Port Arthur"]},{"internal_id":"146","labels":["Texas"],"normalizedLabels":["Texas"]},{"internal_id":"147","labels":["1955-65"],"normalizedLabels":["1955-1965"]},{"internal_id":"148","labels":["Paul Taylor","Taylor"],"normalizedLabels":["Paul Taylor"]},{"internal_id":"149","labels":["1957-59"],"normalizedLabels":["1957-1959"]},{"internal_id":"150","labels":["Dunn"],"normalizedLabels":["Dunn"]},{"internal_id":"151","labels":["Collaboration for David Tudor"],"normalizedLabels":["Collaboration for David Tudor"]},{"internal_id":"152","labels":["1961"],"normalizedLabels":["1961"]},{"internal_id":"153","labels":["The Construction of Boston"],"normalizedLabels":["The Construction of Boston"]},{"internal_id":"154","labels":["1962"],"normalizedLabels":["1962"]},{"internal_id":"155","labels":["Pelican"],"normalizedLabels":["Pelican"]},{"internal_id":"156","labels":["1963"],"normalizedLabels":["1963"]},{"internal_id":"157","labels":["Shotput"],"normalizedLabels":["Shotput"]},{"internal_id":"158","labels":["Elgin Tie"],"normalizedLabels":["Elgin Tie"]},{"internal_id":"159","labels":["Spring Training"],"normalizedLabels":["Spring Training"]},{"internal_id":"160","labels":["Map Room I"],"normalizedLabels":["Map Room I"]},{"internal_id":"161","labels":["Map Room II"],"normalizedLabels":["Map Room II"]},{"internal_id":"162","labels":["1966"],"normalizedLabels":["1966"]},{"internal_id":"163","labels":["Open Score"],"normalizedLabels":["Open Score"]},{"internal_id":"164","labels":["9 Evenings"],"normalizedLabels":["9 Evenings"]},{"internal_id":"165","labels":["Robby Robinson","Robby's"],"normalizedLabels":["Robby Robinson"]},{"internal_id":"166","labels":["Atlantic City"],"normalizedLabels":["Atlantic City"]},{"internal_id":"167","labels":["Bebek"],"normalizedLabels":["Bebek"]},{"internal_id":"168","labels":["Turkey"],"normalizedLabels":["Turkey"]},{"internal_id":"169","labels":["Manfred Schroeder","Manfred"],"normalizedLabels":["Manfred Schroeder"]},{"internal_id":"170","labels":["Bell's Acoustics, Speech and Mechanics Research Laboratory"],"normalizedLabels":["Bell Labs Acoustics, Speech and Mechanics Research Laboratory"]},{"internal_id":"171","labels":["Tony Trozzolo","Tony"],"normalizedLabels":["Tony Trozzolo"]},{"internal_id":"172","labels":["Chicago"],"normalizedLabels":["Chicago"]},{"internal_id":"173","labels":["October 7th"],"normalizedLabels":["October 7"]},{"internal_id":"174","labels":["Martin Wazowicz","Marty"],"normalizedLabels":["Martin Wazowicz"]},{"internal_id":"175","labels":["Pennsylvania"],"normalizedLabels":["Pennsylvania"]},{"internal_id":"176","labels":["Robert Whitman"],"normalizedLabels":["Robert Whitman"]},{"internal_id":"177","labels":["Martinique Theater"],"normalizedLabels":["Martinique Theater"]},{"internal_id":"178","labels":["Circle in the Square"],"normalizedLabels":["Circle in the Square"]},{"internal_id":"179","labels":["Manhattan Project"],"normalizedLabels":["Manhattan Project"]},{"internal_id":"180","labels":["Bell Labs' Polymer Research and Development Department"],"normalizedLabels":["Bell Labs Polymer Research and Development Department"]},{"internal_id":"181","labels":["Witt Wittnebert","Witt"],"normalizedLabels":["Witt Wittnebert"]},{"internal_id":"182","labels":["Rahway"],"normalizedLabels":["Rahway"]},{"internal_id":"183","labels":["Billy Kluver"],"normalizedLabels":["Billy Kluver"]},{"internal_id":"184","labels":["Dick Wolff","Dick"],"normalizedLabels":["Dick Wolff"]}]}

      this.statusLabelNormalize = false;

      for (let eId in this.entities){
        let entity = this.entities[eId];

        let lookForId = entity.internal_id;
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



          
      console.log("LLM Response", response)
      return response

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
              <div v-for="type in Object.keys(entitiesByType).sort()">
                <a :href="'#type-'+type" >{{ type }} <span class="lite-text">[{{ entitiesByType[type].length }}]</span></a>
              </div>
            </div>
          </div>
          <div class="column">
            <div class="a-diff">
              <h3 class="title is-4">All Entities Actions</h3>
              <div>





                <button class="button" v-if="!statusLabelNormalize" @click="normalizeLabels()">Normalize Search Labels</button>
                <font-awesome-icon class="spin" v-else  style="font-size: 2em;" :icon="['fas', 'hourglass-half']" />

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

        <table class="table is-striped is-hoverable is-fullwidth">
          <thead>
            <tr>
              <th>Entity</th>
              <th>Wikibase</th>
              <th>Wikidata</th>
              <th>Blocks</th>
              <th>Actions</th>
              <th>Test</th>
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
                  <td v-if="entity.normalizedLabel">

                      <div><input type="radio" @change="entity.useLabel = entity.entity" :value="entity.entity" class="use-label-radio" :id="'label-select-'+entity.internal_id+'-entity'" :name="'label-select-'+entity.internal_id"  :checked="(entity.entity == entity.useLabel)" /><label :for="'label-select-'+entity.internal_id+'-entity'" >{{ entity.entity }}</label></div>
                      <div><input type="radio" @change="entity.useLabel = entity.normalizedLabel" :value="entity.normalizedLabel" class="use-label-radio" :id="'label-select-'+entity.internal_id+'-normalized'" :name="'label-select-'+entity.internal_id"  :checked="(entity.normalizedLabel == entity.useLabel)" /><label :for="'label-select-'+entity.internal_id+'-normalized'" >{{ entity.normalizedLabel }}</label></div>


                  </td>
                  <td v-else>{{ entity.entity }}</td>
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
                  <td>
                    <button class="button" @click="details(entity)">Details</button>
                  </td>
                  <td>
                    <button class="button" @click="runSemlab(entity)">SemLab</button>
                    <button class="button" @click="runWikidata(entity)">Wiki</button>

                  </td>
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
.use-label-radio{
  margin-right: 0.25em;
}
label{
  cursor: pointer;
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