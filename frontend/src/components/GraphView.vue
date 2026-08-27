<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

const props = defineProps({
  dot: { type: String, default: '' },
  status: { type: String, default: 'idle' }, // idle | loading | ready | error
  message: { type: String, default: '' },
  // Node ids the user actually asked for; the initial view frames these rather
  // than the whole descendant closure, which is often far too wide to read.
  focus: { type: Array, default: () => [] }
})
const viewport = ref(null)
const svgMarkup = shallowRef('')
const renderError = ref('')
const rendering = ref(false)
const panning = ref(false)

const transform = ref({ x: 0, y: 0, scale: 1 })
// Whole ontologies lay out extremely wide, so the floor has to be very low for
// "fit to screen" to genuinely fit them on one screen.
const MIN_SCALE = 0.01
const MAX_SCALE = 8
// Below this, node labels stop being readable and the graph reads as a shape.
const LEGIBLE_SCALE = 0.16
// Opening zoom when framing a selection. Capped below fit-to-view's 1.4 so a
// single selected class still arrives with some of its neighbourhood in view.
const FOCUS_SCALE_CAP = 1

let graphviz = null
let renderToken = 0
// Once the user pans or zooms, stop re-fitting the view under them on resize.
let userAdjusted = false
const naturalSize = ref({ width: 0, height: 0 })

const stageStyle = computed(() => ({
  transform: `translate(${transform.value.x}px, ${transform.value.y}px) scale(${transform.value.scale})`
}))

const zoomPercent = computed(() => {
  const scale = transform.value.scale
  return scale < 0.1 ? scale.toFixed(2).replace(/^0/, '') + '×' : `${Math.round(scale * 100)}%`
})

const busy = computed(() => props.status === 'loading' || rendering.value)
const tooSmallToRead = computed(() => Boolean(svgMarkup.value) && transform.value.scale < LEGIBLE_SCALE)

const emptyState = computed(() => {
  if (busy.value || renderError.value || props.message || svgMarkup.value) return null
  return 'Pick an ontology and the classes you want to see, then render the graph.'
})

/* ------------------------------------------------------------- rendering */

async function loadGraphviz() {
  if (!graphviz) {
    const { Graphviz } = await import('@hpcc-js/wasm-graphviz')
    graphviz = await Graphviz.load()
  }
  return graphviz
}

async function render(dot) {
  const token = ++renderToken
  renderError.value = ''

  if (!dot) {
    svgMarkup.value = ''
    return
  }

  rendering.value = true
  try {
    const engine = await loadGraphviz()
    // Yield once so the spinner paints before the (blocking) layout starts.
    await new Promise((resolve) => requestAnimationFrame(resolve))
    if (token !== renderToken) return

    const svg = engine.layout(dot, 'svg', 'dot')
    if (token !== renderToken) return

    svgMarkup.value = prepareSvg(svg)
    await new Promise((resolve) => requestAnimationFrame(resolve))
    if (token === renderToken) initialView()
  } catch (error) {
    if (token === renderToken) {
      svgMarkup.value = ''
      renderError.value = `Graph layout failed: ${error.message}`
    }
  } finally {
    if (token === renderToken) rendering.value = false
  }
}

/** Strip graphviz's fixed pixel size so the SVG scales with our own transform. */
function prepareSvg(svg) {
  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml')
  const root = doc.documentElement

  const viewBox = (root.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number)
  const width = viewBox[2] || parseFloat(root.getAttribute('width')) || 1000
  const height = viewBox[3] || parseFloat(root.getAttribute('height')) || 800
  naturalSize.value = { width, height }

  root.setAttribute('width', `${width}`)
  root.setAttribute('height', `${height}`)

  // Graphviz paints an opaque background polygon — drop it so the page shows through.
  root.querySelector('g.graph > polygon')?.remove()

  return new XMLSerializer().serializeToString(root)
}

/* ---------------------------------------------------------- view control */

function fitToView(padding = 56) {
  const box = viewport.value?.getBoundingClientRect()
  const { width, height } = naturalSize.value
  if (!box || !width) return

  userAdjusted = false

  const scale = Math.max(MIN_SCALE, Math.min(
    MAX_SCALE,
    (box.width - padding * 2) / width,
    (box.height - padding * 2) / height,
    1.4
  ))

  transform.value = {
    scale,
    x: (box.width - width * scale) / 2,
    y: (box.height - height * scale) / 2
  }
}

