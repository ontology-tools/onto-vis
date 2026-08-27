<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { searchTerms } from '../api.js'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  repos: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Search by label or ID…' },
  variant: { type: String, default: 'include' }, // include | exclude
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const query = ref('')
const results = ref([])
const activeIndex = ref(-1)
const loading = ref(false)
const open = ref(false)
const inputEl = ref(null)
const listEl = ref(null)

let debounceTimer = null
let inFlight = null

const selectedIds = computed(() => new Set(props.modelValue.map((tag) => tag.id)))

const visibleResults = computed(() =>
  results.value.filter((term) => !selectedIds.value.has(term.id))
)

watch(query, (value) => {
  clearTimeout(debounceTimer)
  const term = value.trim()

  if (term.length < 2) {
    results.value = []
    loading.value = false
    open.value = false
    return
  }

  loading.value = true
  debounceTimer = setTimeout(() => runSearch(term), 180)
})

watch(() => props.repos, () => {
  if (query.value.trim().length >= 2) runSearch(query.value.trim())
})

async function runSearch(term) {
  inFlight?.abort()
  inFlight = new AbortController()

  try {
    results.value = await searchTerms(props.repos, term, { signal: inFlight.signal, limit: 30 })
    activeIndex.value = visibleResults.value.length ? 0 : -1
    open.value = true
  } catch (error) {
    if (error.name !== 'AbortError') results.value = []
  } finally {
    if (!inFlight.signal.aborted) loading.value = false
  }
}

function addTag(term) {
  if (!term || selectedIds.value.has(term.id)) return
  emit('update:modelValue', [...props.modelValue, term])
  query.value = ''
  results.value = []
  open.value = false
  activeIndex.value = -1
  nextTick(() => inputEl.value?.focus())
}

function removeTag(id) {
  emit('update:modelValue', props.modelValue.filter((tag) => tag.id !== id))
}

function clearAll() {
  emit('update:modelValue', [])
}

function move(step) {
  const total = visibleResults.value.length
  if (!total) return
  open.value = true
  activeIndex.value = (activeIndex.value + step + total) % total
  nextTick(() => {
    listEl.value?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  })
}

function onEnter(event) {
  if (open.value && activeIndex.value >= 0) {
    event.preventDefault()
    addTag(visibleResults.value[activeIndex.value])
  }
}

function onBackspace() {
  if (query.value === '' && props.modelValue.length) {
    removeTag(props.modelValue[props.modelValue.length - 1].id)
  }
}

/** Accept pasted lists of IDs such as "BCIO:006013, BCIO:006014". */
async function onPaste(event) {
  const text = event.clipboardData?.getData('text') ?? ''
  const ids = text.split(/[,;\n\r\t]+/).map((part) => part.trim()).filter(Boolean)
  if (ids.length < 2) return

  event.preventDefault()
  const found = await Promise.all(
    ids.map((id) => searchTerms(props.repos, id, { limit: 1 }).catch(() => []))
  )
  const additions = []
  const seen = new Set(selectedIds.value)
  for (const [term] of found) {
    if (term && !seen.has(term.id)) {
      seen.add(term.id)
      additions.push(term)
    }
  }
  if (additions.length) emit('update:modelValue', [...props.modelValue, ...additions])
  query.value = ''
}

/** Delay closing so a click on a suggestion still registers. */
function onBlur() {
  setTimeout(() => { open.value = false }, 140)
}

function highlight(text) {
  const term = query.value.trim()
  if (!term) return [{ text, match: false }]

  const index = text.toLowerCase().indexOf(term.toLowerCase())
  if (index === -1) return [{ text, match: false }]

  return [
    { text: text.slice(0, index), match: false },
    { text: text.slice(index, index + term.length), match: true },
    { text: text.slice(index + term.length), match: false }
  ].filter((part) => part.text)
}
</script>

