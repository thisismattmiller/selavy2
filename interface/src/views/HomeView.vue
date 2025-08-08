<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/LoginModal.vue'
import JobStatus from '@/components/JobStatus.vue'

import { mapWritableState } from "pinia";




export default {
  name: 'HomeView',
  components: {
    LoginModal,
    JobStatus
  },
  data() {
    return {

      newJob:false,
      geminiTokenCount: 0,
      geminiTokenLimit: 0,
      docTextChangedTimeout: null,
      apiStatus: null,
      geminiModel: null,
      docText:null,
      jobs: [],
      activeJobsTimer:null,

      uiCounter: 0,
      
      selectedModel: 'gemini-2.5-pro',
      modelOptions: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gpt-5'],
      additionalPromptInstructions: '',
      showAdditionalPrompt: false,


      
    }
  },
  computed: {
   
   //  ...mapStores(useUserStore),
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user']),
 
 
   },

  watch: {
    // Watch for changes in the user store
    isAuthenticated(newValue) {
      if (newValue) {
        this.getJobs();
      }
    }
  },

   
  methods: {
    // Add methods here
    async initialize() {
      
      // Initialize the component      
      // let userNameAvailableInterval = setInterval(() => {
      //   console.log(this.user)
      //   if (this.user) {
      //     clearInterval(userNameAvailableInterval);
      //     this.getJobs();
      //   }
      // }, 100);


      this.getJobs();
      
      this.docText = null;
      this.geminiTokenCount = 0;
      this.geminiTokenLimit = 0;
      this.apiStatus = null;

      
    },

    getJobs() {
      console.log("this.user",this.user)
      this.uiCounter++;
      // Fetch jobs from the server
      socket.emit('jobs_list', { user: this.user }, (response) => {
        console.log(response)
        if (response.success) {
          this.jobs = response.jobs;

          if (this.activeJobsTimer) {
              clearInterval(this.activeJobsTimer);
          }

          if (this.jobs.filter((v) => v.status == 'LLM_MARKING_UP' || v.status=='PRE_LLM_MARKUP').length > 0) {
            this.activeJobsTimer = setInterval(() => {
              this.getJobs();
            }, 5000);
          } 
          

        } else {
          alert("Error fetching jobs");
        }
      })
    },

    processText() {
      
      let docTitle = prompt("Enter a title for this document");
      if (docTitle == null || docTitle == "") {
        alert("Please click again and enter a title for this document");
        return;
      }

      this.apiStatus = 'processing'
      this.newJob = false;
      socket.emit('process_text', { 
        text: this.docText, 
        user: this.user, 
        title: docTitle,
        model: this.selectedModel,
        additionalInstructions: this.additionalPromptInstructions
      }, (response) => {
        console.log("process_text response", response)
        console.log(response)
        this.apiStatus = null;
        this.getJobs()
      })
    },


    docTextChanged(event) {
      // Handle the change event for the textarea
      const text = event.target.value;
      this.apiStatus = 'geminiTokenCount'
      window,clearTimeout(this.docTextChangedTimeout);
      this.docTextChangedTimeout = window.setTimeout(() => {          
        // this.geminiTokenCount = this.calculateGeminiTokenCount(text);
        socket.emit('geminiTokenCount', { text: text }, (response) => {
          this.geminiTokenCount = response.token_count;    
          this.geminiModel = response.model;  
          this.geminiTokenLimit = response.limit;
          this.apiStatus = "tokenCountDone"
          this.docText = text;
        })
      }, 2500);


      

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

      <div class="columns">
        <div class="column">
          <h1 class="is-size-2	">❱Dashboard </h1>
          <hr>

          <button class="button" @click="newJob= (newJob == false) ? true : false">
            <span class="icon is-small">
              <font-awesome-icon :icon="['fas', 'file-circle-plus']" />
            </span>
            <span>Start New Job</span>                          
          </button>
          <template v-if="newJob">


          <div class="columns">
            <div class="column"></div>
            <div class="column is-four-fifths">

              <button class="button is-pulled-right is-success" style="margin-left: 1em;" @click="processText" v-if="apiStatus == 'tokenCountDone' && geminiTokenCount <= geminiTokenLimit">
                <span class="icon is-small">
                  <font-awesome-icon :icon="['fas', 'thumbs-up']" />
                </span>
                <span>Process Document</span>
              </button>



              <div class="dropdown is-hoverable is-pulled-right">

                <div class="dropdown-trigger">                 
                  <button class="button" aria-haspopup="true" aria-controls="dropdown-menu4">



                    <template v-if="apiStatus == 'tokenCountDone'">
                      <span class="icon is-small">
                        <font-awesome-icon :icon="['fas', 'square-binary']" />
                      </span>
                      <span>{{geminiTokenCount}} Total Tokens</span>
                    </template>                   

                    <template v-if="apiStatus == null">
                      <span class="icon is-small">
                        <font-awesome-icon :icon="['fas', 'square-binary']" />
                      </span>
                      <span>Enter Doc Text To Get Started</span>
                    </template>

                    <template v-if="apiStatus == 'geminiTokenCount'">
                      <span class="icon is-small">
                        <font-awesome-icon :icon="['fas', 'spinner']" />
                      </span>
                      <span>Calculating Tokens...</span>
                    </template>


                  </button>
                </div>



                <div class="dropdown-menu" id="dropdown-menu4" role="menu" v-if="apiStatus == null">
                  <div class="dropdown-content">
                    <div class="dropdown-item">
                      <p>
                        After you enter the document text we will calucate the number of tokens in the document and select which model to use.
                      </p>
                    </div>
                  </div>
                </div>

                <div class="dropdown-menu" id="dropdown-menu4" role="menu" v-if="apiStatus == 'tokenCountDone'">
                  <div class="dropdown-content">
                    <div class="dropdown-item">
                      <p>
                        This text has {{geminiTokenCount}} tokens and will be processed using the {{geminiModel}} model. (limit is {{geminiTokenLimit}} tokens))
                      </p>
                    </div>
                  </div>
                </div>


              </div>


            </div>
          </div>
          
          <div class="field" style="margin-top: 1em; margin-bottom: 1em;">
            <label class="label">Select Model</label>
            <div class="control" style="display: flex; align-items: center;">
              <div>
                <template v-for="model in modelOptions" :key="model">
                  <label class="radio" style="margin-right: 1.5em; display: inline-block; padding: 0.25em;">
                    <input type="radio" :value="model" v-model="selectedModel" style="margin-right: 0.5em;">
                    {{ model }}
                  </label>
                </template>
              </div>
              <button class="button is-small is-link is-light" @click="showAdditionalPrompt = !showAdditionalPrompt" style="margin-left: auto; font-size: 0.85rem; padding: 0.25rem 0.5rem;">
                <span class="icon is-small">
                  <font-awesome-icon :icon="['fas', showAdditionalPrompt ? 'chevron-up' : 'chevron-down']" />
                </span>
                <span>{{ showAdditionalPrompt ? 'Hide' : 'Show' }} Additional Instructions</span>
              </button>
            </div>
            <div v-if="showAdditionalPrompt" style="margin-top: 0.5em;">
              <textarea 
                class="textarea-additional" 
                v-model="additionalPromptInstructions"
                placeholder="Enter any additional instructions for the model (optional)"
                rows="3">
              </textarea>
            </div>
          </div>
          
          <textarea class="textarea" @input="docTextChanged"  placeholder="Enter the Text of the document HERE"></textarea>
        </template>



        </div>
        <div class="column">
          
          <h1 class="is-size-2	">&nbsp;</h1>
          <hr>

          <h2 class="is-size-4">❱Your Documents</h2>
          <div v-if="jobs.length==0"> 
            <p style="font-style: italic; padding-left: 1em; padding-top: 1em;">No documents found.</p>
          </div>

          <template v-for="job in jobs" v-bind:key="job.id + '-' + uiCounter">
            <JobStatus :jobId="job.id" :jobData="job"  />
            


            
          </template>

        </div>
      </div>

    </div>
      
  </template>


  

  
</template>

<style scoped>

.content p{
  margin: 0;
}

.home{
  padding: 1em;
}
.textarea{
  min-height: 600px;
}
.textarea-additional{
  min-height: 200px;
  width: 100%;
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