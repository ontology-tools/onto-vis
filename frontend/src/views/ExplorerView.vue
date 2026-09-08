<script setup>
import { computed, inject, onActivated, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { buildGraph, fetchTerm } from '../api.js'
import { LOGO_URL } from '../logo.js'

import GraphView from '../components/GraphView.vue'
import OntologyPicker from '../components/OntologyPicker.vue'
import TagInput from '../components/TagInput.vue'

const { status, ontologies } = inject('ontologyStatus')

const route = useRoute()
const router = useRouter()

/** `?repo=BCIO&include=BCIO:003000,…` — one comma-separated list per field. */
function queryList(value) {
  const joined = Array.isArray(value) ? value.join(',') : value
  return String(joined ?? '').split(',').map((part) => part.trim()).filter(Boolean)
}

// Seeded from the URL so a reload reproduces the same graph. The tag fields need
// whole term objects, so the ids are resolved on mount.
const selectedRepos = ref(queryList(route.query.repo).map((repo) => repo.toUpperCase()))
const include = ref([])
const exclude = ref([])

const graph = ref({ dot: '', nodeCount: 0, edgeCount: 0, focus: [] })
const graphState = ref('idle')
const graphMessage = ref('')

const sidebarOpen = ref(true)
const graphView = ref(null)

let graphRequest = null

const canRender = computed(() => (selectedRepos.value.length > 0 || ontologies.value.length === 1) && graphState.value !== 'loading')
const failedRepos = computed(() => Object.keys(status.value.failed || {}))

const summary = computed(() => {
  if (!graph.value.nodeCount) return ''
  const { nodeCount, edgeCount } = graph.value
  return `${nodeCount.toLocaleString()} classes · ${edgeCount.toLocaleString()} relations`
})

onBeforeUnmount(() => graphRequest?.abort())

/* --------------------------------------------------------- URL round-trip */

/** Turn the ids from the URL into the term objects the tag fields hold. */
async function resolveTerms(ids) {
  const terms = await Promise.all(
    ids.map((id) => fetchTerm(selectedRepos.value, id).catch(() => null))
  )
  return terms.filter(Boolean)
}

onMounted(async () => {
  const includeIds = queryList(route.query.include)
  const excludeIds = queryList(route.query.exclude)
  if (!includeIds.length && !excludeIds.length && !selectedRepos.value.length) return

  const [resolvedInclude, resolvedExclude] = await Promise.all([
    resolveTerms(includeIds),
    resolveTerms(excludeIds)
  ])
  include.value = resolvedInclude
  exclude.value = resolvedExclude

  // A hand-written link may name classes without naming their ontologies.
  if (!selectedRepos.value.length) {
    selectedRepos.value = [...new Set([...resolvedInclude, ...resolvedExclude].map((term) => term.repo))]
  }
  render()
})

// The view is kept alive, so coming back from /contact restores the URL from state.
onActivated(() => writeQuery())

/** Mirror the current selection into the address bar. */
function writeQuery() {
  const query = {}
  if (selectedRepos.value.length) query.repo = selectedRepos.value.join(',')
  if (include.value.length) query.include = include.value.map((tag) => tag.curie).join(',')
  if (exclude.value.length) query.exclude = exclude.value.map((tag) => tag.curie).join(',')

  const same = ['repo', 'include', 'exclude'].every((key) => (route.query[key] ?? '') === (query[key] ?? ''))
  if (same) return
  router.replace({ query })
}

async function render() {
  if (selectedRepos.value.length == 0) {
    if (ontologies.value.length === 1) {
      selectedRepos.value = [ontologies.value[0].id]
    } else {
      graphMessage.value = 'Select at least one ontology.'
      graphState.value = 'error'
      return
    }
  }

  graphRequest?.abort()
  graphRequest = new AbortController()

  graphState.value = 'loading'
  graphMessage.value = ''
  writeQuery()

  const requested = include.value.map((tag) => tag.id)

  try {
    const result = await buildGraph(
      {
        repos: selectedRepos.value,
        include: requested,
        exclude: exclude.value.map((tag) => tag.id)
      },
      { signal: graphRequest.signal }
    )

    if (result.error) {
      graph.value = { dot: '', nodeCount: result.nodeCount ?? 0, edgeCount: 0, focus: [] }
      graphMessage.value = result.error
      graphState.value = 'ready'
      return
    }

    graph.value = { ...result, focus: requested }
    graphState.value = 'ready'
  } catch (error) {
    if (error.name === 'AbortError') return
    graphMessage.value = error.message
    graphState.value = 'error'
  }
}

function reset() {
  include.value = []
  exclude.value = []
  graph.value = { dot: '', nodeCount: 0, edgeCount: 0, focus: [] }
  graphMessage.value = ''
  graphState.value = 'idle'
  writeQuery()
}

function download(format) {
  const svg = graphView.value?.getSvg()
  if (!svg) return

  const name = `${selectedRepos.value.join('-') || 'ontology'}-graph`
  if (format === 'svg') {
    saveBlob(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }), `${name}.svg`)
    return
  }

  const image = new Image()
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
  image.onload = () => {
    const scale = 2
    const canvas = document.createElement('canvas')
    canvas.width = image.width * scale
    canvas.height = image.height * scale
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = getComputedStyle(document.body).backgroundColor
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(image, 0, 0)
    canvas.toBlob((blob) => {
      if (blob) saveBlob(blob, `${name}.png`)
      URL.revokeObjectURL(url)
    })
  }
  image.onerror = () => URL.revokeObjectURL(url)
  image.src = url
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  // The PNG is saved from an async canvas callback, so the download is queued
  // rather than started inline; revoking straight away cancels it.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
