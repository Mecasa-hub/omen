<template>
  <div class="glass-card overflow-hidden group">
    <!-- Gradient top border -->
    <div class="h-1 bg-gradient-to-r" :class="profit >= 0 ? 'from-green-500 via-gold-500 to-green-500' : 'from-red-500 via-red-400 to-red-500'" />

    <div class="p-5">
      <!-- Status badge -->
      <div class="flex items-center justify-between mb-3">
        <span class="badge" :class="profit >= 0 ? 'badge-green' : 'badge-red'">
          {{ profit >= 0 ? '🎯 WIN' : '❌ LOSS' }}
        </span>
        <span class="text-xs text-gray-500">{{ formatDate(trade.timestamp) }}</span>
      </div>

      <!-- Prediction -->
      <p class="text-sm font-medium text-white mb-3 leading-relaxed">{{ trade.question }}</p>

      <!-- Outcome details -->
      <div class="flex items-center justify-between mb-4 p-3 rounded-lg bg-dark">
        <div>
          <span class="text-xs text-gray-500">Direction</span>
          <div class="text-sm font-bold" :class="trade.direction === 'YES' ? 'text-green-400' : 'text-red-400'">{{ trade.direction }}</div>
        </div>
        <div class="text-right">
          <span class="text-xs text-gray-500">Profit</span>
          <div class="text-lg font-bold" :class="profit >= 0 ? 'text-green-400' : 'text-red-400'">
            {{ profit >= 0 ? '+' : '' }}${{ Math.abs(profit).toFixed(2) }}
          </div>
        </div>
      </div>

      <!-- Confidence meter -->
      <div class="mb-4">
        <div class="flex justify-between text-xs mb-1">
          <span class="text-gray-500">Oracle Confidence</span>
          <span class="font-semibold" :class="trade.confidence >= 80 ? 'text-green-400' : 'text-gold-400'">{{ trade.confidence }}%</span>
        </div>
        <div class="h-1.5 rounded-full bg-dark overflow-hidden">
          <div class="h-full rounded-full transition-all duration-700" :class="trade.confidence >= 80 ? 'bg-green-500' : 'bg-gold-500'" :style="{ width: trade.confidence + '%' }" />
        </div>
      </div>

      <!-- Share buttons -->
      <div class="flex gap-2">
        <button @click="shareOnTwitter" class="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-[#1DA1F2]/10 text-[#1DA1F2] border border-[#1DA1F2]/20 hover:bg-[#1DA1F2]/20 transition-all">
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
          Share on 𝕏
        </button>
        <button @click="copyLink" class="flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-purple-900/20 text-purple-300 border border-purple-900/30 hover:bg-purple-900/30 transition-all">
          {{ copied ? '✅' : '🔗' }}
        </button>
      </div>
    </div>

    <!-- OMEN watermark -->
    <div class="px-5 py-2 border-t border-purple-900/20 bg-dark/50 flex items-center justify-between">
      <span class="text-[10px] text-gray-600">Powered by OMEN — The Oracle Machine</span>
      <span class="text-[10px] text-purple-500">🔮</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  trade: { type: Object, default: () => ({
    question: 'Will Bitcoin exceed $150,000 by December 2026?',
    direction: 'YES', confidence: 87, entryPrice: 0.42, exitPrice: 0.91,
    amount: 50, timestamp: new Date().toISOString(),
  })}
})

const copied = ref(false)
const profit = computed(() => (props.trade.exitPrice - props.trade.entryPrice) * props.trade.amount)

function formatDate(ts) { return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }

function shareOnTwitter() {
  const text = `${profit.value >= 0 ? '🎯' : '📉'} ${profit.value >= 0 ? 'Won' : 'Lost'} $${Math.abs(profit.value).toFixed(2)} on Polymarket!\n\n"${props.trade.question}"\n\nOracle confidence: ${props.trade.confidence}%\n\nPowered by @OmenOracle 🔮`
  window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`, '_blank')
}

function copyLink() {
  navigator.clipboard.writeText(`${window.location.origin}/brag/${props.trade.id || 'demo'}`)
  copied.value = true; setTimeout(() => copied.value = false, 2000)
}
</script>
