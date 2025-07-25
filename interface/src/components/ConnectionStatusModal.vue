<template>
        <transition name="modal-fade">
            <div v-if="display" class="modal-overlay">
            <div class="modal-content">
                <div :class="['status-indicator']">
                <h3>Lost connection to the server.<br> Check your internet or the server is down. <br>If it restores this dialog will close.</h3>


            </div>
            </div>
            </div>
        </transition>
</template>

<script>
import { useConnectionStore } from '../stores/connection'

export default {
  name: 'ConnectionStatusModal',
  props: {

    
  },
  data() {
    return {
      connectionStore: useConnectionStore()
    }
  },
  computed: {
    display(){
        if (this.connectionStore.isConnected){
            return false
        } else {
            return true
        }
    }

    
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.modal-content {
  background-color: var(--color-background);
  border-color: var(--color-text);
  padding: 20px;
  border-radius: 8px;
  border-width: 1px;
  border-style: solid;
  max-width: 400px;
  width: 90%;
}

.status-indicator {
  padding: 15px;
  border-radius: 4px;
  text-align: center;
}

.status-indicator.connected {
  background-color: #e6ffe6;
  color: #006400;
}

.status-indicator.disconnected {
  background-color: #fff3e6;
  color: #cc7000;
}

.status-indicator.error {
  background-color: #ffe6e6;
  color: #cc0000;
}

.status-indicator.connecting {
  background-color: #e6f3ff;
  color: #004080;
}

.close-button {
  margin-top: 15px;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  background-color: #4a5568;
  color: white;
  cursor: pointer;
}

.close-button:hover {
  background-color: #2d3748;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>