/**
 * Frame just the requested classes. Whole-ontology layouts are extreme ribbons
 * (BCIO is ~49:1), so fitting everything lands at ~1% zoom and reads as noise —
 * framing the selection instead opens on something legible.
 */
function fitToNodes(ids, padding = 120) {
  const viewportBox = viewport.value?.getBoundingClientRect()
  const stage = viewport.value?.querySelector('.graph-stage')
  const svg = stage?.querySelector('svg')
  if (!viewportBox || !svg) return false

  const wanted = new Set(ids.map((id) => id.replace(':', '_')))
  const rects = []
  for (const node of svg.querySelectorAll('g.node')) {
    const id = node.querySelector('title')?.textContent?.trim()
    if (id && wanted.has(id)) rects.push(node.getBoundingClientRect())
  }
  if (!rects.length) return false

  // Screen rects -> the stage's own untransformed coordinate space.
  const stageBox = stage.getBoundingClientRect()
  const { scale: current } = transform.value
  const left = (Math.min(...rects.map((r) => r.left)) - stageBox.left) / current
  const top = (Math.min(...rects.map((r) => r.top)) - stageBox.top) / current
  const right = (Math.max(...rects.map((r) => r.right)) - stageBox.left) / current
  const bottom = (Math.max(...rects.map((r) => r.bottom)) - stageBox.top) / current

  const width = Math.max(right - left, 1)
  const height = Math.max(bottom - top, 1)

  const scale = Math.max(MIN_SCALE, Math.min(
    MAX_SCALE,
    (viewportBox.width - padding * 2) / width,
    (viewportBox.height - padding * 2) / height,
    FOCUS_SCALE_CAP
  ))

  userAdjusted = false
  transform.value = {
    scale,
    x: viewportBox.width / 2 - (left + width / 2) * scale,
    y: viewportBox.height / 2 - (top + height / 2) * scale
  }
  return true
}

/** Frame the selection if there is one, otherwise the whole graph. */
function initialView() {
  if (props.focus.length && fitToNodes(props.focus)) return
  fitToView()
}

/** Zoom about a viewport point, so the graph stays put under the cursor. */
function zoomBy(factor, origin) {
  const box = viewport.value?.getBoundingClientRect()
  if (!box) return

  const { x, y, scale } = transform.value
  const next = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale * factor))
  if (next === scale) return

  userAdjusted = true

  const px = origin ? origin.x - box.left : box.width / 2
  const py = origin ? origin.y - box.top : box.height / 2

  transform.value = {
    scale: next,
    x: px - ((px - x) / scale) * next,
    y: py - ((py - y) / scale) * next
  }
}

/* ----------------------------------------------------------- interaction */

let activePointer = null
let dragOrigin = null
let dragged = false

function onPointerDown(event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  // The controls sit inside the viewport; capturing the pointer for a pan would
  // retarget the pointerup and the button would never see a click. Match the
  // controls specifically — graphviz wraps every node's shape in an <a>.
  if (event.target.closest('.graph__controls')) return
  activePointer = event.pointerId
  dragged = false
  panning.value = true
  dragOrigin = { x: event.clientX - transform.value.x, y: event.clientY - transform.value.y }
  viewport.value.setPointerCapture(activePointer)
}

function onPointerMove(event) {
  if (event.pointerId !== activePointer || !dragOrigin) return
  const x = event.clientX - dragOrigin.x
  const y = event.clientY - dragOrigin.y
  // A couple of pixels of slop keeps a click from being read as a drag.
  if (Math.abs(x - transform.value.x) > 2 || Math.abs(y - transform.value.y) > 2) {
    dragged = true
    userAdjusted = true
  }
  transform.value = { ...transform.value, x, y }
}

function onPointerUp(event) {
  if (event.pointerId !== activePointer) return
  viewport.value?.releasePointerCapture?.(activePointer)
  activePointer = null
  dragOrigin = null
  panning.value = false
}

