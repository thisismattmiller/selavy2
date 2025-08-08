<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/LoginModal.vue'
import { mapWritableState } from "pinia";
import JobStatus from '@/components/JobStatus.vue'




export default {
  name: 'WorkLMMReview',
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

      saveButtonText: "Saved",

            
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

      // console.log("useUserStore().user", useUserStore().user)
      // ask for the document diffs
      socket.emit('get_document_diffs', {doc:this.documentId, user:this.user}, (response) => {
        console.log(response)
        console.log("Hello")
        if (response.success) {
          this.documentDiffs = response.documentDiffs;
          this.documentOrginal = response.documentOrginal;
          this.documentMarkup = response.documentMarkup;
        } else {
          console.error("Error fetching document diffs:", response.error);
        }
      });
      

      socket.emit('get_document_status', {doc:this.documentId, user:this.user}, (response) => {

        if (response.success) {
          console.log("job_data", response.job_data)
        } else {
          console.error("Error fetching document diffs:", response.error);
        }
      });

      
    },

    saveMarkup() {
      // Save the document markup
      socket.emit('update_document_markup', {doc:this.documentId, user:this.user, text_markup:this.documentMarkup}, (response) => {
        if (response.success) {
          console.log("Document markup saved successfully");
          this.saveButtonText = "Saved";
        } else {
          console.error("Error saving document markup:", response.error);
        }
      });
    },


    markComplete() {
      // Mark the job as complete
      socket.emit('update_document_status', {doc:this.documentId, user:this.user, workflow:'DIFF_REVIEW',value:'COMPLETE'}, (response) => {
        if (response.success) {
          console.log("Job marked as complete");
          this.$refs.jobstatus.initialize()
        } else {
          console.error("Error marking job as complete:", response.error);
        }
      });
    },


    async llmJudge() {
      this.judgeStatus = "judging"

      let needToBeJudged = this.documentDiffs.filter(diff => !diff.judgement)
      console.log(needToBeJudged)
      if (needToBeJudged.length == 0){
        this.judgeStatus = "judged"
        console.log("All document diffs have been judged")
        console.log(this.documentDiffs)
      }else{
        socket.emit('judge_diff', needToBeJudged[0], (response) => {
            console.log(response)
            needToBeJudged[0].judgement = response.judgement            
            if (response.success) {

            } else {
              console.error("Error juding document diffs:", response.error);
            }

            this.llmJudge()

          });
      }

      


    },

    onJobStatus(job) {
      // Handle job status updates
      // this.judgeStatus = job.status
      if (job.workflow && job.workflow.DIFF_REVIEW && job.workflow.DIFF_REVIEW.status == 'COMPLETE') {
        this.workflowComplete = true
      } else {
        this.workflowComplete = false
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

            <div class="toolbar">
              <button class="button home-button" @click="$router.push('/')"><font-awesome-icon :icon="['fas', 'arrow-left']" />  <span>Home</span></button>
            </div>
            <div class="toolbar">
              <button class="button" @click="llmJudge">Request LLM Review</button>

              <button class="button" v-if="!workflowComplete" @click="markComplete">Mark as Complete</button>
              <button class="button" v-if="workflowComplete" disabled>Mark as Complete</button>


            </div>
          

          </div>
          <div class="column">

            <JobStatus :jobId="documentId" ref="jobstatus" @jobStatus="onJobStatus"  />

          </div>
        </div>





        <div class="columns a-diff" v-for="(diff, idx) in documentDiffs">
          <div class="column is-1" style="align-content: center; text-align: center;">

            <div v-if="judgeStatus=='judging' &&  !('judgement' in diff)">
              <font-awesome-icon class="spin"  style="font-size: 2em;" :icon="['fas', 'hourglass-half']" />
            </div>
            <div v-else-if="(judgeStatus=='judging' || judgeStatus == 'judged') && diff.judgement && diff.judgement.significantChange === false ">
              <font-awesome-icon class="thumbs-up"  style="font-size: 2em;" :icon="['fas', 'thumbs-up']" />
            </div>
            <div v-else-if="(judgeStatus=='judging' || judgeStatus == 'judged') && diff.judgement && diff.judgement.significantChange === true">
              <font-awesome-icon class="warning"  style="font-size: 2em;" :icon="['fas', 'triangle-exclamation']" />
            </div>

            

            

            


            

          </div>
          <div class="column">
             <div class="diff-example">Change Type: {{ diff.type }}</div>

            <div class="diff-example" v-html="'Original:</br>' + diff.changes_markedup.original"></div>
            <div class="diff-example" v-html="'Processed:</br>' + diff.changes_markedup.processed"></div>

            <div class="judgement-text" v-if="diff.judgement && diff.judgement.reason">
              {{ diff.judgement.reason }}
            </div>

          </div>
        </div>
        <button class="button" @click="saveMarkup">{{ saveButtonText }}</button>
        <textarea v-model="documentMarkup" @input="saveButtonText='Save Markup'" placeholder="Document Diffs"></textarea>


      </div>
    </div>
      
  </template>


  

  
</template>

<style scoped>

.a-diff{
  padding: 1em;
  margin: 1em;
  background-color: whitesmoke;
}
.diff-example{
  font-family: 'Courier New', Courier, monospace;
}

strong{
  background-color: yellow !important;
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


@media (prefers-color-scheme: dark) {
  .a-diff, textarea {
    background-color: #2c2c2c; /* Darker background for dark mode */
    color: #f5f5f5; /* Lighter text for dark mode */
  }
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