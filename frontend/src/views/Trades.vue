<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-2">📈 Trade History</h1>
        <p class="text-sm text-gray-500 mt-1">Your complete prediction and trading record</p>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="filter" class="input-dark text-sm py-2 w-40">
          <option value="all">All Trades</option>
          <option value="won">Won</option>
          <option value="lost">Lost</option>
          <option value="active">Active</option>
        </select>
      </div>
    </div>

    <!-- P&L summary -->
    <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
      <div class="stat-card">
        <div class="text-xs text-gray-500 mb-1">Total P&L</div>
        <div class="text-2xl font-bold text-green-400">+$1,847.32</div>
      </div>
      <div class="stat-card">
        <div class="text-xs text-gray-500 mb-1">Best Trade</div>
        <div class="text-2xl font-bold text-green-400">+$245.00</div>
      </div>
      <div class="stat-card">
        <div class="text-xs text-gray-500 mb-1">Worst Trade</div>
        <div class="text-2xl font-bold text-red-400">-$82.50</div>
      </div>
      <div class="stat-card">
        <div class="text-xs text-gray-500 mb-1">Avg Trade</div>
        <div class="text-2xl font-bold text-white">$12.56</div>
      </div>
    </div>

    <!-- Chart placeholder -->
    <div class="glass-card p-6 mb-6">
      <h3 class="text-sm font-semibold text-white mb-4">Cumulative P&L</h3>
      <div class="h-48 flex items-end gap-1">
        <div v-for="(bar, idx) in chartBars" :key="idx"
          class="flex-1 rounded-t transition-all duration-300 hover:opacity-80 cursor-pointer relative group"
          :class="bar.value >= 0 ? 'bg-green-500/60' : 'bg-red-500/60'"
          :style="{ height: Math.abs(bar.value) / maxBar * 100 + '%', minHeight: '4px' }">
          <div class="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 rounded bg-dark-300 text-[10px] text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
            {{ bar.label }}: {{ bar.value >= 0 ? '+' : '' }}${{ bar.value.toFixed(0) }}
          </div>
        </div>
      </div>
      <div class="flex justify-between mt-2">
        <span class="text-[10px] text-gray-600">30 days ago</span>
        <span class="text-[10px] text-gray-600">Today</span>
      </div>
    </div>

    <!-- Trade table -->
    <div class="glass-card overflow-hidden">
      <table class="w-full">
        <thead>
          <tr class="text-xs text-gray-500 border-b border-purple-900/20">
            <th class="text-left py-3 px-5 font-medium">Market</th>
            <th class="text-center py-3 px-3 font-medium">Direction</th>
            <th class="text-right py-3 px-3 font-medium">Entry</th>
            <th class="text-right py-3 px-3 font-medium">Exit</th>
            <th class="text-right py-3 px-3 font-medium">P&L</th>
            <th class="text-center py-3 px-3 font-medium">Status</th>
            <th class="text-right py-3 px-5 font-medium">Date</th>
            <th class="text-right py-3 px-5 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="trade in filteredTrades" :key="trade.id"
            class="border-b border-purple-900/10 hover:bg-purple-900/5 transition-colors">
            <td class="py-3 px-5">
              <p class="text-sm text-white truncate max-w-xs">{{ trade.question }}</p>
              <span class="text-[10px] text-gray-600">Conf: {{ trade.confidence }}%</span>
            </td>
            <td class="py-3 px-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded" :class="trade.direction === 'YES' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'">
                {{ trade.direction }}
              </span>
            </td>
            <td class="py-3 px-3 text-right text-sm text-gray-300">${{ trade.entryPrice.toFixed(2) }}</td>
            <td class="py-3 px-3 text-right text-sm text-gray-300">{{ trade.exitPrice ? '$' + trade.exitPrice.toFixed(2) : '—' }}</td>
            <td class="py-3 px-3 text-right">
              <span class="text-sm font-bold" :class="trade.profit >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ trade.profit >= 0 ? '+' : '' }}${{ trade.profit.toFixed(2) }}
              </span>
            </td>
            <td class="py-3 px-3 text-center">
              <span class="badge text-[10px]" :class="trade.status === 'won' ? 'badge-green' : trade.status === 'lost' ? 'badge-red' : 'badge-purple'">
                {{ trade.status.toUpperCase() }}
              </span>
            </td>
            <td class="py-3 px-5 text-right text-xs text-gray-500">{{ formatDate(trade.timestamp) }}</td>
            <td class="py-3 px-5 text-right">
              <button v-if="trade.status === 'won'" @click="showBrag = trade" class="text-xs text-gold-400 hover:text-gold-300 transition-colors">🏆 Brag</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Brag modal -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="showBrag" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showBrag = null">
          <div class="w-full max-w-sm mx-4">
            <BragCard :trade="showBrag" />
            <button @click="showBrag = null" class="w-full mt-3 btn-ghost text-sm">Close</button>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import BragCard from '@/components/BragCard.vue'

const filter = ref('all')
const showBrag = ref(null)

const trades = [
  { id: 1, question: 'Will Bitcoin exceed $150,000 by December 2026?', direction: 'YES', confidence: 87, entryPrice: 0.42, exitPrice: 0.91, profit: 24.50, status: 'won', amount: 50, timestamp: '2026-03-16T10:30:00Z' },
  { id: 2, question: 'Will the Fed cut rates in April 2026?', direction: 'NO', confidence: 72, entryPrice: 0.55, exitPrice: 0.31, profit: -12.00, status: 'lost', amount: 50, timestamp: '2026-03-15T14:20:00Z' },
  { id: 3, question: 'Will ETH flip BTC by market cap in 2026?', direction: 'NO', confidence: 91, entryPrice: 0.22, exitPrice: 0.05, profit: 38.75, status: 'won', amount: 50, timestamp: '2026-03-14T09:15:00Z' },
  { id: 4, question: 'Trump popular vote win?', direction: 'YES', confidence: 65, entryPrice: 0.60, exitPrice: 0.90, profit: 15.00, status: 'won', amount: 50, timestamp: '2026-03-13T16:45:00Z' },
  { id: 5, question: 'Apple AR glasses in 2026?', direction: 'YES', confidence: 58, entryPrice: 0.42, exitPrice: null, profit: 0, status: 'active', amount: 50, timestamp: '2026-03-12T11:00:00Z' },
  { id: 6, question: 'SpaceX Starship orbital success?', direction: 'YES', confidence: 82, entryPrice: 0.78, exitPrice: 1.00, profit: 11.00, status: 'won', amount: 50, timestamp: '2026-03-11T08:30:00Z' },
  { id: 7, question: 'US recession by Q4 2026?', direction: 'NO', confidence: 68, entryPrice: 0.55, exitPrice: null, profit: 0, status: 'active', amount: 50, timestamp: '2026-03-10T12:00:00Z' },
  { id: 8, question: 'Solana ETF approved 2026?', direction: 'YES', confidence: 74, entryPrice: 0.35, exitPrice: 0.15, profit: -10.00, status: 'lost', amount: 50, timestamp: '2026-03-09T15:20:00Z' },
]

const filteredTrades = computed(() => filter.value === 'all' ? trades : trades.filter(t => t.status === filter.value))

const chartBars = Array.from({ length: 30 }, (_, i) => ({
  label: `Day ${i + 1}`,
  value: Math.sin(i * 0.3) * 80 + (Math.random() - 0.3) * 40 + i * 2,
}))
const maxBar = Math.max(...chartBars.map(b => Math.abs(b.value)))

function formatDate(ts) { return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
</script>
