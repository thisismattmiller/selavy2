<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h2>
          <font-awesome-icon :icon="['fas', 'gear']" />
          API Key Settings
        </h2>
        <button class="delete-btn" @click="$emit('close')">
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>

      <p class="user-label">User: <strong>{{ user }}</strong></p>

      <div v-if="statusMsg" class="status-msg" :class="statusClass">
        {{ statusMsg }}
      </div>

      <div v-if="hasCustomKey" class="current-key-info">
        <p>You have a custom Google AI API key set.</p>
        <button class="button is-danger is-outlined" @click="removeKey" :disabled="loading">
          <span class="icon is-small">
            <font-awesome-icon :icon="['fas', 'trash']" />
          </span>
          <span>Remove Custom Key</span>
        </button>
      </div>

      <div class="form-group">
        <label for="apiKey">{{ hasCustomKey ? 'Replace' : 'Set' }} Google AI API Key</label>
        <input
          id="apiKey"
          v-model="apiKey"
          type="password"
          placeholder="Enter your Google AI API key"
          :disabled="loading"
        />
      </div>

      <div class="button-row">
        <button class="button" @click="$emit('close')" :disabled="loading">Close</button>
        <button class="button is-success" @click="saveKey" :disabled="loading || !apiKey.trim()">
          <span v-if="loading" class="icon is-small">
            <font-awesome-icon :icon="['fas', 'spinner']" spin />
          </span>
          <span>Save</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { socket } from "@/socket";
import { useUserStore } from '@/stores/user'
import { mapWritableState } from "pinia";

export default {
  name: 'ApiKeyModal',
  emits: ['close'],
  data() {
    return {
      apiKey: '',
      hasCustomKey: false,
      loading: false,
      statusMsg: '',
      statusClass: '',
    }
  },
  computed: {
    ...mapWritableState(useUserStore, ['user']),
  },
  methods: {
    checkStatus() {
      this.loading = true;
      socket.emit('get_user_api_key_status', { user: this.user }, (response) => {
        this.loading = false;
        if (response.success) {
          this.hasCustomKey = response.has_custom_key;
        }
      });
    },
    saveKey() {
      if (!this.apiKey.trim()) return;
      this.loading = true;
      this.statusMsg = '';
      socket.emit('set_user_api_key', { user: this.user, api_key: this.apiKey.trim() }, (response) => {
        this.loading = false;
        if (response.success) {
          this.statusMsg = 'API key saved successfully.';
          this.statusClass = 'success';
          this.hasCustomKey = true;
          this.apiKey = '';
        } else {
          this.statusMsg = response.error || 'Failed to save API key.';
          this.statusClass = 'error';
        }
      });
    },
    removeKey() {
      this.loading = true;
      this.statusMsg = '';
      socket.emit('remove_user_api_key', { user: this.user }, (response) => {
        this.loading = false;
        if (response.success) {
          this.statusMsg = 'Custom API key removed. Using default key.';
          this.statusClass = 'success';
          this.hasCustomKey = false;
          this.apiKey = '';
        } else {
          this.statusMsg = response.error || 'Failed to remove API key.';
          this.statusClass = 'error';
        }
      });
    },
  },
  mounted() {
    this.checkStatus();
  },
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
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background-color: var(--color-background);
  border: 1px solid var(--color-text);
  color: var(--color-text);
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 480px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.modal-header h2 {
  font-weight: bold;
  font-size: 1.25rem;
  margin: 0;
}

.delete-btn {
  background: none;
  border: none;
  color: var(--color-text);
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0.25rem;
}

.delete-btn:hover {
  opacity: 0.7;
}

.user-label {
  margin-bottom: 1rem;
}

.status-msg {
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.status-msg.success {
  background-color: #d4edda;
  color: #155724;
}

.status-msg.error {
  background-color: #f8d7da;
  color: #721c24;
}

.current-key-info {
  padding: 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.current-key-info p {
  margin-bottom: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: monospace;
}

.button-row {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
