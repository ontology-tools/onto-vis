<script setup>
import { computed } from 'vue'
import { LOGO_ALT, LOGO_URL } from '../logo.js'

const props = defineProps({
  status: { type: Object, required: true }
})

const total = computed(() => {
  const { loaded = [], pending = [], failed = {} } = props.status
  return loaded.length + pending.length + Object.keys(failed).length
})

const percent = computed(() => {
  if (props.status.state === 'discovering' || !total.value) return null
  return Math.round((props.status.loaded.length / total.value) * 100)
})

const headline = computed(() => ({
  idle: 'Starting up…',
  discovering: 'Finding the BSSO Foundry ontologies…',
  loading: 'Parsing ontologies',
  error: 'Could not start'
}[props.status.state] ?? 'Loading'))
</script>

<template>
  <div class="boot">
    <div class="boot__card">
      <img :src="LOGO_URL" :alt="LOGO_ALT" class="brand-logo boot__logo" />

      <p class="boot__status">{{ headline }}</p>

      <div v-if="status.state !== 'error'" class="boot__bar" :class="{ 'boot__bar--indeterminate': percent === null }">
        <div class="boot__fill" :style="percent === null ? undefined : { width: `${percent}%` }" />
      </div>

      <p v-if="status.current" class="hint">
        Reading <strong>{{ status.current }}</strong>
        <span v-if="percent !== null"> · {{ status.loaded.length }} of {{ total }} done</span>
      </p>

      <p v-if="status.error" class="boot__error">{{ status.error }}</p>

      <ul v-if="status.loaded?.length" class="boot__loaded">
        <li v-for="repo in status.loaded" :key="repo">{{ repo }}</li>
      </ul>

      <p class="boot__note">
        The ontologies are downloaded and parsed once when the server starts. This usually takes a minute or two.
      </p>
    </div>
  </div>
</template>

<style scoped>
.boot {
  display: grid;
  place-items: center;
  height: 100%;
  padding: 24px;
  background:
    radial-gradient(1200px 600px at 50% -10%, color-mix(in srgb, var(--accent) 12%, transparent), transparent),
    var(--bg);
}

.boot__card {
  width: min(440px, 100%);
  padding: 32px;
  text-align: center;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}

.boot__logo { margin: 0 auto 20px; max-width: 240px; }

.boot__status { margin: 0 0 20px; color: var(--text-muted); font-size: 13px; }

.boot__bar {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-2);
}

.boot__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 50%, var(--success)));
  transition: width 0.4s ease;
}

.boot__bar--indeterminate .boot__fill {
  width: 38%;
  animation: sweep 1.3s ease-in-out infinite;
}
@keyframes sweep {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}

.boot__loaded {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 5px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}
.boot__loaded li {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}

.boot__error {
  margin: 16px 0 0;
  color: var(--danger);
  font-size: 13px;
}

.boot__note {
  margin: 22px 0 0;
  color: var(--text-faint);
  font-size: 12px;
  line-height: 1.55;
}

.hint { margin: 12px 0 0; }
</style>
