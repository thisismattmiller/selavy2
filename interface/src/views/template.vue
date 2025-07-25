<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/LoginModal.vue'
import { mapWritableState } from "pinia";




export default {
  name: 'WorkLMMReview',
  components: {
    LoginModal
  },
  data() {
    return {

      

      
    }
  },
  computed: {
   
   //  ...mapStores(useUserStore),
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user']),
 
 
   },

   
   
  methods: {
    // Add methods here
    async initialize() {

      
      
      
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
       helllerooo
      </div>
    </div>
      
  </template>


  

  
</template>

<style scoped>


.home{
  padding: 1em;
}

</style>