<template>
  <div class="tag-input" :class="[`tag-input--${variant}`, { 'is-disabled': disabled }]">
    <div class="tag-input__box" @click="inputEl?.focus()">
      <TransitionGroup name="tag">
        <span v-for="tag in modelValue" :key="tag.id" class="tag" :title="tag.definition || tag.label">
          <span class="tag__id mono">{{ tag.curie }}</span>
          <span class="tag__label">{{ tag.label }}</span>
          <button
            type="button"
            class="tag__remove"
            :aria-label="`Remove ${tag.label}`"
            @click.stop="removeTag(tag.id)"
          >&times;</button>
        </span>
      </TransitionGroup>

      <input
        ref="inputEl"
        v-model="query"
        class="tag-input__field"
        type="text"
        autocomplete="off"
        spellcheck="false"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        :disabled="disabled"
        :placeholder="modelValue.length ? '' : placeholder"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter="onEnter"
        @keydown.esc="open = false"
        @keydown.delete="onBackspace"
        @paste="onPaste"
        @focus="open = visibleResults.length > 0"
        @blur="onBlur"
      />

      <span v-if="loading" class="tag-input__spinner" aria-hidden="true" />
      <button
        v-else-if="modelValue.length"
        type="button"
        class="tag-input__clear"
        aria-label="Clear all"
        @click.stop="clearAll"
      >&times;</button>
    </div>

    <ul v-if="open && visibleResults.length" ref="listEl" class="suggestions scroll-area" role="listbox">
      <li
        v-for="(term, index) in visibleResults"
        :key="term.id"
        class="suggestion"
        :data-active="index === activeIndex"
        role="option"
        :aria-selected="index === activeIndex"
        @mouseenter="activeIndex = index"
        @mousedown.prevent="addTag(term)"
      >
        <div class="suggestion__head">
          <span class="suggestion__label">
            <span v-for="(part, i) in highlight(term.label)" :key="i" :class="{ mark: part.match }">{{ part.text }}</span>
          </span>
          <span class="suggestion__id mono">{{ term.curie }}</span>
        </div>
        <p v-if="term.definition" class="suggestion__definition">{{ term.definition }}</p>
      </li>
    </ul>

    <p v-else-if="open && !loading && query.trim().length >= 2" class="suggestions suggestions--empty">
      No matching classes in the selected ontologies.
    </p>
  </div>
</template>

<style scoped>
.tag-input { position: relative; }

.tag-input__box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  min-height: 42px;
  padding: 6px 30px 6px 7px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: text;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.tag-input__box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.is-disabled .tag-input__box { opacity: 0.55; pointer-events: none; }

.tag-input__field {
  flex: 1 1 90px;
  min-width: 90px;
  padding: 4px 2px;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
}
.tag-input__field:focus { outline: none; }
.tag-input__field::placeholder { color: var(--text-faint); }

/* ------------------------------------------------------------------ tags */
.tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 3px 4px 3px 8px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.4;
}
.tag-input--include .tag {
  background: var(--accent-soft);
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  color: color-mix(in srgb, var(--accent) 78%, var(--text));
}
.tag-input--exclude .tag {
  background: var(--danger-soft);
  border-color: color-mix(in srgb, var(--danger) 35%, transparent);
  color: color-mix(in srgb, var(--danger) 78%, var(--text));
}

.tag__id { font-size: 10.5px; opacity: 0.75; }
.tag__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 190px;
  font-weight: 500;
}
.tag__remove {
  display: grid;
  place-items: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
  opacity: 0.6;
}
.tag__remove:hover { opacity: 1; background: rgb(0 0 0 / 0.1); }

.tag-enter-active, .tag-leave-active { transition: opacity 0.14s ease, transform 0.14s ease; }
.tag-enter-from, .tag-leave-to { opacity: 0; transform: scale(0.86); }

/* ------------------------------------------------------- box decorations */
.tag-input__clear,
.tag-input__spinner {
  position: absolute;
  top: 12px;
  right: 9px;
}

.tag-input__clear {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: var(--text-faint);
  font-size: 16px;
  line-height: 1;
}
.tag-input__clear:hover { color: var(--text); background: var(--surface-hover); }

.tag-input__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.65s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ----------------------------------------------------------- suggestions */
.suggestions {
  position: absolute;
  z-index: 40;
  top: calc(100% + 5px);
  left: 0;
  right: 0;
  max-height: 320px;
  margin: 0;
  padding: 4px;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.suggestions--empty {
  padding: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.suggestion {
  padding: 7px 9px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.suggestion[data-active='true'] { background: var(--surface-hover); }

.suggestion__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.suggestion__label { font-weight: 500; }
.suggestion__id { flex: none; font-size: 11px; color: var(--text-faint); }

.suggestion__definition {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mark {
  background: color-mix(in srgb, var(--accent) 26%, transparent);
  border-radius: 3px;
}
</style>