</script>

<template>
  <div class="shell" :class="{ 'shell--collapsed': !sidebarOpen }">
    <aside class="sidebar">
      <header class="sidebar__head">
        <RouterLink to="/" class="sidebar__brand">
          <img :src="LOGO_URL" class="brand-logo" />
        </RouterLink>

        <div class="sidebar__actions">
          <RouterLink class="btn btn--ghost sidebar__link" to="/contact">Contact</RouterLink>
        </div>
      </header>

      <div class="sidebar__body scroll-area">
        <section class="block" v-if="ontologies?.length > 1">
          <label class="field-label">Ontologies</label>
          <OntologyPicker v-model="selectedRepos" :ontologies="ontologies" />
          <p v-if="failedRepos.length" class="hint hint--warn">
            Failed to load: {{ failedRepos.join(', ') }}
          </p>
        </section>

        <section class="block">
          <label class="field-label">Classes to show</label>
          <TagInput v-model="include" :repos="selectedRepos" :disabled="!selectedRepos.length && ontologies.length !== 1"
            placeholder="Search by label or ID…" variant="include" />
          <p class="hint">Each class is drawn with its ancestors and all of its descendants. Leave empty for the whole
            ontology.</p>
        </section>

        <section class="block">
          <label class="field-label">Classes to exclude</label>
          <TagInput v-model="exclude" :repos="selectedRepos" :disabled="!selectedRepos.length && ontologies.length !== 1"
            placeholder="Search classes to leave out…" variant="exclude" />
        </section>
      </div>

      <footer class="sidebar__foot">
        <div class="sidebar__buttons">
          <button class="btn btn--primary" :disabled="!canRender" @click="render">
            {{ graphState === 'loading' ? 'Rendering…' : 'Render graph' }}
          </button>
          <button class="btn" :disabled="!include.length && !exclude.length && !graph.dot" @click="reset">Reset</button>
        </div>

        <div v-if="graph.dot" class="sidebar__export">
          <span class="hint">{{ summary }}</span>
          <span class="sidebar__export-buttons">
            <button class="btn btn--ghost" @click="download('svg')">SVG</button>
            <button class="btn btn--ghost" @click="download('png')">PNG</button>
          </span>
        </div>
      </footer>
    </aside>

    <button class="sidebar-toggle" :title="sidebarOpen ? 'Hide panel' : 'Show panel'"
      :aria-label="sidebarOpen ? 'Hide panel' : 'Show panel'" @click="sidebarOpen = !sidebarOpen">{{ sidebarOpen ? '‹' :
        '›' }}</button>

    <main class="canvas">
      <GraphView ref="graphView" :dot="graph.dot" :focus="graph.focus" :status="graphState" :message="graphMessage" />
    </main>
  </div>
</template>

<style scoped lang="scss">
.shell {
  display: grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  height: 100%;
  transition: grid-template-columns 0.22s ease;
}

.shell--collapsed {
  grid-template-columns: 0 1fr;
}

/* --------------------------------------------------------------- sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}

.sidebar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 12px 14px 18px;
  border-bottom: 1px solid var(--border);
}

.sidebar__brand {
  display: block;
  min-width: 0;
}

/* Trimmed so the logo and the actions share the header without wrapping. */
.sidebar__brand .brand-logo {
  max-width: 165px;
}

.sidebar__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: none;
}

.sidebar__link {
  padding: 7px 9px;
  font-size: 12.5px;
  color: var(--text-muted);
}

.sidebar__link:hover {
  color: var(--text);
}

.sidebar__body {
  flex: 1;
  padding: 18px;
}

.block {
  margin-bottom: 24px;
}

.block:last-child {
  margin-bottom: 0;
}

.block .hint {
  margin: 8px 0 0;
  line-height: 1.5;
}

.hint--warn {
  color: var(--danger);
}

.sidebar__foot {
  padding: 14px 18px 16px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.sidebar__buttons {
  display: flex;
  gap: 8px;
}

.sidebar__buttons .btn:first-child {
  flex: 1;
}

.sidebar__export {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
}

.sidebar__export-buttons {
  display: flex;
  gap: 2px;
}

.sidebar__export-buttons .btn {
  padding: 5px 9px;
  font-size: 12px;
}

/* ---------------------------------------------------------------- canvas */
.canvas {
  position: relative;
  min-width: 0;
  height: 100%;
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  left: var(--sidebar-width);
  z-index: 25;
  width: 18px;
  height: 46px;
  margin-top: -23px;
  border: 1px solid var(--border);
  border-left: none;
  border-radius: 0 8px 8px 0;
  background: var(--surface);
  color: var(--text-muted);
  font-size: 15px;
  line-height: 1;
  box-shadow: var(--shadow-sm);
  transition: left 0.22s ease, background 0.12s ease;
}

.sidebar-toggle:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.shell--collapsed .sidebar-toggle {
  left: 0;
}

/* ----------------------------------------------------------------- small */
@media (max-width: 780px) {
  .shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .shell--collapsed {
    grid-template-rows: 0 1fr;
  }

  .sidebar {
    max-height: 62vh;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }

  .sidebar-toggle {
    display: none;
  }
}
</style>
