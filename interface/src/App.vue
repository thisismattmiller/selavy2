<script>
import { RouterLink, RouterView } from 'vue-router'
import HelloWorld from './components/HelloWorld.vue'
import { useConnectionStore } from "@/stores/connection";
import { useUserStore } from "@/stores/user";

import { socket, state as socketState } from "@/socket";
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
      socketState,
    }
  },
  computed: {

    ...mapStores(useConnectionStore),
    ...mapState(useConnectionStore, ['isConnected']),
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user','login_token']),


  },


  methods: {
    increment() {
      this.count++
    },
    dismissApiKeyError() {
      socketState.apiKeyError = null;
    },
  },

  created() {
    socket.off();
    // itemStore.bindEvents();
    this.connectionStore.bindEvents();
    // Re-register global listeners that socket.off() cleared
    socket.on("api_key_error", (data) => {
      socketState.apiKeyError = data;
    });
  },


  mounted() {

    if (window.localStorage.getItem('selavy-login-token')){
      console.log("Validating login token...,",window.localStorage.getItem('selavy-login-token'))
      socket.emit('login_validate', window.localStorage.getItem('selavy-login-token'), (response) => {
        console.log(response)
        if (response.success) {
          this.isAuthenticated = true
          this.user = response.user
          this.login_token = window.localStorage.getItem('selavy-login-token')
          console.log(this.isAuthenticated, this.user)
        }
      })
    }
  }


}




</script>



<template>


  <div v-if="socketState.apiKeyError" class="api-key-error-banner">
    <div class="api-key-error-content">
      <strong>API Key Error ({{ socketState.apiKeyError.provider }})</strong>
      <p>{{ socketState.apiKeyError.message }}</p>
      <p>Go to the gear icon on the Dashboard to update or remove your custom API key.</p>
      <button class="button is-small is-dark" @click="dismissApiKeyError">Dismiss</button>
    </div>
  </div>

  <template v-if="!isConnected">
    <ConnectionStatusModal />
  </template>

  <RouterView />
</template>

<style scoped>
.api-key-error-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background-color: #cc0000;
  color: #fff;
  padding: 1rem 2rem;
  z-index: 9999;
  text-align: center;
}
.api-key-error-banner strong {
  font-size: 1.2rem;
}
.api-key-error-banner p {
  margin: 0.25rem 0;
}
.api-key-error-content {
  max-width: 800px;
  margin: 0 auto;
}

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