function onWheel(event) {
  event.preventDefault()
  // ctrlKey is a pinch gesture on trackpads, which needs a coarser step.
  const factor = Math.exp(-event.deltaY * (event.ctrlKey ? 0.01 : 0.0018))
  zoomBy(factor, { x: event.clientX, y: event.clientY })
}

function onKeydown(event) {
  if (event.target.closest('input, textarea, [contenteditable]')) return
  if (event.key === '+' || event.key === '=') zoomBy(1.2)
  else if (event.key === '-' || event.key === '_') zoomBy(1 / 1.2)
  else if (event.key === '0') fitToView()
}

/* ------------------------------------------------------------- lifecycle */

watch(() => props.dot, (dot) => render(dot), { immediate: true })

let resizeObserver
onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  resizeObserver = new ResizeObserver(() => {
    if (svgMarkup.value && !userAdjusted) initialView()
  })
  if (viewport.value) resizeObserver.observe(viewport.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  resizeObserver?.disconnect()
})

defineExpose({ fitToView, fitToNodes, zoomBy, getSvg: () => svgMarkup.value })
</script>

<template>
  <div
    ref="viewport"
    class="graph"
    :class="{ 'is-dragging': panning }"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @wheel="onWheel"
  >
    <div class="graph__grid" aria-hidden="true" />

    <!-- Class name is load-bearing: fitToNodes() looks the stage up by it. -->
    <div class="graph-stage" :style="stageStyle" v-html="svgMarkup" />

    <Transition name="fade">
      <div v-if="busy" class="graph__overlay">
        <div class="graph__spinner" />
        <p>{{ rendering ? 'Laying out the graph…' : 'Building the graph…' }}</p>
      </div>
    </Transition>

    <div v-if="renderError || message" class="graph__notice" :class="{ 'graph__notice--error': renderError }">
      {{ renderError || message }}
    </div>

    <p v-else-if="emptyState" class="graph__empty">{{ emptyState }}</p>

    <Transition name="fade">
      <p v-if="tooSmallToRead" class="graph__hint">Zoom in to read the labels</p>
    </Transition>

    <div v-if="svgMarkup" class="graph__controls">
      <button class="btn btn--icon" title="Zoom in (+)" aria-label="Zoom in" @click="zoomBy(1.25)">＋</button>
      <button class="btn btn--icon" title="Zoom out (−)" aria-label="Zoom out" @click="zoomBy(0.8)">－</button>
      <button class="btn btn--icon" title="Fit to screen (0)" aria-label="Fit to screen" @click="fitToView()">⤢</button>
      <span class="graph__zoom mono">{{ zoomPercent }}</span>
    </div>
  </div>
</template>

<style scoped>
.graph {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
  cursor: grab;
  touch-action: none;
  contain: strict;
}
.graph.is-dragging { cursor: grabbing; }

.graph__grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle at 1px 1px, var(--border) 1px, transparent 0);
  background-size: 26px 26px;
  opacity: 0.5;
  pointer-events: none;
}

.graph-stage {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  will-change: transform;
}

.graph-stage :deep(svg) { display: block; overflow: visible; }
/* ---------------------------------------------------------------- states */
.graph__overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 14px;
  background: color-mix(in srgb, var(--bg) 78%, transparent);
  backdrop-filter: blur(2px);
  color: var(--text-muted);
  font-size: 13px;
}
.graph__overlay p { margin: 0; }

.graph__spinner {
  width: 30px;
  height: 30px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.graph__notice,
.graph__empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  max-width: 420px;
  margin: 0;
  padding: 16px 20px;
  text-align: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-md);
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.55;
}
.graph__notice--error {
  border-color: color-mix(in srgb, var(--danger) 45%, transparent);
  color: var(--danger);
}

.graph__hint {
  position: absolute;
  left: 50%;
  bottom: 22px;
  transform: translateX(-50%);
  margin: 0;
  padding: 6px 13px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow-sm);
  color: var(--text-muted);
  font-size: 12px;
  pointer-events: none;
}

/* -------------------------------------------------------------- controls */
.graph__controls {
  position: absolute;
  right: 18px;
  bottom: 18px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow-md);
}
.graph__controls .btn { border-color: transparent; background: transparent; }
.graph__controls .btn:hover { background: var(--surface-hover); }

.graph__zoom {
  min-width: 52px;
  padding-right: 6px;
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
