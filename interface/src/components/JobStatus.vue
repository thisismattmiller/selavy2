<template>
  
  <div class="card">
    <div class="card-content">
      <div class="content">
        <div class="columns">
          <div class="column">

            <p><strong>{{ job.title }}</strong></p>
            <p > Status: <div v-if="job.status=='LLM_MARKING_UP' || job.status == 'PRE_LLM_MARKUP'"  class="flashing-dot"></div>  {{ job.status }}</p>
            <p style="line-break: anywhere;" v-if="job.status=='LLM_MARKING_UP' || job.status == 'PRE_LLM_MARKUP' || job.status.indexOf('ERROR') > -1"> Percent:   {{ job.status_percent   }}</p>
            <p>Created At: {{ job.created_at }}</p>
          </div>
          <div class="column">
            Workflow Status:
            <template v-if="job.workflow">

              <div v-if="job.workflow.DIFF_REVIEW" class="workflow-status">
                <span class="icon-text">
                  <span class="icon">
                    <font-awesome-icon v-if="job.workflow.DIFF_REVIEW.status == 'NOT_STARTED'" :icon="['fas', 'circle']" />
                    <font-awesome-icon v-if="job.workflow.DIFF_REVIEW.status == 'COMPLETE'" :icon="['fas', 'circle-check']" />
                  </span>
                  <router-link :to="{ name: 'llm-review', params: { documentId: job['id'] } }">
                    Review LLM Markup
                  </router-link>                 
                </span>
              </div>

              <div v-if="job.workflow.NER" class="workflow-status">
                <span class="icon-text">
                  <span class="icon">
                    <font-awesome-icon v-if="job.workflow.NER.status == 'NOT_STARTED'" :icon="['fas', 'circle']" />
                    <font-awesome-icon v-if="job.workflow.NER.status == 'COMPLETE'" :icon="['fas', 'circle-check']" />
                  </span>
                  <router-link :to="{ name: 'ner', params: { documentId: job['id'] } }">
                    NER Review
                  </router-link>                 
                </span>
              </div>

            </template>
            <template v-else>
              <p></p>
            </template>
          </div>
        </div>

      </div>
    </div>
    <!-- <footer class="card-footer" v-if="job.status != 'LLM_MARKING_UP' && job.status != 'PRE_LLM_MARKUP'">
        <a href="#" class="card-footer-item">Work</a>                  
    </footer> -->

    <footer class="card-footer" v-if="job.status == 'LLM_MARKUP_COMPLETE'">
      

      <router-link class="card-footer-item" :to="{ name: 'llm-review', params: { documentId: job['id'] } }">
        Review LLM Markup
      </router-link>


    </footer>

    

  </div>

</template>

<script>

import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import { mapWritableState } from "pinia";



export default {
  name: 'JobStatus',
  props: {
    jobId: {
      type: String,
      required: true
    },
     jobData: {
      type: Object,
      default: () => ({})
     }
  },
  data() {
    return {
      job: {
        id: this.jobId,
        title: "Loading...",
        status: "Loading...",
        status_percent: 0,
        created_at: "Loading..."
      }
      
    }
  },
  computed: {
   
  //  ...mapStores(useUserStore),
   ...mapWritableState(useUserStore, ['isAuthenticated', 'user']),


  },

  watch: {
    // Watch for changes in the user store
    user(newValue) {     
      initialize();
    }
  },

  methods: {
    
    async initialize() {
      // Initialize the component
      console.log("Initializing JobStatus for jobId:", this.jobId);
      socket.emit('get_document_status', {doc:this.jobId, user:this.user}, (response) => {
        console.log("response",response)
        if (response.success) {
          this.job = response.job_data
          this.$emit("jobStatus", this.job);
        }else{
          window.setTimeout(() => {
            this.initialize();
          }, 1000); // Retry after 1 second if the job data is not available


        }
      });
    },


    
  },
  mounted() {
     // Component lifecycle hook when component is mounted

    this.initialize();


     

  }
}
</script>

<style scoped>

.flashing-dot {
  width: 15px; /* Adjust size as needed */
  height: 15px; /* Adjust size as needed */
  background-color: lawngreen;
  border-radius: 50%;
  display: inline-block;
  vertical-align: middle;
  animation: flash 1s infinite alternate; /* Adjust duration as needed */
}
.workflow-status{
  padding-left: 1rem;
}
@media (prefers-color-scheme: dark) {
  
  


}

</style>