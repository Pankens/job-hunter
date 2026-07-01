<script setup>
import { computed, reactive, ref, watch } from 'vue'
import JobCard from './components/JobCard.vue'
import jobsData from './data/jobs.json'

const STORAGE_KEY = 'job-hunter:user-state:v1'
const timeOptions = [
  { label: '24 h', value: 24 },
  { label: '36 h', value: 36 },
  { label: '48 h', value: 48 },
  { label: '3 días', value: 72 },
  { label: '7 días', value: 168 },
]
const cities = ['Valencia', 'Paterna', 'Burjassot']

const storedState = (() => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}
  } catch {
    return {}
  }
})()

const userState = reactive({
  applied: storedState.applied || {},
  discarded: storedState.discarded || {},
})
const activePanel = ref('valid')
const filters = reactive({
  maxHours: 168,
  cities: [],
  type: 'all',
  source: 'all',
})

watch(
  userState,
  (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)),
  { deep: true },
)

const availableSources = computed(() => [...new Set(jobsData.jobs.map((job) => job.source))])

function isVisibleByFilters(job) {
  const ageHours = (Date.now() - new Date(job.publishedAt)) / 3_600_000
  return (
    ageHours <= filters.maxHours &&
    (!filters.cities.length || filters.cities.includes(job.city)) &&
    (filters.type === 'all' || job.type === filters.type) &&
    (filters.source === 'all' || job.source === filters.source)
  )
}

const validJobs = computed(() =>
  jobsData.jobs.filter(
    (job) => job.valid && !userState.discarded[job.id] && isVisibleByFilters(job),
  ),
)

const discardedJobs = computed(() =>
  jobsData.jobs
    .filter((job) => !job.valid || userState.discarded[job.id])
    .map((job) =>
      userState.discarded[job.id]
        ? { ...job, reject_reasons: ['Descartada manualmente'] }
        : job,
    )
    .filter(isVisibleByFilters),
)

const currentJobs = computed(() =>
  activePanel.value === 'valid' ? validJobs.value : discardedJobs.value,
)

function toggleCity(city) {
  filters.cities = filters.cities.includes(city)
    ? filters.cities.filter((item) => item !== city)
    : [...filters.cities, city]
}

function toggleApplied(id) {
  if (userState.applied[id]) delete userState.applied[id]
  else userState.applied[id] = new Date().toISOString()
}

function discardJob(id) {
  userState.discarded[id] = new Date().toISOString()
}

function resetFilters() {
  filters.maxHours = 168
  filters.cities = []
  filters.type = 'all'
  filters.source = 'all'
}

function formatGeneratedAt(value) {
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>

<template>
  <div class="app-shell">
    <header class="hero">
      <nav class="nav">
        <a class="brand" href="#" aria-label="Job Hunter, inicio">
          <span class="brand__mark">JH</span>
          <span>job-hunter</span>
        </a>
        <span class="mock-badge">
          {{ jobsData.mode === 'live' ? 'InfoJobs · Live' : 'Modo mock · fallback' }}
        </span>
      </nav>

      <div class="hero__content">
        <p class="eyebrow">Tu búsqueda, sin ruido</p>
        <h1>Ofertas que sí<br /><em>encajan contigo.</em></h1>
        <p class="hero__intro">
          Un panel personal para encontrar oportunidades relevantes en Valencia y alrededores.
        </p>
      </div>

      <div class="stats" aria-label="Resumen de ofertas">
        <div><strong>{{ jobsData.summary.valid }}</strong><span>Válidas</span></div>
        <div><strong>{{ jobsData.summary.discarded }}</strong><span>Descartadas</span></div>
        <div><strong>{{ Object.keys(userState.applied).length }}</strong><span>Aplicadas</span></div>
      </div>
    </header>

    <main>
      <section class="filters" aria-labelledby="filter-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Afinar resultados</p>
            <h2 id="filter-title">Filtros</h2>
          </div>
          <button class="text-button" type="button" @click="resetFilters">Limpiar filtros</button>
        </div>

        <div class="filter-grid">
          <fieldset>
            <legend>Publicada en las últimas</legend>
            <div class="segmented">
              <button
                v-for="option in timeOptions"
                :key="option.value"
                type="button"
                :class="{ active: filters.maxHours === option.value }"
                @click="filters.maxHours = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </fieldset>

          <fieldset>
            <legend>Ciudad</legend>
            <div class="check-list">
              <label v-for="city in cities" :key="city">
                <input
                  type="checkbox"
                  :checked="filters.cities.includes(city)"
                  @change="toggleCity(city)"
                />
                <span>{{ city }}</span>
              </label>
            </div>
          </fieldset>

          <label class="select-field">
            <span>Tipo de oferta</span>
            <select v-model="filters.type">
              <option value="all">Todos los tipos</option>
              <option value="general">General</option>
              <option value="technical">Técnica</option>
            </select>
          </label>

          <label class="select-field">
            <span>Fuente</span>
            <select v-model="filters.source">
              <option value="all">Todas las fuentes</option>
              <option v-for="source in availableSources" :key="source" :value="source">
                {{ source === 'infojobs' ? 'InfoJobs' : source === 'indeed' ? 'Indeed' : 'Mock' }}
              </option>
            </select>
          </label>
        </div>
      </section>

      <section class="results" aria-live="polite">
        <div class="panel-tabs">
          <button
            type="button"
            :class="{ active: activePanel === 'valid' }"
            @click="activePanel = 'valid'"
          >
            Ofertas válidas <span>{{ validJobs.length }}</span>
          </button>
          <button
            type="button"
            :class="{ active: activePanel === 'discarded' }"
            @click="activePanel = 'discarded'"
          >
            Descartadas <span>{{ discardedJobs.length }}</span>
          </button>
        </div>

        <div v-if="currentJobs.length" class="job-grid">
          <JobCard
            v-for="job in currentJobs"
            :key="job.id"
            :job="job"
            :applied="Boolean(userState.applied[job.id])"
            :discarded="activePanel === 'discarded'"
            @toggle-applied="toggleApplied"
            @discard="discardJob"
          />
        </div>
        <div v-else class="empty-state">
          <span>⌁</span>
          <h3>No hay ofertas con estos filtros</h3>
          <p>Prueba a ampliar el rango temporal o limpiar la selección.</p>
        </div>
      </section>
    </main>

    <footer>
      <span>
        {{ jobsData.mode === 'live' ? 'Datos de InfoJobs API' : 'Datos mock · Sin scraping real' }}
      </span>
      <span>Actualizado {{ formatGeneratedAt(jobsData.generatedAt) }}</span>
    </footer>
  </div>
</template>
