<template>
  <div class="glass-card p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-600 to-gold-500 flex items-center justify-center text-xl">🤖</div>
        <div>
          <h3 class="text-base font-bold text-white">AutoPilot</h3>
          <p class="text-xs text-gray-500">AI-powered copy trading</p>
        </div>
      </div>
      <!-- Master toggle -->
      <button @click="toggleAutoPilot" class="relative w-14 h-7 rounded-full transition-colors duration-300"
        :class="config.enabled ? 'bg-green-600' : 'bg-gray-700'">
        <span class="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300"
          :class="config.enabled ? 'translate-x-7' : 'translate-x-0.5'" />
      </button>
    </div>

    <div class="space-y-5" :class="{ 'opacity-50 pointer-events-none': !config.enabled }">
      <!-- Whale selection -->
      <div>
        <label class="text-sm font-medium text-gray-300 mb-2 block">Copy Whales</label>
        <div class="flex flex-wrap gap-2">
          <button v-for="w in availableWhales" :key="w.address" @click="toggleWhale(w.address)"
            class="px-3 py-1.5 text-xs rounded-lg border transition-all duration-200"
            :class="config.selectedWhales.includes(w.address) ? 'border-gold-400 bg-gold-500/10 text-gold-300' : 'border-purple-900/30 text-gray-400 hover:border-purple-600/50'">
            🐋 {{ w.label || truncAddr(w.address) }}
          </button>
        </div>
      </div>

      <!-- Max bet slider -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-gray-300">Max Bet per Trade</label>
          <span class="text-sm font-bold text-gold-400">${{ config.maxBet }}</span>
        </div>
        <input type="range" v-model.number="config.maxBet" min="1" max="500" step="1"
          class="w-full h-1.5 rounded-full bg-dark appearance-none cursor-pointer accent-purple-500"
          style="background: linear-gradient(to right, #7C3AED 0%, #7C3AED var(--pct), #1A1127 var(--pct), #1A1127 100%);"
          :style="{ '--pct': (config.maxBet / 500 * 100) + '%' }" />
        <div class="flex justify-between text-[10px] text-gray-600 mt-1"><span>$1</span><span>$250</span><span>$500</span></div>
      </div>

      <!-- Daily limit -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-gray-300">Daily Limit</label>
          <span class="text-sm font-bold text-gold-400">${{ config.dailyLimit }}</span>
        </div>
        <input type="range" v-model.number="config.dailyLimit" min="10" max="5000" step="10"
          class="w-full h-1.5 rounded-full bg-dark appearance-none cursor-pointer accent-purple-500"
          style="background: linear-gradient(to right, #7C3AED 0%, #7C3AED var(--pct), #1A1127 var(--pct), #1A1127 100%);"
          :style="{ '--pct': (config.dailyLimit / 5000 * 100) + '%' }" />
        <div class="flex justify-between text-[10px] text-gray-600 mt-1"><span>$10</span><span>$2500</span><span>$5000</span></div>
      </div>

      <!-- Risk level -->
      <div>
        <label class="text-sm font-medium text-gray-300 mb-2 block">Risk Level</label>
        <div class="grid grid-cols-3 gap-2">
          <button v-for="level in riskLevels" :key="level.id" @click="config.riskLevel = level.id"
            class="p-3 rounded-lg border text-center transition-all duration-200"
            :class="config.riskLevel === level.id ? level.activeClass : 'border-purple-900/30 hover:border-purple-600/40'">
            <span class="text-xl">{{ level.icon }}</span>
            <div class="text-xs font-medium mt-1" :class="config.riskLevel === level.id ? level.textClass : 'text-gray-400'">{{ level.label }}</div>
          </button>
        </div>
      </div>

      <!-- Save button -->
      <button @click="saveConfig" :disabled="saving" class="w-full btn-primary flex items-center justify-center gap-2">
        <span v-if="saving">Saving...</span>
        <span v-else-if="saved">✅ Saved</span>
        <span v-else>Save Configuration</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import * as apiMethods from '@/api.js'

const saving = ref(false)
const saved = ref(false)

const config = reactive({
  enabled: false,
  selectedWhales: [],
  maxBet: 50,
  dailyLimit: 500,
  riskLevel: 'moderate',
})

const availableWhales = [
  { address: '0x1a2b3c4d5e6f7890abcdef1234567890abcdef12', label: 'Degen King' },
  { address: '0x2b3c4d5e6f7890abcdef1234567890abcdef1234', label: 'Smart Money' },
  { address: '0x7890abcdef1234567890abcdef12345678901234', label: 'OG Trader' },
  { address: '0x4d5e6f7890abcdef1234567890abcdef12345678', label: 'Whale Alert' },
]

const riskLevels = [
  { id: 'conservative', label: 'Conservative', icon: '🛡️', activeClass: 'border-green-500 bg-green-900/20', textClass: 'text-green-400' },
  { id: 'moderate', label: 'Moderate', icon: '⚖️', activeClass: 'border-gold-500 bg-gold-900/20', textClass: 'text-gold-400' },
  { id: 'aggressive', label: 'Aggressive', icon: '🔥', activeClass: 'border-red-500 bg-red-900/20', textClass: 'text-red-400' },
]

function truncAddr(addr) { return addr.slice(0, 6) + '...' + addr.slice(-4) }

function toggleWhale(addr) {
  const idx = config.selectedWhales.indexOf(addr)
  if (idx >= 0) config.selectedWhales.splice(idx, 1)
  else config.selectedWhales.push(addr)
}

async function toggleAutoPilot() {
  config.enabled = !config.enabled
  try { await apiMethods.toggleAutoPilot(config.enabled) } catch (err) { console.error('Toggle failed:', err) }
}

async function saveConfig() {
  saving.value = true
  try {
    await apiMethods.updateAutoPilotConfig({ ...config })
    saved.value = true; setTimeout(() => saved.value = false, 2000)
  } catch (err) { console.error('Save failed:', err) }
  finally { saving.value = false }
}

onMounted(async () => {
  try { const res = await apiMethods.getAutoPilotConfig(); Object.assign(config, res.data) } catch (err) { /* use defaults */ }
})
</script>
