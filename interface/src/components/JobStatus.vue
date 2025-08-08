<template>
  
  <div v-if="isVisible" class="card" :class="{ 'deleting': isDeleting }">
    <div class="card-content">
      <button class="delete-button" @click="deleteJob" title="Delete Job">
        <font-awesome-icon :icon="['fas', 'trash']" />
      </button>
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

          <div v-if="job.status=='LLM_MARKUP_ERROR'" class="column">
            <p>THERE WAS AN ERROR WITH LLM PROCESSOR.</p>
            <details>
              <summary>Show Error Details</summary>
              <pre><code>{{ job.error }}</code></pre>
            </details>
          </div>

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
      },
      isVisible: true,
      isDeleting: false
      
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

    deleteJob() {
      const confirmed = confirm(`Are you sure you want to delete the job "${this.job.title}"? This action cannot be undone.`);
      
      if (!confirmed) {
        return;
      }
      
      this.isDeleting = true;
      setTimeout(() => {
        this.isVisible = false;
        this.$emit('delete', this.job.id);
        socket.emit('delete_job', this.job.id);
      }, 400); // Wait for animation to complete
    }
    
  },
  mounted() {
     // Component lifecycle hook when component is mounted

    this.initialize();


     

  }
}
</script>

<style scoped>
.card {
  position: relative;
  transition: all 0.3s ease;
}

.card.deleting {
  animation: deleteFlash 0.4s ease-out;
}

@keyframes deleteFlash {
  0% {
    background-color: inherit;
    opacity: 1;
    transform: scale(1);
  }
  20% {
    background-color: #ff4444;
    transform: scale(1.02);
  }
  40% {
    background-color: #ff6666;
    transform: scale(1);
  }
  100% {
    background-color: #ff8888;
    opacity: 0;
    transform: scale(0.95);
  }
}

.delete-button {
  position: absolute;
  top: 10px;
  right: 10px;
  background: none;
  border: none;
  color: #dc3545;
  cursor: pointer;
  padding: 5px;
  font-size: 1rem;
  opacity: 0.6;
  transition: opacity 0.2s;
  z-index: 10;
}

.delete-button:hover {
  opacity: 1;
}

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

@keyframes flash {
  from {
    opacity: 1;
  }
  to {
    opacity: 0.2; /* Adjust the dimmed opacity */
  }
}
</style>