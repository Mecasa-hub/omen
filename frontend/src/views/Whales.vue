<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-2">🐋 Whale Tracker</h1>
        <p class="text-sm text-gray-500 mt-1">Track and copy the most profitable Polymarket wallets</p>
      </div>
      <div class="flex items-center gap-3">
        <div class="relative">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input v-model="searchQuery" type="text" placeholder="Search by address..." class="input-dark pl-10 w-64 text-sm" />
        </div>
      </div>
    </div>

    <div class="flex gap-6" :class="selectedWhale ? 'flex-col lg:flex-row' : ''">
      <!-- Whale board -->
      <div class="flex-1">
        <div class="glass-card">
          <WhaleBoard @selectWhale="handleSelectWhale" />
        </div>
      </div>

      <!-- Whale detail panel -->
      <transition name="slide-right">
        <div v-if="selectedWhale" class="lg:w-96 flex-shrink-0">
          <div class="glass-card p-5 sticky top-24">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-semibold text-white">Whale Detail</h3>
              <button @click="selectedWhale = null" class="text-gray-500 hover:text-gray-300 transition-colors">✕</button>
            </div>
            <!-- Whale avatar -->
            <div class="flex items-center gap-3 mb-5">
              <div class="w-12 h-12 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-lg font-bold text-white">
                {{ selectedWhale.address.slice(2, 4).toUpperCase() }}
              </div>
              <div>
                <p class="text-sm font-mono text-gray-300">{{ truncAddr(selectedWhale.address) }}</p>
                <span v-if="selectedWhale.label" class="badge-purple text-[10px]">{{ selectedWhale.label }}</span>
              </div>
            </div>
            <!-- Stats -->
            <div class="grid grid-cols-2 gap-3 mb-5">
              <div class="p-3 rounded-lg bg-dark text-center">
                <div class="text-lg font-bold" :class="selectedWhale.roi >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ selectedWhale.roi >= 0 ? '+' : '' }}{{ selectedWhale.roi.toFixed(1) }}%
                </div>
                <div class="text-[10px] text-gray-500">ROI</div>
              </div>
              <div class="p-3 rounded-lg bg-dark text-center">
                <div class="text-lg font-bold text-white">{{ selectedWhale.winRate.toFixed(0) }}%</div>
                <div class="text-[10px] text-gray-500">Win Rate</div>
              </div>
            </div>
            <!-- Recent activity mock -->
            <h4 class="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Recent Activity</h4>
            <div class="space-y-2">
              <div v-for="act in mockActivity" :key="act.id" class="flex items-center justify-between p-2.5 rounded-lg bg-dark">
                <div class="min-w-0 flex-1">
                  <p class="text-xs text-white truncate">{{ act.question }}</p>
                  <span class="text-[10px]" :class="act.direction === 'YES' ? 'text-green-400' : 'text-red-400'">{{ act.direction }}</span>
                </div>
                <span class="text-xs font-mono text-gray-400">${{ act.amount }}</span>
              </div>
            </div>
            <!-- Action buttons -->
            <div class="flex gap-2 mt-5">
              <button class="flex-1 btn-gold text-sm py-2">🐋 Copy Trades</button>
              <button class="flex-1 btn-ghost text-sm py-2">📊 Full Analysis</button>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WhaleBoard from '@/components/WhaleBoard.vue'

const searchQuery = ref('')
const selectedWhale = ref(null)

const mockActivity = [
  { id: 1, question: 'BTC > $150K by Dec 2026?', direction: 'YES', amount: '2,500' },
  { id: 2, question: 'Fed rate cut April?', direction: 'NO', amount: '1,200' },
  { id: 3, question: 'ETH ETF approved Q2?', direction: 'YES', amount: '3,100' },
  { id: 4, question: 'Trump VP pick Vivek?', direction: 'NO', amount: '800' },
]

function truncAddr(addr) { return addr.slice(0, 6) + '...' + addr.slice(-4) }
function handleSelectWhale(whale) { selectedWhale.value = whale }
</script>

<style scoped>
.slide-right-enter-active, .slide-right-leave-active { transition: all 0.3s ease; }
.slide-right-enter-from, .slide-right-leave-to { opacity: 0; transform: translateX(20px); }
</style>
