<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-bold text-white flex items-center gap-2">🐋 Whale Leaderboard</h3>
      <button @click="whaleStore.fetchWhales()" class="text-xs text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1">
        <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': whaleStore.loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        Refresh
      </button>
    </div>

    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr class="text-xs text-gray-500 border-b border-purple-900/20">
            <th class="text-left py-3 px-3 font-medium">#</th>
            <th class="text-left py-3 px-3 font-medium cursor-pointer hover:text-gray-300 transition-colors" @click="whaleStore.setSort('address')">Address</th>
            <th class="text-right py-3 px-3 font-medium cursor-pointer hover:text-gray-300 transition-colors" @click="whaleStore.setSort('roi')">ROI {{ sortIcon('roi') }}</th>
            <th class="text-right py-3 px-3 font-medium cursor-pointer hover:text-gray-300 transition-colors" @click="whaleStore.setSort('winRate')">Win Rate {{ sortIcon('winRate') }}</th>
            <th class="text-right py-3 px-3 font-medium cursor-pointer hover:text-gray-300 transition-colors" @click="whaleStore.setSort('volume')">Volume {{ sortIcon('volume') }}</th>
            <th class="text-right py-3 px-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(whale, idx) in displayWhales" :key="whale.address"
            class="border-b border-purple-900/10 hover:bg-purple-900/10 transition-colors cursor-pointer group"
            @click="emit('selectWhale', whale)">
            <td class="py-3 px-3">
              <span class="text-sm font-bold" :class="idx < 3 ? 'text-gold-400' : 'text-gray-500'">{{ idx + 1 }}</span>
            </td>
            <td class="py-3 px-3">
              <div class="flex items-center gap-2">
                <div class="w-7 h-7 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-xs font-bold text-white">
                  {{ whale.address.slice(2, 4).toUpperCase() }}
                </div>
                <div>
                  <span class="text-sm text-gray-300 font-mono">{{ truncAddr(whale.address) }}</span>
                  <button @click.stop="copyAddress(whale.address)" class="ml-1.5 text-gray-600 hover:text-gray-300 transition-colors">
                    <svg class="w-3.5 h-3.5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                  </button>
                </div>
                <span v-if="whale.label" class="badge-purple text-[10px]">{{ whale.label }}</span>
              </div>
            </td>
            <td class="py-3 px-3 text-right">
              <span class="text-sm font-semibold" :class="whale.roi >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ whale.roi >= 0 ? '+' : '' }}{{ whale.roi.toFixed(1) }}%
              </span>
            </td>
            <td class="py-3 px-3 text-right">
              <div class="flex items-center justify-end gap-2">
                <div class="w-12 h-1.5 rounded-full bg-dark overflow-hidden">
                  <div class="h-full rounded-full" :class="whale.winRate >= 60 ? 'bg-green-500' : whale.winRate >= 50 ? 'bg-gold-500' : 'bg-red-500'" :style="{ width: whale.winRate + '%' }" />
                </div>
                <span class="text-sm text-gray-300">{{ whale.winRate.toFixed(0) }}%</span>
              </div>
            </td>
            <td class="py-3 px-3 text-right">
              <span class="text-sm text-gray-300">${{ formatVolume(whale.volume) }}</span>
            </td>
            <td class="py-3 px-3 text-right">
              <button v-if="isFollowed(whale.address)" @click.stop="whaleStore.unfollowWhale(whale.address)"
                class="px-3 py-1 text-xs font-medium rounded-md bg-purple-600/20 text-purple-300 border border-purple-600/30 hover:bg-red-900/20 hover:text-red-400 hover:border-red-600/30 transition-all">
                Following
              </button>
              <button v-else @click.stop="whaleStore.followWhale(whale.address)"
                class="px-3 py-1 text-xs font-medium rounded-md bg-gold-500/10 text-gold-400 border border-gold-500/30 hover:bg-gold-500/20 hover:border-gold-400/50 transition-all opacity-0 group-hover:opacity-100">
                Copy 🐋
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty state -->
    <div v-if="displayWhales.length === 0 && !whaleStore.loading" class="text-center py-12">
      <span class="text-4xl">🐋</span>
      <p class="text-sm text-gray-500 mt-3">No whales found. Check back later.</p>
    </div>

    <!-- Loading -->
    <div v-if="whaleStore.loading" class="space-y-3 mt-4">
      <div v-for="i in 5" :key="i" class="h-14 rounded-lg shimmer" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useWhaleStore } from '@/store.js'

const emit = defineEmits(['selectWhale'])
const whaleStore = useWhaleStore()

const mockWhales = [
  { address: '0x1a2b3c4d5e6f7890abcdef1234567890abcdef12', roi: 342.5, winRate: 78, volume: 2450000, label: 'Degen King' },
  { address: '0x2b3c4d5e6f7890abcdef1234567890abcdef1234', roi: 218.3, winRate: 72, volume: 1890000, label: 'Smart Money' },
  { address: '0x3c4d5e6f7890abcdef1234567890abcdef123456', roi: 156.7, winRate: 68, volume: 3200000, label: '' },
  { address: '0x4d5e6f7890abcdef1234567890abcdef12345678', roi: 128.2, winRate: 65, volume: 980000, label: 'Whale Alert' },
  { address: '0x5e6f7890abcdef1234567890abcdef1234567890', roi: -12.4, winRate: 45, volume: 540000, label: '' },
  { address: '0x6f7890abcdef1234567890abcdef123456789012', roi: 89.1, winRate: 62, volume: 1250000, label: 'Consistent' },
  { address: '0x7890abcdef1234567890abcdef12345678901234', roi: 205.8, winRate: 74, volume: 4100000, label: 'OG Trader' },
  { address: '0x890abcdef1234567890abcdef1234567890123456', roi: 67.3, winRate: 58, volume: 720000, label: '' },
]

const displayWhales = computed(() => whaleStore.sortedWhales.length > 0 ? whaleStore.sortedWhales : mockWhales)
const isFollowed = (addr) => whaleStore.followedWhales.includes(addr)

function truncAddr(addr) { return addr.slice(0, 6) + '...' + addr.slice(-4) }
function formatVolume(v) { return v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(0) + 'K' : v.toFixed(0) }
function copyAddress(addr) { navigator.clipboard.writeText(addr) }
function sortIcon(field) { return whaleStore.sortBy === field ? (whaleStore.sortOrder === 'desc' ? '↓' : '↑') : '' }

onMounted(() => whaleStore.fetchWhales())
</script>
