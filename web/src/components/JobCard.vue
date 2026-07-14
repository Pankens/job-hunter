<script setup>
import { computed } from 'vue'

const props = defineProps({
  job: { type: Object, required: true },
  applied: { type: Boolean, default: false },
  discarded: { type: Boolean, default: false },
})

defineEmits(['toggle-applied', 'discard'])

const publishedLabel = computed(() => {
  const referenceDate = props.job.publishedAt || props.job.firstSeenAt
  const prefix = props.job.publishedAt ? 'Hace' : 'Vista hace'
  const hours = Math.max(1, Math.round((Date.now() - new Date(referenceDate)) / 3_600_000))
  if (hours < 24) return `${prefix} ${hours} h`
  const days = Math.round(hours / 24)
  return `${prefix} ${days} ${days === 1 ? 'día' : 'días'}`
})

const sourceLabel = computed(() => {
  const labels = {
    greenhouse: 'Greenhouse',
    lever: 'Lever',
    arbeitnow: 'Arbeitnow',
    infojobs: 'InfoJobs',
    indeed: 'Indeed',
    mock: 'Mock',
  }
  return labels[props.job.source] || props.job.source
})
</script>

<template>
  <article class="job-card" :class="{ 'job-card--discarded': discarded }">
    <div class="job-card__topline">
      <span class="source-badge">{{ sourceLabel }}</span>
      <span>{{ publishedLabel }}</span>
    </div>

    <div>
      <p class="job-card__company">{{ job.company }}</p>
      <h3>{{ job.title }}</h3>
      <p class="job-card__location">{{ job.city }} · {{ job.location }}</p>
    </div>

    <p class="job-card__description">{{ job.description }}</p>

    <div class="tag-list">
      <span class="tag">{{ job.type === 'technical' ? 'Técnica' : 'General' }}</span>
      <span v-for="skill in job.matched_skills" :key="skill" class="tag tag--skill">
        {{ skill }}
      </span>
    </div>

    <p v-if="job.salaryText" class="job-card__salary">{{ job.salaryText }}</p>

    <div v-if="discarded && job.reject_reasons.length" class="rejection-box">
      <strong>Motivo de descarte</strong>
      <ul>
        <li v-for="reason in job.reject_reasons" :key="reason">{{ reason }}</li>
      </ul>
    </div>

    <div class="job-card__actions">
      <a class="button button--primary" :href="job.url" target="_blank" rel="noopener noreferrer">
        Ver oferta original
      </a>
      <button
        v-if="!discarded"
        class="button"
        :class="{ 'button--active': applied }"
        type="button"
        @click="$emit('toggle-applied', job.id)"
      >
        {{ applied ? 'Aplicada ✓' : 'Marcar como aplicada' }}
      </button>
      <button
        v-if="!discarded"
        class="button button--danger"
        type="button"
        @click="$emit('discard', job.id)"
      >
        Descartar
      </button>
    </div>
  </article>
</template>
