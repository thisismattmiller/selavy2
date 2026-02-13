<script>
import { socket } from '../socket';
import { mapWritableState } from 'pinia';
import { useUserStore } from '../stores/user';
import LoginModal from '../components/LoginModal.vue';

// Helper function to promisify socket.emit
function asyncEmit(eventName, data) {
  return new Promise(function (resolve, reject) {
    socket.emit(eventName, data, (response) => {
      resolve(response);
    });
  });
}

export default {
  name: 'WorkPublish',
  components: {
    LoginModal
  },
  data() {
    return {
      documentId: null,
      blocks: {},
      blockIds: [],
      entities: {},
      classMap: {},
      tripleStatements: {},

      // Publish state
      publishState: null,
      currentStep: 1,

      // Step 1: Document
      documentMode: 'search', // 'search' or 'create'
      documentSearchQuery: '',
      documentSearchResults: [],
      documentSearchLoading: false,
      documentSearchTimer: null,
      selectedDocumentQid: null,
      selectedDocumentLabel: '',
      newDocumentLabel: '',
      newDocumentDescription: '',
      documentInstanceOf: [{qid: 'Q19069', label: 'document'}],
      documentProjects: [],
      instanceOfSearchQuery: '',
      instanceOfSearchResults: [],
      instanceOfSearchTimer: null,
      projectSearchQuery: '',
      projectSearchResults: [],
      projectSearchTimer: null,
      isCreatingDocument: false,

      // Step 2: Summarization
      summarizationEnabled: false,
      summarizedTexts: {},
      currentSummarizingBlock: null,
      editingSummaryBlock: null,
      editingSummaryText: '',

      // Step 3: S3 Upload
      s3Uploads: {},
      currentUploadingBlock: null,
      isUploadingAll: false,

      // Step 4: Block Publishing
      publishedBlocks: {},
      currentPublishingBlock: null,
      isPublishingAllBlocks: false,

      // Step 5: Triple Publishing
      publishedStatements: {},
      currentPublishingTriple: null,
      isPublishingAllTriples: false,

      // Undo
      isUndoing: false,
      undoProgress: null,

      // General
      isLoading: true,
      projects: [],
    };
  },

  computed: {
    ...mapWritableState(useUserStore, ['isAuthenticated', 'user', 'login_token']),

    // Check if step 1 is complete (document QID set)
    step1Complete() {
      return !!(this.publishState && this.publishState.documentQid);
    },

    // Check if step 2 is complete (all blocks summarized, or summarization disabled)
    step2Complete() {
      if (!this.step1Complete) return false;
      if (!this.summarizationEnabled) return true;
      return this.blockIds.every(id => this.summarizedTexts[id] && this.summarizedTexts[id].status === 'completed');
    },

    // Check if step 3 is complete (all blocks uploaded)
    step3Complete() {
      if (!this.step1Complete) return false;
      return this.blockIds.every(id => this.s3Uploads[id] && this.s3Uploads[id].status === 'completed');
    },

    // Check if step 4 is complete (all blocks published)
    step4Complete() {
      if (!this.step3Complete) return false;
      return this.blockIds.every(id => this.publishedBlocks[id] && this.publishedBlocks[id].status === 'completed');
    },

    // Check if step 5 is complete (all publishable triples published)
    step5Complete() {
      if (!this.step4Complete) return false;
      return this.allPublishableTriples.every(t => {
        const blockStmts = this.publishedStatements[t.blockId] || [];
        return blockStmts.some(s => s.tripleId === t.triple.id && s.status === 'completed');
      });
    },

    // All active publishable triples across all blocks
    allPublishableTriples() {
      const result = [];
      for (const blockId of this.blockIds) {
        const triples = this.tripleStatements[blockId] || [];
        for (const triple of triples) {
          if (triple.active && triple.propertyQid && (triple.subjectQid || triple.blockSubject !== null && triple.blockSubject !== undefined) && (triple.objectQid || triple.objectLiteral !== null && triple.objectLiteral !== undefined)) {
            result.push({ blockId, triple });
          }
        }
      }
      return result;
    },

    // Has any content been published to wikibase
    hasPublishedContent() {
      return Object.keys(this.publishedBlocks).length > 0 || Object.keys(this.publishedStatements).length > 0;
    },

    // Get projects from entities
    detectedProjects() {
      const projectSet = new Set();
      for (const entityId in this.entities) {
        const entity = this.entities[entityId];
        if (entity.project) {
          if (Array.isArray(entity.project)) {
            entity.project.forEach(p => projectSet.add(JSON.stringify(p)));
          }
        }
      }
      return Array.from(projectSet).map(p => JSON.parse(p));
    }
  },

  methods: {
    async initialize() {
      this.documentId = this.$route.params.id;
      this.isLoading = true;

      try {
        // Load blocks and entities
        const nerResponse = await asyncEmit('get_ner', { user: this.user, doc: this.documentId });
        if (nerResponse && nerResponse.ner) {
          this.blocks = nerResponse.ner.blocks || {};
          this.entities = nerResponse.ner.entities || {};
          this.classMap = nerResponse.class_map || {};
          this.blockIds = Object.keys(this.blocks).sort((a, b) => parseInt(a) - parseInt(b));
        }

        // Load triples
        const triplesResponse = await asyncEmit('get_triples', { documentId: this.documentId, user: this.user });
        if (triplesResponse && triplesResponse.success) {
          this.tripleStatements = triplesResponse.triples || {};
        }

        // Load publish state
        const stateResponse = await asyncEmit('publish_get_state', { user: this.user, doc: this.documentId });
        if (stateResponse && stateResponse.success && stateResponse.publishState) {
          this.publishState = stateResponse.publishState;
          this.currentStep = this.publishState.currentStep || 1;
          this.summarizationEnabled = this.publishState.summarizationEnabled || false;
          this.summarizedTexts = this.publishState.summarizedTexts || {};
          this.s3Uploads = this.publishState.s3Uploads || {};
          this.publishedBlocks = this.publishState.publishedBlocks || {};
          this.publishedStatements = this.publishState.publishedStatements || {};
          if (this.publishState.documentQid) {
            this.selectedDocumentQid = this.publishState.documentQid;
            this.selectedDocumentLabel = this.publishState.documentLabel || '';
          }
          if (this.publishState.projects) {
            this.documentProjects = this.publishState.projects;
          }
        }

        // Detect projects from entities
        this.detectProjectsFromEntities();

      } catch (err) {
        console.error('Error initializing publish view:', err);
      }

      this.isLoading = false;
    },

    detectProjectsFromEntities() {
      // Look through entities for project associations
      const projectSet = new Set();
      for (const entityId in this.entities) {
        const entity = this.entities[entityId];
        if (entity.mintData && entity.mintData.project) {
          const projects = Array.isArray(entity.mintData.project) ? entity.mintData.project : [entity.mintData.project];
          for (const p of projects) {
            if (p && typeof p === 'string') {
              projectSet.add(p);
            } else if (p && p.qid) {
              projectSet.add(JSON.stringify({qid: p.qid, label: p.label || p.qid}));
            }
          }
        }
      }
      if (projectSet.size > 0 && this.documentProjects.length === 0) {
        this.projects = Array.from(projectSet).map(p => {
          try { return JSON.parse(p); } catch(e) { return {qid: p, label: p}; }
        });
      }
    },

    searchDocument() {
      clearTimeout(this.documentSearchTimer);
      if (!this.documentSearchQuery || this.documentSearchQuery.length < 2) {
        this.documentSearchResults = [];
        return;
      }
      this.documentSearchLoading = true;
      this.documentSearchTimer = setTimeout(() => {
        socket.emit('search_semlab_autocomplete', this.documentSearchQuery, (response) => {
          this.documentSearchLoading = false;
          if (response && response.success && response.data && response.data.search) {
            this.documentSearchResults = response.data.search;
          } else {
            this.documentSearchResults = [];
          }
        });
      }, 300);
    },

    selectDocument(item) {
      this.selectedDocumentQid = item.id;
      this.selectedDocumentLabel = item.label;
    },

    async confirmDocument() {
      if (!this.selectedDocumentQid) return;
      this.publishState = this.publishState || {};
      this.publishState.documentQid = this.selectedDocumentQid;
      this.publishState.documentLabel = this.selectedDocumentLabel;
      this.publishState.projects = this.documentProjects;
      this.currentStep = 2;
      await this.savePublishState();
    },

    async createDocument() {
      if (!this.newDocumentLabel) return;
      this.isCreatingDocument = true;

      try {
        const instanceOfQids = this.documentInstanceOf.map(i => i.qid);
        const projectQids = this.documentProjects.map(p => p.qid);

        const response = await asyncEmit('publish_create_document', {
          login_token: this.login_token,
          label: this.newDocumentLabel,
          description: this.newDocumentDescription,
          instanceOf: instanceOfQids,
          projects: projectQids
        });

        if (response && response.success) {
          this.selectedDocumentQid = response.qid;
          this.selectedDocumentLabel = this.newDocumentLabel;
          this.publishState = this.publishState || {};
          this.publishState.documentQid = response.qid;
          this.publishState.documentLabel = this.newDocumentLabel;
          this.publishState.documentInstanceOf = instanceOfQids;
          this.publishState.projects = this.documentProjects;
          this.currentStep = 2;
          await this.savePublishState();
        } else {
          alert('Error creating document: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error creating document: ' + err.message);
      }

      this.isCreatingDocument = false;
    },

    searchInstanceOf() {
      clearTimeout(this.instanceOfSearchTimer);
      if (!this.instanceOfSearchQuery || this.instanceOfSearchQuery.length < 2) {
        this.instanceOfSearchResults = [];
        return;
      }
      this.instanceOfSearchTimer = setTimeout(() => {
        socket.emit('search_semlab_autocomplete', this.instanceOfSearchQuery, (response) => {
          if (response && response.success && response.data && response.data.search) {
            this.instanceOfSearchResults = response.data.search;
          }
        });
      }, 300);
    },

    addInstanceOf(item) {
      if (!this.documentInstanceOf.find(i => i.qid === item.id)) {
        this.documentInstanceOf.push({qid: item.id, label: item.label});
      }
      this.instanceOfSearchQuery = '';
      this.instanceOfSearchResults = [];
    },

    removeInstanceOf(index) {
      if (this.documentInstanceOf[index].qid !== 'Q19069') {
        this.documentInstanceOf.splice(index, 1);
      }
    },

    searchProject() {
      clearTimeout(this.projectSearchTimer);
      if (!this.projectSearchQuery || this.projectSearchQuery.length < 2) {
        this.projectSearchResults = [];
        return;
      }
      this.projectSearchTimer = setTimeout(() => {
        socket.emit('search_semlab_autocomplete', this.projectSearchQuery, (response) => {
          if (response && response.success && response.data && response.data.search) {
            this.projectSearchResults = response.data.search;
          }
        });
      }, 300);
    },

    addProject(item) {
      if (!this.documentProjects.find(p => p.qid === item.id)) {
        this.documentProjects.push({qid: item.id, label: item.label});
      }
      this.projectSearchQuery = '';
      this.projectSearchResults = [];
    },

    removeProject(index) {
      this.documentProjects.splice(index, 1);
    },

    async summarizeBlock(blockId) {
      if (!this.blocks[blockId]) return;
      this.currentSummarizingBlock = blockId;

      try {
        const response = await asyncEmit('publish_summarize_block', {
          user: this.user,
          doc: this.documentId,
          blockId: blockId,
          blockText: this.blocks[blockId].clean
        });

        if (response && response.success) {
          this.summarizedTexts[blockId] = {
            original: this.blocks[blockId].clean,
            summary: response.summary,
            status: 'completed'
          };
          await this.savePublishState();
        } else {
          alert('Error summarizing block: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error summarizing block: ' + err.message);
      }

      this.currentSummarizingBlock = null;
    },

    async summarizeAllBlocks() {
      for (const blockId of this.blockIds) {
        if (!this.summarizedTexts[blockId] || this.summarizedTexts[blockId].status !== 'completed') {
          await this.summarizeBlock(blockId);
        }
      }
    },

    startEditSummary(blockId) {
      this.editingSummaryBlock = blockId;
      this.editingSummaryText = this.summarizedTexts[blockId].summary;
    },

    async saveSummaryEdit(blockId) {
      if (this.summarizedTexts[blockId]) {
        this.summarizedTexts[blockId].summary = this.editingSummaryText;
        await this.savePublishState();
      }
      this.editingSummaryBlock = null;
      this.editingSummaryText = '';
    },

    cancelSummaryEdit() {
      this.editingSummaryBlock = null;
      this.editingSummaryText = '';
    },

    onSummarizationToggle() {
      this.savePublishState();
    },

    async uploadBlockToS3(blockId) {
      this.currentUploadingBlock = blockId;

      try {
        let text, originalText, summarized;

        if (this.summarizationEnabled && this.summarizedTexts[blockId] && this.summarizedTexts[blockId].status === 'completed') {
          text = this.summarizedTexts[blockId].summary;
          originalText = this.blocks[blockId].clean;
          summarized = true;
        } else {
          text = this.blocks[blockId].clean;
          originalText = null;
          summarized = false;
        }

        const response = await asyncEmit('publish_upload_s3', {
          user: this.user,
          doc: this.documentId,
          documentQid: this.publishState.documentQid,
          blockId: blockId,
          text: text,
          originalText: originalText,
          summarized: summarized
        });

        if (response && response.success) {
          this.s3Uploads[blockId] = {
            textUrl: response.textUrl,
            originalUrl: response.originalUrl,
            status: 'completed'
          };
          await this.savePublishState();
        } else {
          alert('Error uploading to S3: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error uploading to S3: ' + err.message);
      }

      this.currentUploadingBlock = null;
    },

    async uploadAllToS3() {
      this.isUploadingAll = true;
      for (const blockId of this.blockIds) {
        if (!this.s3Uploads[blockId] || this.s3Uploads[blockId].status !== 'completed') {
          await this.uploadBlockToS3(blockId);
        }
      }
      this.isUploadingAll = false;
    },

    getBlockEntities(blockId) {
      if (!this.blocks[blockId]) return [];
      const markup = this.blocks[blockId].markup || '';
      const entityIds = new Set();
      const regex = /\{([^|]+)\|([^|]+)\|([^}]+)\}/g;
      let match;
      while ((match = regex.exec(markup)) !== null) {
        entityIds.add(match[2]);
      }
      return Array.from(entityIds)
        .map(id => this.entities[id])
        .filter(e => e && e.qid);
    },

    async publishBlockToWikibase(blockId) {
      this.currentPublishingBlock = blockId;

      try {
        const blockEntities = this.getBlockEntities(blockId);
        const associatedEntityQids = blockEntities.map(e => e.qid).filter(Boolean);
        const projectQids = this.documentProjects.map(p => p.qid);
        const s3Url = this.s3Uploads[blockId] ? this.s3Uploads[blockId].textUrl : '';
        const blockText = this.blocks[blockId] ? (this.blocks[blockId].clean || '') : '';

        const response = await asyncEmit('publish_block_to_wikibase', {
          login_token: this.login_token,
          user: this.user,
          doc: this.documentId,
          blockId: blockId,
          documentQid: this.publishState.documentQid,
          documentLabel: this.publishState.documentLabel || 'Document',
          projects: projectQids,
          s3Url: s3Url,
          associatedEntities: associatedEntityQids,
          blockText: blockText
        });

        if (response && response.success) {
          this.publishedBlocks[blockId] = {
            blockQid: response.blockQid,
            status: 'completed'
          };
          await this.savePublishState();
        } else {
          alert('Error publishing block: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error publishing block: ' + err.message);
      }

      this.currentPublishingBlock = null;
    },

    async publishAllBlocks() {
      this.isPublishingAllBlocks = true;
      for (const blockId of this.blockIds) {
        if (!this.publishedBlocks[blockId] || this.publishedBlocks[blockId].status !== 'completed') {
          await this.publishBlockToWikibase(blockId);
        }
      }
      this.isPublishingAllBlocks = false;
    },

    async unpublishBlock(blockId) {
      if (!this.publishedBlocks[blockId]) return;
      if (!confirm(`Unpublish block ${blockId}? This will delete its statements and block item from Wikibase.`)) return;

      this.currentPublishingBlock = blockId;

      try {
        const blockQid = this.publishedBlocks[blockId].blockQid;
        const statements = this.publishedStatements[blockId] || [];

        const response = await asyncEmit('publish_unpublish_block', {
          login_token: this.login_token,
          blockQid: blockQid,
          statements: statements
        });

        if (response && response.success) {
          delete this.publishedBlocks[blockId];
          delete this.publishedStatements[blockId];
          await this.savePublishState();
        } else {
          alert('Error unpublishing block: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error unpublishing block: ' + err.message);
      }

      this.currentPublishingBlock = null;
    },

    getBlockActiveTriples(blockId) {
      const triples = this.tripleStatements[blockId] || [];
      return triples.filter(t =>
        t.active &&
        t.propertyQid &&
        (t.subjectQid || (t.blockSubject !== null && t.blockSubject !== undefined)) &&
        (t.objectQid || (t.objectLiteral !== null && t.objectLiteral !== undefined))
      );
    },

    getTriplePublishStatus(blockId, tripleId) {
      const blockStmts = this.publishedStatements[blockId] || [];
      return blockStmts.find(s => s.tripleId === tripleId && s.status === 'completed');
    },

    async publishTriple(blockId, triple) {
      this.currentPublishingTriple = triple.id;

      try {
        const blockQid = this.publishedBlocks[blockId] ? this.publishedBlocks[blockId].blockQid : null;
        if (!blockQid) {
          alert('Block must be published first');
          this.currentPublishingTriple = null;
          return;
        }

        // If the triple uses blockSubject, use the block QID as subject
        const subjectQid = (triple.blockSubject !== null && triple.blockSubject !== undefined)
          ? (this.publishedBlocks[triple.blockSubject] ? this.publishedBlocks[triple.blockSubject].blockQid : triple.subjectQid)
          : triple.subjectQid;

        const response = await asyncEmit('publish_triple_to_wikibase', {
          login_token: this.login_token,
          user: this.user,
          doc: this.documentId,
          blockQid: blockQid,
          triple: {
            id: triple.id,
            subjectQid: subjectQid,
            propertyQid: triple.propertyQid,
            objectQid: triple.objectQid,
            objectLiteral: triple.objectLiteral,
            contexts: triple.contexts || []
          }
        });

        if (response && response.success) {
          if (!this.publishedStatements[blockId]) {
            this.publishedStatements[blockId] = [];
          }
          this.publishedStatements[blockId].push({
            tripleId: triple.id,
            statementId: response.statementId,
            claimGuid: response.claimGuid,
            subjectQid: response.subjectQid,
            status: 'completed'
          });
          await this.savePublishState();
        } else {
          alert('Error publishing triple: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error publishing triple: ' + err.message);
      }

      this.currentPublishingTriple = null;
    },

    async unpublishTriple(blockId, tripleId) {
      const blockStmts = this.publishedStatements[blockId] || [];
      const stmt = blockStmts.find(s => s.tripleId === tripleId);
      if (!stmt) return;

      if (!confirm('Unpublish this triple? The statement will be deleted from Wikibase.')) return;

      this.currentPublishingTriple = tripleId;

      try {
        const response = await asyncEmit('publish_unpublish_triple', {
          login_token: this.login_token,
          subjectQid: stmt.subjectQid,
          claimGuid: stmt.claimGuid
        });

        if (response && response.success) {
          this.publishedStatements[blockId] = blockStmts.filter(s => s.tripleId !== tripleId);
          await this.savePublishState();
        } else {
          alert('Error unpublishing triple: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error unpublishing triple: ' + err.message);
      }

      this.currentPublishingTriple = null;
    },

    async publishAllTriplesForBlock(blockId) {
      const triples = this.getBlockActiveTriples(blockId);
      for (const triple of triples) {
        if (!this.getTriplePublishStatus(blockId, triple.id)) {
          await this.publishTriple(blockId, triple);
        }
      }
    },

    async publishAllTriples() {
      this.isPublishingAllTriples = true;
      for (const blockId of this.blockIds) {
        await this.publishAllTriplesForBlock(blockId);
      }
      this.isPublishingAllTriples = false;
    },

    async undoPublish() {
      if (!confirm('This will delete all published statements and blocks from Wikibase. S3 uploads will be preserved. Continue?')) return;

      this.isUndoing = true;
      this.undoProgress = null;

      socket.on('publish_undo_progress', (data) => {
        this.undoProgress = data;
      });

      try {
        const response = await asyncEmit('publish_undo', {
          login_token: this.login_token,
          user: this.user,
          doc: this.documentId,
          publishState: {
            publishedStatements: this.publishedStatements,
            publishedBlocks: this.publishedBlocks
          }
        });

        if (response && response.success) {
          this.publishedStatements = {};
          this.publishedBlocks = {};
          this.currentStep = 4;
          await this.savePublishState();
          alert('Undo complete. Deleted ' + response.deletedStatements + ' statements and ' + response.deletedBlocks + ' blocks.');
        } else {
          alert('Error during undo: ' + (response ? response.error : 'Unknown error'));
        }
      } catch (err) {
        alert('Error during undo: ' + err.message);
      }

      socket.off('publish_undo_progress');
      this.isUndoing = false;
      this.undoProgress = null;
    },

    async savePublishState() {
      const state = {
        documentId: this.documentId,
        documentQid: this.publishState ? this.publishState.documentQid : this.selectedDocumentQid,
        documentLabel: this.publishState ? this.publishState.documentLabel : this.selectedDocumentLabel,
        documentInstanceOf: this.publishState ? this.publishState.documentInstanceOf : this.documentInstanceOf.map(i => i.qid),
        projects: this.documentProjects,
        summarizationEnabled: this.summarizationEnabled,
        summarizedTexts: this.summarizedTexts,
        s3Uploads: this.s3Uploads,
        publishedBlocks: this.publishedBlocks,
        publishedStatements: this.publishedStatements,
        currentStep: this.currentStep,
        updatedAt: new Date().toISOString()
      };
      this.publishState = state;

      await asyncEmit('publish_save_state', {
        user: this.user,
        doc: this.documentId,
        publishState: state
      });
    },

    goToStep(step) {
      // Can always go back, but can only advance if previous step is complete
      if (step <= this.currentStep) {
        this.currentStep = step;
        return;
      }
      switch(step) {
        case 2: if (this.step1Complete) this.currentStep = step; break;
        case 3: if (this.step2Complete) this.currentStep = step; break;
        case 4: if (this.step3Complete) this.currentStep = step; break;
        case 5: if (this.step4Complete || Object.keys(this.publishedBlocks).length > 0) this.currentStep = step; break;
      }
      this.savePublishState();
    }
  },

  watch: {
    user(newUser, oldUser) {
      if (newUser && !oldUser) {
        this.initialize();
      }
    }
  },

  mounted() {
    if (this.user) {
      this.initialize();
    }
  }
};
</script>

<template>
  <LoginModal v-if="!isAuthenticated"/>
  <div v-else class="section">
    <div class="container">
      <!-- Back link and title -->
      <div class="level">
        <div class="level-left">
          <router-link to="/" class="button is-light is-small">
            <span class="icon"><font-awesome-icon :icon="['fas', 'arrow-left']" /></span>
            <span>Dashboard</span>
          </router-link>
        </div>
        <div class="level-right" v-if="hasPublishedContent">
          <button class="button is-danger is-outlined is-small" @click="undoPublish" :disabled="isUndoing">
            <span class="icon"><font-awesome-icon :icon="['fas', 'undo']" /></span>
            <span>{{ isUndoing ? 'Undoing...' : 'Undo Published' }}</span>
          </button>
        </div>
      </div>

      <h1 class="title">Publish Document</h1>

      <div v-if="isLoading" class="has-text-centered">
        <span class="icon is-large"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
        <p>Loading document data...</p>
      </div>

      <div v-else>
        <!-- STEP 1: Connect/Create Document -->
        <div class="box" :class="{'step-active': currentStep === 1, 'step-complete': step1Complete && currentStep !== 1}">
          <div class="step-header" @click="goToStep(1)" style="cursor:pointer;">
            <span class="tag is-rounded" :class="step1Complete ? 'is-success' : (currentStep === 1 ? 'is-info' : 'is-light')">1</span>
            <strong style="margin-left:0.5rem;">Connect or Create Document</strong>
            <span v-if="step1Complete" style="margin-left:0.5rem;" class="has-text-success">
              <font-awesome-icon :icon="['fas', 'check-circle']" /> <a :href="'https://base.semlab.io/wiki/Item:' + publishState.documentQid" target="_blank">{{ publishState.documentQid }}</a>
            </span>
          </div>

          <div v-if="currentStep === 1" class="step-content" style="margin-top:1rem;">
            <!-- Mode toggle -->
            <div class="tabs is-toggle is-small" style="margin-bottom:1rem;">
              <ul>
                <li :class="{'is-active': documentMode === 'search'}">
                  <a @click="documentMode = 'search'">Search Existing</a>
                </li>
                <li :class="{'is-active': documentMode === 'create'}">
                  <a @click="documentMode = 'create'">Create New</a>
                </li>
              </ul>
            </div>

            <!-- Search mode -->
            <div v-if="documentMode === 'search'">
              <div class="field">
                <label class="label">Search Wikibase for Document</label>
                <div class="control has-icons-right">
                  <input class="input" type="text" v-model="documentSearchQuery" @input="searchDocument" placeholder="Search by name...">
                  <span class="icon is-right" v-if="documentSearchLoading">
                    <font-awesome-icon :icon="['fas', 'spinner']" spin />
                  </span>
                </div>
              </div>
              <div v-if="documentSearchResults.length > 0" class="search-results">
                <div v-for="item in documentSearchResults" :key="item.id" class="search-result-item" @click="selectDocument(item)" :class="{'is-selected': selectedDocumentQid === item.id}">
                  <strong>{{ item.label }}</strong> <span class="tag is-light is-small">{{ item.id }}</span>
                  <p v-if="item.description" class="is-size-7 has-text-grey">{{ item.description }}</p>
                </div>
              </div>
              <button v-if="selectedDocumentQid" class="button is-primary" style="margin-top:1rem;" @click="confirmDocument">
                Use {{ selectedDocumentQid }} ({{ selectedDocumentLabel }})
              </button>
            </div>

            <!-- Create mode -->
            <div v-if="documentMode === 'create'">
              <div class="field">
                <label class="label">Document Name</label>
                <input class="input" type="text" v-model="newDocumentLabel" placeholder="Enter document name">
              </div>
              <div class="field">
                <label class="label">Description (optional)</label>
                <input class="input" type="text" v-model="newDocumentDescription" placeholder="Enter description">
              </div>

              <!-- Instance Of -->
              <div class="field">
                <label class="label">Instance Of (P1)</label>
                <div class="tags">
                  <span v-for="(inst, idx) in documentInstanceOf" :key="idx" class="tag is-info is-medium">
                    {{ inst.label }} ({{ inst.qid }})
                    <button v-if="inst.qid !== 'Q19069'" class="delete is-small" @click="removeInstanceOf(idx)"></button>
                  </span>
                </div>
                <div class="control">
                  <input class="input is-small" type="text" v-model="instanceOfSearchQuery" @input="searchInstanceOf" placeholder="Search to add more instance of...">
                </div>
                <div v-if="instanceOfSearchResults.length > 0" class="search-results">
                  <div v-for="item in instanceOfSearchResults" :key="item.id" class="search-result-item" @click="addInstanceOf(item)">
                    <strong>{{ item.label }}</strong> <span class="tag is-light is-small">{{ item.id }}</span>
                  </div>
                </div>
              </div>

              <!-- Projects -->
              <div class="field">
                <label class="label">Projects (P11)</label>
                <div class="tags">
                  <span v-for="(proj, idx) in documentProjects" :key="idx" class="tag is-warning is-medium">
                    {{ proj.label }} ({{ proj.qid }})
                    <button class="delete is-small" @click="removeProject(idx)"></button>
                  </span>
                </div>
                <div class="control">
                  <input class="input is-small" type="text" v-model="projectSearchQuery" @input="searchProject" placeholder="Search to add project...">
                </div>
                <div v-if="projectSearchResults.length > 0" class="search-results">
                  <div v-for="item in projectSearchResults" :key="item.id" class="search-result-item" @click="addProject(item)">
                    <strong>{{ item.label }}</strong> <span class="tag is-light is-small">{{ item.id }}</span>
                  </div>
                </div>
              </div>

              <button class="button is-primary" @click="createDocument" :disabled="!newDocumentLabel || isCreatingDocument" style="margin-top:1rem;">
                <span class="icon" v-if="isCreatingDocument"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
                <span>{{ isCreatingDocument ? 'Creating...' : 'Create Document' }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- BLOCKS OVERVIEW (shown after step 1) -->
        <div v-if="step1Complete" class="box" style="margin-bottom:1rem;">
          <h3 class="subtitle is-5">Blocks Overview</h3>
          <div v-for="blockId in blockIds" :key="'overview-'+blockId" class="block-overview-item" style="border-bottom: 1px solid #eee; padding: 0.5rem 0;">
            <div class="columns is-vcentered">
              <div class="column is-1">
                <span class="tag is-dark">{{ blockId }}</span>
              </div>
              <div class="column">
                <p class="is-size-7" style="max-height:3em;overflow:hidden;">{{ blocks[blockId] ? blocks[blockId].clean.substring(0, 200) : '' }}...</p>
              </div>
              <div class="column is-2">
                <span class="tag is-info is-light">{{ getBlockActiveTriples(blockId).length }} triples</span>
              </div>
              <div class="column is-3">
                <span v-if="publishedBlocks[blockId]" class="tag is-success is-light">
                  <font-awesome-icon :icon="['fas', 'check']" style="margin-right:0.25rem;" />
                  <a :href="'https://base.semlab.io/wiki/Item:' + publishedBlocks[blockId].blockQid" target="_blank">{{ publishedBlocks[blockId].blockQid }}</a>
                </span>
                <span v-else class="tag is-light">Not published</span>
              </div>
            </div>
          </div>
        </div>

        <!-- STEP 2: Fair Use Summarize -->
        <div v-if="step1Complete" class="box" :class="{'step-active': currentStep === 2, 'step-complete': step2Complete && currentStep !== 2}">
          <div class="step-header" @click="goToStep(2)" style="cursor:pointer;">
            <span class="tag is-rounded" :class="step2Complete ? 'is-success' : (currentStep === 2 ? 'is-info' : 'is-light')">2</span>
            <strong style="margin-left:0.5rem;">Fair Use Summarize</strong>
            <span v-if="!summarizationEnabled" class="tag is-light is-small" style="margin-left:0.5rem;">Disabled</span>
          </div>

          <div v-if="currentStep === 2" class="step-content" style="margin-top:1rem;">
            <div class="field">
              <label class="checkbox">
                <input type="checkbox" v-model="summarizationEnabled" @change="onSummarizationToggle">
                Enable Fair Use Summarization
              </label>
              <p class="help">When enabled, block text will be summarized into bullet points using LLM. The original text is preserved for S3 upload.</p>
            </div>

            <div v-if="summarizationEnabled">
              <div class="level">
                <div class="level-left">
                  <button class="button is-info is-small" @click="summarizeAllBlocks" :disabled="currentSummarizingBlock !== null">
                    <span class="icon" v-if="currentSummarizingBlock !== null"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
                    <span>Summarize All Blocks</span>
                  </button>
                </div>
              </div>

              <div v-for="blockId in blockIds" :key="'sum-'+blockId" class="block-summary-item" style="margin-top:1rem; border: 1px solid #ddd; border-radius:4px; padding:1rem;">
                <div class="level" style="margin-bottom:0.5rem;">
                  <div class="level-left">
                    <span class="tag is-dark">Block {{ blockId }}</span>
                    <span v-if="summarizedTexts[blockId] && summarizedTexts[blockId].status === 'completed'" class="tag is-success is-light" style="margin-left:0.5rem;">
                      <font-awesome-icon :icon="['fas', 'check']" />
                    </span>
                  </div>
                  <div class="level-right">
                    <button class="button is-small" @click="summarizeBlock(blockId)" :disabled="currentSummarizingBlock !== null">
                      <span class="icon" v-if="currentSummarizingBlock == blockId"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
                      <span>{{ summarizedTexts[blockId] ? 'Rerun' : 'Summarize' }}</span>
                    </button>
                  </div>
                </div>

                <div class="columns">
                  <div class="column">
                    <label class="label is-small">Original Text</label>
                    <div class="content is-small" style="max-height:300px; overflow-y:auto; background:#f5f5f5; padding:0.75rem; border-radius:4px;">
                      <p style="white-space:pre-wrap;">{{ blocks[blockId] ? blocks[blockId].clean : '' }}</p>
                    </div>
                  </div>
                  <div class="column">
                    <label class="label is-small">Summary
                      <span v-if="summarizedTexts[blockId] && editingSummaryBlock !== blockId">
                        <a class="is-size-7" @click="startEditSummary(blockId)">Edit</a>
                      </span>
                    </label>
                    <div v-if="currentSummarizingBlock == blockId" class="has-text-centered" style="padding:2rem;">
                      <font-awesome-icon :icon="['fas', 'spinner']" spin size="2x" />
                      <p class="is-size-7" style="margin-top:0.5rem;">Summarizing...</p>
                    </div>
                    <div v-else-if="editingSummaryBlock === blockId">
                      <textarea class="textarea is-small" v-model="editingSummaryText" rows="10"></textarea>
                      <div class="buttons is-small" style="margin-top:0.5rem;">
                        <button class="button is-small is-success" @click="saveSummaryEdit(blockId)">Save</button>
                        <button class="button is-small" @click="cancelSummaryEdit">Cancel</button>
                      </div>
                    </div>
                    <div v-else-if="summarizedTexts[blockId]" class="content is-small" style="max-height:300px; overflow-y:auto; background:#f0f9f0; padding:0.75rem; border-radius:4px;">
                      <p style="white-space:pre-wrap;">{{ summarizedTexts[blockId].summary }}</p>
                    </div>
                    <div v-else class="has-text-grey is-size-7" style="padding:1rem;">
                      Not yet summarized
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button class="button is-primary" style="margin-top:1rem;" @click="goToStep(3)" :disabled="!step2Complete">
              Continue to S3 Upload
            </button>
          </div>
        </div>

        <!-- STEP 3: Upload to S3 -->
        <div v-if="step1Complete" class="box" :class="{'step-active': currentStep === 3, 'step-complete': step3Complete && currentStep !== 3}">
          <div class="step-header" @click="goToStep(3)" style="cursor:pointer;">
            <span class="tag is-rounded" :class="step3Complete ? 'is-success' : (currentStep === 3 ? 'is-info' : 'is-light')">3</span>
            <strong style="margin-left:0.5rem;">Upload to S3</strong>
          </div>

          <div v-if="currentStep === 3" class="step-content" style="margin-top:1rem;">
            <button class="button is-info" @click="uploadAllToS3" :disabled="isUploadingAll || step3Complete">
              <span class="icon" v-if="isUploadingAll"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
              <span>{{ isUploadingAll ? 'Uploading...' : 'Upload All Blocks' }}</span>
            </button>

            <table class="table is-fullwidth is-striped" style="margin-top:1rem;">
              <thead>
                <tr>
                  <th>Block</th>
                  <th>Text URL</th>
                  <th>Original URL</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="blockId in blockIds" :key="'s3-'+blockId">
                  <td><span class="tag is-dark">{{ blockId }}</span></td>
                  <td>
                    <span v-if="s3Uploads[blockId]" class="is-size-7">{{ s3Uploads[blockId].textUrl }}</span>
                    <span v-else class="has-text-grey is-size-7">-</span>
                  </td>
                  <td>
                    <span v-if="s3Uploads[blockId] && s3Uploads[blockId].originalUrl" class="is-size-7">{{ s3Uploads[blockId].originalUrl }}</span>
                    <span v-else class="has-text-grey is-size-7">-</span>
                  </td>
                  <td>
                    <span v-if="s3Uploads[blockId] && s3Uploads[blockId].status === 'completed'" class="tag is-success is-light">
                      <font-awesome-icon :icon="['fas', 'check']" />
                    </span>
                    <span v-else-if="currentUploadingBlock == blockId" class="tag is-info is-light">
                      <font-awesome-icon :icon="['fas', 'spinner']" spin />
                    </span>
                    <span v-else class="tag is-light">Pending</span>
                  </td>
                  <td>
                    <button class="button is-small" @click="uploadBlockToS3(blockId)" :disabled="isUploadingAll || currentUploadingBlock !== null">
                      Upload
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <button class="button is-primary" style="margin-top:1rem;" @click="goToStep(4)" :disabled="!step3Complete">
              Continue to Publish Blocks
            </button>
          </div>
        </div>

        <!-- STEP 4: Publish Blocks to Wikibase -->
        <div v-if="step1Complete" class="box" :class="{'step-active': currentStep === 4, 'step-complete': step4Complete && currentStep !== 4}">
          <div class="step-header" @click="goToStep(4)" style="cursor:pointer;">
            <span class="tag is-rounded" :class="step4Complete ? 'is-success' : (currentStep === 4 ? 'is-info' : 'is-light')">4</span>
            <strong style="margin-left:0.5rem;">Publish Blocks to Wikibase</strong>
          </div>

          <div v-if="currentStep === 4" class="step-content" style="margin-top:1rem;">
            <button class="button is-info" @click="publishAllBlocks" :disabled="isPublishingAllBlocks || step4Complete">
              <span class="icon" v-if="isPublishingAllBlocks"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
              <span>{{ isPublishingAllBlocks ? 'Publishing...' : 'Publish All Blocks' }}</span>
            </button>

            <table class="table is-fullwidth is-striped" style="margin-top:1rem;">
              <thead>
                <tr>
                  <th>Block</th>
                  <th>Block QID</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="blockId in blockIds" :key="'pub-'+blockId">
                  <td><span class="tag is-dark">{{ blockId }}</span></td>
                  <td>
                    <a v-if="publishedBlocks[blockId]" :href="'https://base.semlab.io/wiki/Item:' + publishedBlocks[blockId].blockQid" target="_blank">{{ publishedBlocks[blockId].blockQid }}</a>
                    <span v-else class="has-text-grey">-</span>
                  </td>
                  <td>
                    <span v-if="publishedBlocks[blockId] && publishedBlocks[blockId].status === 'completed'" class="tag is-success is-light">
                      <font-awesome-icon :icon="['fas', 'check']" />
                    </span>
                    <span v-else-if="currentPublishingBlock == blockId" class="tag is-info is-light">
                      <font-awesome-icon :icon="['fas', 'spinner']" spin />
                    </span>
                    <span v-else class="tag is-light">Pending</span>
                  </td>
                  <td>
                    <button v-if="!publishedBlocks[blockId] || publishedBlocks[blockId].status !== 'completed'" class="button is-small" @click="publishBlockToWikibase(blockId)" :disabled="isPublishingAllBlocks || currentPublishingBlock !== null">
                      Publish
                    </button>
                    <button v-else class="button is-small is-danger is-outlined" @click="unpublishBlock(blockId)" :disabled="isPublishingAllBlocks || currentPublishingBlock !== null">
                      <span class="icon is-small"><font-awesome-icon :icon="['fas', 'undo']" /></span>
                      <span>Unpublish</span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <button class="button is-primary" style="margin-top:1rem;" @click="goToStep(5)" :disabled="!step4Complete">
              Continue to Build Triples
            </button>
          </div>
        </div>

        <!-- STEP 5: Build Triples -->
        <div v-if="step1Complete" class="box" :class="{'step-active': currentStep === 5, 'step-complete': step5Complete && currentStep !== 5}">
          <div class="step-header" @click="goToStep(5)" style="cursor:pointer;">
            <span class="tag is-rounded" :class="step5Complete ? 'is-success' : (currentStep === 5 ? 'is-info' : 'is-light')">5</span>
            <strong style="margin-left:0.5rem;">Build Triples / Statements</strong>
          </div>

          <div v-if="currentStep === 5" class="step-content" style="margin-top:1rem;">
            <button class="button is-info" @click="publishAllTriples" :disabled="isPublishingAllTriples">
              <span class="icon" v-if="isPublishingAllTriples"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
              <span>{{ isPublishingAllTriples ? 'Publishing...' : 'Publish All Triples' }}</span>
            </button>

            <div v-for="blockId in blockIds" :key="'triple-'+blockId" style="margin-top:1.5rem;">
              <div v-if="getBlockActiveTriples(blockId).length > 0">
                <div class="level">
                  <div class="level-left">
                    <span class="tag is-dark">Block {{ blockId }}</span>
                    <a v-if="publishedBlocks[blockId]" class="tag is-light is-small" style="margin-left:0.5rem;" :href="'https://base.semlab.io/wiki/Item:' + publishedBlocks[blockId].blockQid" target="_blank">{{ publishedBlocks[blockId].blockQid }}</a>
                  </div>
                  <div class="level-right">
                    <button class="button is-small is-info is-outlined" @click="publishAllTriplesForBlock(blockId)" :disabled="isPublishingAllTriples || currentPublishingTriple !== null">
                      Publish Block Triples
                    </button>
                  </div>
                </div>

                <table class="table is-fullwidth is-narrow is-size-7" style="margin-top:0.5rem;">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Property</th>
                      <th>Object</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="triple in getBlockActiveTriples(blockId)" :key="triple.id">
                      <td>
                        <a v-if="triple.subjectQid" :href="'https://base.semlab.io/wiki/Item:' + triple.subjectQid" target="_blank">{{ triple.subjectLabel || triple.subjectQid }}</a>
                        <span v-else>{{ triple.subjectLabel }}</span>
                      </td>
                      <td>{{ triple.propertyLabel }} ({{ triple.propertyQid }})</td>
                      <td>
                        <a v-if="triple.objectQid" :href="'https://base.semlab.io/wiki/Item:' + triple.objectQid" target="_blank">{{ triple.objectLabel || triple.objectQid }}</a>
                        <span v-else>{{ triple.objectLiteral || triple.objectLabel }}</span>
                      </td>
                      <td>
                        <span v-if="getTriplePublishStatus(blockId, triple.id)" class="tag is-success is-light">
                          <font-awesome-icon :icon="['fas', 'check']" />
                        </span>
                        <span v-else-if="currentPublishingTriple === triple.id" class="tag is-info is-light">
                          <font-awesome-icon :icon="['fas', 'spinner']" spin />
                        </span>
                        <span v-else class="tag is-light">Pending</span>
                      </td>
                      <td>
                        <button v-if="!getTriplePublishStatus(blockId, triple.id)" class="button is-small" @click="publishTriple(blockId, triple)" :disabled="isPublishingAllTriples || currentPublishingTriple !== null">
                          Publish
                        </button>
                        <button v-else class="button is-small is-danger is-outlined" @click="unpublishTriple(blockId, triple.id)" :disabled="isPublishingAllTriples || currentPublishingTriple !== null">
                          <span class="icon is-small"><font-awesome-icon :icon="['fas', 'undo']" /></span>
                          <span>Unpublish</span>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <!-- UNDO Section -->
        <div v-if="hasPublishedContent" class="box" style="border: 2px solid #ff3860;">
          <h3 class="subtitle is-5 has-text-danger">Undo Published Content</h3>
          <p class="is-size-7">This will delete all statements and block items from Wikibase. S3 uploads will be preserved.</p>
          <div v-if="undoProgress" class="is-size-7" style="margin:0.5rem 0;">
            Progress: {{ undoProgress.step }} - {{ undoProgress.deleted || 0 }} items processed
          </div>
          <button class="button is-danger" @click="undoPublish" :disabled="isUndoing" style="margin-top:0.5rem;">
            <span class="icon" v-if="isUndoing"><font-awesome-icon :icon="['fas', 'spinner']" spin /></span>
            <span>{{ isUndoing ? 'Undoing...' : 'Undo All Published Content' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-active {
  border-left: 4px solid #3273dc;
}
.step-complete {
  border-left: 4px solid #48c774;
  opacity: 0.85;
}
.step-header {
  display: flex;
  align-items: center;
}
.search-results {
  border: 1px solid #ddd;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 0.25rem;
}
.search-result-item {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
}
.search-result-item:hover {
  background-color: #f5f5f5;
}
.search-result-item.is-selected {
  background-color: #ebf5fb;
}
</style>
