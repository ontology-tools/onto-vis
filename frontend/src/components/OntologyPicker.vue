<script setup>
defineProps({
  ontologies: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue'])

function toggle(id, selected) {
  emit('update:modelValue', selected.includes(id)
    ? selected.filter((entry) => entry !== id)
    : [...selected, id])
}
</script>

<template>
  <div class="picker">
    <button
      v-for="ontology in ontologies"
      :key="ontology.id"
      type="button"
      class="chip"
      :class="{ 'chip--on': modelValue.includes(ontology.id) }"
      :aria-pressed="modelValue.includes(ontology.id)"
      :title="`${ontology.termCount.toLocaleString()} classes`"
      @click="toggle(ontology.id, modelValue)"
    >
      <span class="chip__name">{{ ontology.id }}</span>
      <span class="chip__count">{{ ontology.termCount.toLocaleString() }}</span>
    </button>
    <p v-if="!ontologies.length" class="hint">No ontologies loaded.</p>
  </div>
</template>

<style scoped>
.picker { display: flex; flex-wrap: wrap; gap: 6px; }

.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  font-size: 12.5px;
  font-weight: 500;
  transition: background 0.12s ease, border-color 0.12s ease, color 0.12s ease;
}
.chip:hover { border-color: var(--border-strong); background: var(--surface-hover); }

.chip--on {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-contrast);
}
.chip--on:hover { background: var(--accent-hover); border-color: var(--accent-hover); }

.chip__count {
  font-size: 10.5px;
  font-variant-numeric: tabular-nums;
  opacity: 0.65;
}
</style>
