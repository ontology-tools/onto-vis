<script setup>
import { LOGO_URL } from '../logo.js'
</script>

<template>
  <div class="page">
    <header class="page__head">
      <RouterLink to="/" class="page__brand">
        <img :src="LOGO_URL" class="brand-logo" />
      </RouterLink>

      <div class="page__actions">
        <RouterLink class="btn" to="/">Back to the explorer</RouterLink>
      </div>
    </header>

    <div class="page__body scroll-area">
      <article class="prose">
        <h1>Contact</h1>

        <p>
          The BCIO is intended to be a growing resource and its ongoing development benefits from
          community input. If you have a query or would like to contribute to the BCIO, please
          submit an issue on
          <a href="https://github.com/HumanBehaviourChangeProject/ontologies/issues" target="_blank" rel="noopener">
            <strong>Github</strong>
          </a>
          (you may need create a free account).
        </p>

        <p>Through Github you can submit requests to:</p>
        <ul>
          <li>add new entities</li>
          <li>revise the labels or definitions of existing entities</li>
          <li>add new synonyms or examples</li>
          <li>report typos, errors or bugs</li>
        </ul>

        <p>
          We strongly encourage users to submit issues on Github to allow us to publicly track and
          respond to requests from the community. This is to reflect the
          <a href="https://obofoundry.org/principles/fp-000-summary.html" target="_blank" rel="noopener">
            Open Biological and Biomedical Ontology (OBO) Foundry principles
          </a>
          of good practice in ontology development.
        </p>

        <p>
          For all other queries, please email
          <a href="mailto:humanbehaviourchangeproject@gmail.com">humanbehaviourchangeproject@gmail.com</a>
        </p>
      </article>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
}

.page__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.page__brand { display: block; }
.page__actions { display: flex; align-items: center; gap: 6px; }

.page__body { flex: 1; padding: 48px 24px; }

.prose {
  max-width: 640px;
  margin: 0 auto;
  color: var(--text-muted);
  line-height: 1.7;
}
.prose h1 {
  margin-bottom: 22px;
  color: var(--text);
  font-size: 26px;
}
.prose p { margin: 0 0 16px; }
.prose ul { margin: 0 0 16px; padding-left: 22px; }
.prose li { margin-bottom: 5px; }
.prose strong { color: var(--text); }
</style>
