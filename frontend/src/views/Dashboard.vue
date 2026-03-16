<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold text-white">Welcome back, {{ authStore.username }} 👋</h1>
        <p class="text-sm text-gray-500 mt-1">Here's your prediction performance overview</p>
      </div>
      <router-link to="/oracle" class="btn-primary flex items-center gap-2">
        🔮 Ask Oracle
      </router-link>
    </div>

    <!-- Stats grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div v-for="stat in statsCards" :key="stat.label" class="stat-card group">
        <div class="flex items-center justify-between mb-3">
          <span class="text-2xl">{{ stat.icon }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="stat.changeClass">
            {{ stat.change }}
          </span>
        </div>
        <div class="text-2xl font-bold text-white mb-1">{{ stat.value }}</div>
        <div class="text-xs text-gray-500">{{ stat.label }}</div>
      </div>
    </div>

    <div class="grid lg:grid-cols-3 gap-6">
      <!-- Recent predictions -->
      <div class="lg:col-span-2">
        <div class="glass-card">
          <div class="px-5 py-4 border-b border-purple-900/20 flex items-center justify-between">
            <h2 class="text-base font-semibold text-white">Recent Predictions</h2>
            <router-link to="/trades" class="text-xs text-purple-400 hover:text-purple-300 transition-colors">View all →</router-link>
          </div>
          <div class="divide-y divide-purple-900/10">
            <div v-for="pred in recentPredictions" :key="pred.id" class="px-5 py-4 hover:bg-purple-900/5 transition-colors">
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-white truncate">{{ pred.question }}</p>
                  <div class="flex items-center gap-3 mt-1.5">
                    <span class="text-xs" :class="pred.direction === 'YES' ? 'text-green-400' : 'text-red-400'">{{ pred.direction }}</span>
                    <span class="text-xs text-gray-500">{{ pred.confidence }}% conf.</span>
                    <span class="text-xs text-gray-600">{{ formatDate(pred.timestamp) }}</span>
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <div class="text-sm font-bold" :class="pred.profit >= 0 ? 'text-green-400' : 'text-red-400'">
                    {{ pred.profit >= 0 ? '+' : '' }}${{ pred.profit.toFixed(2) }}
                  </div>
                  <span class="badge text-[10px]" :class="pred.status === 'won' ? 'badge-green' : pred.status === 'lost' ? 'badge-red' : 'badge-purple'">
                    {{ pred.status.toUpperCase() }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="space-y-6">
        <!-- Active positions -->
        <div class="glass-card">
          <div class="px-5 py-4 border-b border-purple-900/20">
            <h2 class="text-base font-semibold text-white">Active Positions</h2>
          </div>
          <div class="p-5 space-y-3">
            <div v-for="pos in activePositions" :key="pos.id" class="flex items-center justify-between p-3 rounded-lg bg-dark hover:bg-dark-300 transition-colors">
              <div class="min-w-0 flex-1">
                <p class="text-xs text-white truncate">{{ pos.question }}</p>
                <span class="text-[10px]" :class="pos.direction === 'YES' ? 'text-green-400' : 'text-red-400'">{{ pos.direction }} @ ${{ pos.entryPrice.toFixed(2) }}</span>
              </div>
              <div class="text-right ml-3">
                <div class="text-xs font-bold" :class="pos.unrealizedPnl >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ pos.unrealizedPnl >= 0 ? '+' : '' }}{{ (pos.unrealizedPnl * 100).toFixed(0) }}%
                </div>
              </div>
            </div>
            <div v-if="activePositions.length === 0" class="text-center py-4">
              <p class="text-xs text-gray-500">No active positions</p>
            </div>
          </div>
        </div>

        <!-- Quick actions -->
        <div class="glass-card p-5">
          <h2 class="text-base font-semibold text-white mb-4">Quick Actions</h2>
          <div class="grid grid-cols-2 gap-3">
            <router-link to="/oracle" class="flex flex-col items-center gap-2 p-3 rounded-lg bg-dark hover:bg-dark-300 transition-colors text-center">
              <span class="text-xl">🔮</span>
              <span class="text-xs text-gray-400">Ask Oracle</span>
            </router-link>
            <router-link to="/whales" class="flex flex-col items-center gap-2 p-3 rounded-lg bg-dark hover:bg-dark-300 transition-colors text-center">
              <span class="text-xl">🐋</span>
              <span class="text-xs text-gray-400">Whales</span>
            </router-link>
            <router-link to="/settings" class="flex flex-col items-center gap-2 p-3 rounded-lg bg-dark hover:bg-dark-300 transition-colors text-center">
              <span class="text-xl">🤖</span>
              <span class="text-xs text-gray-400">AutoPilot</span>
            </router-link>
            <router-link to="/trades" class="flex flex-col items-center gap-2 p-3 rounded-lg bg-dark hover:bg-dark-300 transition-colors text-center">
              <span class="text-xl">📈</span>
              <span class="text-xs text-gray-400">Trades</span>
            </router-link>
          </div>
        </div>

        <!-- Credit balance -->
        <div class="glass-card p-5">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold text-white">Credits</h2>
            <span class="text-lg">🪙</span>
          </div>
          <div class="text-3xl font-black text-gold-400 mb-1">{{ creditStore.balance }}</div>
          <p class="text-xs text-gray-500 mb-4">credits remaining</p>
          <div class="h-2 rounded-full bg-dark overflow-hidden mb-2">
            <div class="h-full bg-gradient-to-r from-gold-500 to-purple-500 rounded-full transition-all" :style="{ width: Math.min((creditStore.balance / 500) * 100, 100) + '%' }" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/store.js'
import { useCreditStore } from '@/store.js'

const authStore = useAuthStore()
const creditStore = useCreditStore()

const statsCards = [
  { icon: '📊', label: 'Total Trades', value: '147', change: '+12 this week', changeClass: 'bg-green-900/30 text-green-400' },
  { icon: '🎯', label: 'Win Rate', value: '73.2%', change: '+2.1%', changeClass: 'bg-green-900/30 text-green-400' },
  { icon: '💰', label: 'Total Profit', value: '$1,847.32', change: '+$245 today', changeClass: 'bg-green-900/30 text-green-400' },
  { icon: '🪙', label: 'Credits Used', value: '312', change: '188 remaining', changeClass: 'bg-purple-900/30 text-purple-300' },
]

const recentPredictions = [
  { id: 1, question: 'Will Bitcoin exceed $150,000 by December 2026?', direction: 'YES', confidence: 87, profit: 24.50, status: 'won', timestamp: '2026-03-16T10:30:00Z' },
  { id: 2, question: 'Will the Fed cut rates in April 2026?', direction: 'NO', confidence: 72, profit: -12.00, status: 'lost', timestamp: '2026-03-15T14:20:00Z' },
  { id: 3, question: 'Will ETH flip BTC by market cap in 2026?', direction: 'NO', confidence: 91, profit: 38.75, status: 'won', timestamp: '2026-03-14T09:15:00Z' },
  { id: 4, question: 'Will Trump win popular vote?', direction: 'YES', confidence: 65, profit: 15.00, status: 'won', timestamp: '2026-03-13T16:45:00Z' },
  { id: 5, question: 'Will Apple release AR glasses in 2026?', direction: 'YES', confidence: 58, profit: 0, status: 'active', timestamp: '2026-03-12T11:00:00Z' },
]

const activePositions = [
  { id: 1, question: 'Apple AR glasses in 2026?', direction: 'YES', entryPrice: 0.42, unrealizedPnl: 0.15 },
  { id: 2, question: 'SpaceX Starship orbital 2026?', direction: 'YES', entryPrice: 0.78, unrealizedPnl: 0.05 },
  { id: 3, question: 'US recession by Q4 2026?', direction: 'NO', entryPrice: 0.55, unrealizedPnl: -0.08 },
]

function formatDate(ts) {
  const d = new Date(ts)
  const now = new Date()
  const diff = Math.floor((now - d) / (1000 * 60 * 60))
  if (diff < 1) return 'Just now'
  if (diff < 24) return `${diff}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

onMounted(() => { creditStore.fetchBalance() })
</script>
