<script setup>
import { onBeforeUnmount, onMounted, provide, ref } from 'vue'
import { fetchStatus } from './api.js'

import LoadingScreen from './components/LoadingScreen.vue'

const status = ref({ state: 'idle', loaded: [], pending: [], failed: {}, ready: false })
const ontologies = ref([])

let statusTimer = null

async function pollStatus() {
  try {
    const next = await fetchStatus()
    status.value = next
    ontologies.value = next.repositories ?? []
    if (!next.ready) statusTimer = setTimeout(pollStatus, 1500)
  } catch (error) {
    status.value = { ...status.value, state: 'error', error: error.message }
    statusTimer = setTimeout(pollStatus, 4000)
  }
}

onMounted(pollStatus)
onBeforeUnmount(() => clearTimeout(statusTimer))

// The views read these rather than fetching them again.
provide('ontologyStatus', { status, ontologies })
</script>

<template>
  <LoadingScreen v-if="!status.ready" :status="status" />

  <RouterView v-else v-slot="{ Component }">
    <KeepAlive>
      <component :is="Component" />
    </KeepAlive>
  </RouterView>
</template>
