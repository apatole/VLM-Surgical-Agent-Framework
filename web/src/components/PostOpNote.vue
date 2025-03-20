<template>
  <div>
    <!-- Procedure Information Section -->
    <div class="p-4 border border-dark-700 rounded-lg">
      <h3 class="text-lg font-semibold mb-2 text-primary-400">Procedure Information</h3>
      <div class="space-y-2">
        <p class="text-sm"><span class="font-medium text-gray-400">Type:</span> {{ procedureInfo.procedure_type || 'Not specified' }}</p>
        <p class="text-sm"><span class="font-medium text-gray-400">Date:</span> {{ procedureInfo.date || 'Not specified' }}</p>
        <p class="text-sm"><span class="font-medium text-gray-400">Duration:</span> {{ procedureInfo.duration || 'Not specified' }}</p>
        <p class="text-sm"><span class="font-medium text-gray-400">Surgeon:</span> {{ procedureInfo.surgeon || 'Not specified' }}</p>
      </div>
    </div>

    <!-- Findings Section -->
    <div v-if="findings && findings.length > 0" class="p-4 border border-dark-700 rounded-lg mt-4">
      <h3 class="text-lg font-semibold mb-2 text-primary-400">Key Findings</h3>
      <ul class="list-disc list-inside space-y-1 text-sm">
        <li v-for="(finding, index) in findings" :key="index" v-if="finding && finding.trim()">
          {{ finding }}
        </li>
      </ul>
    </div>

    <!-- Timeline Section -->
    <div v-if="hasValidEvents" class="p-4 border border-dark-700 rounded-lg mt-4">
      <h3 class="text-lg font-semibold mb-2 text-primary-400">Procedure Timeline</h3>
      <ul class="list-disc list-inside space-y-1 text-sm">
        <li v-for="(event, index) in validEvents" :key="index">
          <span class="font-medium text-primary-300">{{ event.time || 'Unknown' }}</span>: {{ event.description }}
        </li>
      </ul>
    </div>

    <!-- Complications Section -->
    <div v-if="validComplications.length > 0" class="p-4 border border-dark-700 rounded-lg mt-4">
      <h3 class="text-lg font-semibold mb-2 text-primary-400">Complications</h3>
      <ul class="list-disc list-inside space-y-1 text-sm">
        <li v-for="(complication, index) in validComplications" :key="index">
          {{ complication }}
        </li>
      </ul>
    </div>

    <!-- Message when no content is available -->
    <div v-if="!hasContent" class="p-4 border border-dark-700 rounded-lg mt-4">
      <h3 class="text-lg font-semibold mb-2 text-primary-400">Additional Information</h3>
      <p class="text-sm text-gray-300">
        Insufficient procedure data is available for a detailed summary. 
        For better results, add more annotations and notes during the procedure.
      </p>
    </div>

    <!-- Error state -->
    <div v-if="error" class="p-4 border border-dark-700 rounded-lg mt-4">
      <h3 class="text-lg font-semibold mb-2 text-red-400">Error Generating Summary</h3>
      <p class="text-sm text-gray-300">An error occurred while formatting the procedure summary: {{ error }}</p>
      <p class="text-sm text-gray-400 mt-2">Try adding more annotations and notes to improve summary generation.</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PostOpNote',
  props: {
    postOpNote: {
      type: Object,
      required: true
    },
    error: {
      type: String,
      default: null
    }
  },
  computed: {
    procedureInfo() {
      return this.postOpNote?.procedure_information || {};
    },
    findings() {
      return this.postOpNote?.findings || [];
    },
    timeline() {
      return this.postOpNote?.procedure_timeline || [];
    },
    complications() {
      return this.postOpNote?.complications || [];
    },
    validEvents() {
      return this.timeline.filter(event => event.description && event.description.trim());
    },
    hasValidEvents() {
      return this.validEvents.length > 0;
    },
    validComplications() {
      return this.complications.filter(comp => comp && comp.trim());
    },
    hasContent() {
      return this.findings.length > 0 || this.validEvents.length > 0 || this.validComplications.length > 0;
    }
  }
}
</script>