<script>
import { RouterLink, RouterView } from 'vue-router'
import HelloWorld from './components/HelloWorld.vue'
import { useConnectionStore } from "@/stores/connection";
import { useUserStore } from "@/stores/user";

import { socket } from "@/socket";
import { mapStores, mapState, mapWritableState } from 'pinia'

import ConnectionStatusModal from './components/ConnectionStatusModal.vue'





export default {
  components: {
    HelloWorld,
    RouterLink,
    RouterView,

    ConnectionStatusModal

  },
  data() {
    return {
      count: 0,
      showModal: true,

    }
  },
  computed: {
   
    ...mapStores(useConnectionStore),
    ...mapState(useConnectionStore, ['isConnected']),
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user']),


  },


  methods: {
    increment() {
      this.count++
    }
  },

  created() {
    socket.off();
    // itemStore.bindEvents();
    this.connectionStore.bindEvents();   
  },


  mounted() {

    if (window.localStorage.getItem('selavy-login-token')){
      socket.emit('login_validate', window.localStorage.getItem('selavy-login-token'), (response) => {
        console.log(response)
        if (response.success) {
          this.isAuthenticated = true
          this.user = response.user
          console.log(this.isAuthenticated, this.user)
        }
      })
    }
  }


}




</script>



<template>


  <template v-if="!isConnected">
    <ConnectionStatusModal />
  </template>

  <RouterView />
</template>

<style scoped>
header {
  line-height: 1.5;
  max-height: 100vh;
}

.logo {
  display: block;
  margin: 0 auto 2rem;
}

nav {
  width: 100%;
  font-size: 12px;
  text-align: center;
  margin-top: 2rem;
}

nav a.router-link-exact-active {
  color: var(--color-text);
}

nav a.router-link-exact-active:hover {
  background-color: transparent;
}

nav a {
  display: inline-block;
  padding: 0 1rem;
  border-left: 1px solid var(--color-border);
}

nav a:first-of-type {
  border: 0;
}

@media (min-width: 1024px) {
  header {
    display: flex;
    place-items: center;
    padding-right: calc(var(--section-gap) / 2);
  }

  .logo {
    margin: 0 2rem 0 0;
  }

  header .wrapper {
    display: flex;
    place-items: flex-start;
    flex-wrap: wrap;
  }

  nav {
    text-align: left;
    margin-left: -1rem;
    font-size: 1rem;

    padding: 1rem 0;
    margin-top: 1rem;
  }
}
</style>
