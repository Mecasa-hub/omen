<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="px-5 py-3 border-b border-purple-900/30">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-lg">⚔️</span>
          <h3 class="text-sm font-semibold text-white">War Room</h3>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="wsConnected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'">
            {{ wsConnected ? 'LIVE' : 'OFFLINE' }}
          </span>
        </div>
        <button v-if="!wsConnected" @click="oracleStore.connectWarRoom()" class="text-xs text-purple-400 hover:text-purple-300 transition-colors">Reconnect</button>
      </div>
      <!-- Agent avatars -->
      <div class="flex items-center gap-4 mt-3">
        <div v-for="agent in agents" :key="agent.id" class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2" :class="agent.borderClass">{{ agent.avatar }}</div>
          <div>
            <div class="text-xs font-medium" :class="agent.textClass">{{ agent.name }}</div>
            <div class="text-[10px] text-gray-500">{{ getVoteCount(agent.id) }} votes</div>
          </div>
        </div>
      </div>
      <!-- Vote bar -->
      <div class="flex h-1.5 rounded-full overflow-hidden mt-2 bg-dark">
        <div class="bg-green-500 transition-all duration-500" :style="{ width: bullPct + '%' }" />
        <div class="bg-blue-500 transition-all duration-500" :style="{ width: analystPct + '%' }" />
        <div class="bg-red-500 transition-all duration-500" :style="{ width: bearPct + '%' }" />
      </div>
    </div>

    <!-- Debate messages -->
    <div ref="debateContainer" class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      <div v-if="allDebates.length === 0" class="flex flex-col items-center justify-center h-full text-center py-8">
        <span class="text-3xl mb-3">⚔️</span>
        <p class="text-sm text-gray-500">Waiting for AI agents to debate...</p>
        <p class="text-xs text-gray-600 mt-1">Ask the Oracle a question to start</p>
      </div>

      <div v-for="msg in allDebates" :key="msg.id" class="flex gap-2.5 animate-slide-up">
        <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 border" :class="getStyle(msg.agent).borderClass">
          {{ getStyle(msg.agent).avatar }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="text-xs font-semibold" :class="getStyle(msg.agent).textClass">{{ getStyle(msg.agent).name }}</span>
            <span class="text-[10px] text-gray-600">{{ formatTime(msg.timestamp) }}</span>
            <span v-if="msg.confidence" class="text-[10px] px-1.5 py-0.5 rounded-full"
              :class="msg.confidence > 70 ? 'bg-green-900/30 text-green-400' : 'bg-gold-900/30 text-gold-400'">
              {{ msg.confidence }}%
            </span>
          </div>
          <p class="text-xs text-gray-300 leading-relaxed">{{ msg.content }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useOracleStore } from '@/store.js'

const oracleStore = useOracleStore()
const debateContainer = ref(null)
const wsConnected = computed(() => oracleStore.wsConnected)

const agents = [
  { id: 'bull', name: 'Bull', avatar: '🟢', borderClass: 'border-green-500/50 bg-green-900/20', textClass: 'text-green-400' },
  { id: 'analyst', name: 'Analyst', avatar: '🔵', borderClass: 'border-blue-500/50 bg-blue-900/20', textClass: 'text-blue-400' },
  { id: 'bear', name: 'Bear', avatar: '🔴', borderClass: 'border-red-500/50 bg-red-900/20', textClass: 'text-red-400' },
]

const mockDebates = [
  { id: 1, agent: 'bull', content: 'BTC ETF inflows strong for 3 weeks. Institutional demand not slowing. $150K target within reach by Q3.', confidence: 85, timestamp: new Date().toISOString() },
  { id: 2, agent: 'bear', content: 'Overextended RSI on weekly. Similar patterns in 2021 before 50% correction. Macro headwinds remain.', confidence: 72, timestamp: new Date().toISOString() },
  { id: 3, agent: 'analyst', content: 'On-chain shows accumulation by LTH. Exchange reserves at 5-year lows. But derivatives funding elevated — caution.', confidence: 78, timestamp: new Date().toISOString() },
  { id: 4, agent: 'bull', content: 'Mining difficulty ATH. Hash rate shows network strength. Halving supply shock still being absorbed.', confidence: 80, timestamp: new Date().toISOString() },
  { id: 5, agent: 'bear', content: 'Stablecoin dominance rising. Smart money rotating to safety. Watch for death cross on 4H.', confidence: 65, timestamp: new Date().toISOString() },
]

const allDebates = computed(() => oracleStore.debates.length > 0 ? oracleStore.debates : mockDebates)

function getStyle(agentId) { return agents.find(a => a.id === agentId) || agents[1] }
function getVoteCount(agentId) { return allDebates.value.filter(d => d.agent === agentId).length }

const total = computed(() => Math.max(allDebates.value.length, 1))
const bullPct = computed(() => (getVoteCount('bull') / total.value) * 100)
const bearPct = computed(() => (getVoteCount('bear') / total.value) * 100)
const analystPct = computed(() => 100 - bullPct.value - bearPct.value)

function formatTime(ts) { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }

watch(() => oracleStore.debates, async () => {
  await nextTick()
  if (debateContainer.value) debateContainer.value.scrollTop = debateContainer.value.scrollHeight
}, { deep: true })

onMounted(() => oracleStore.connectWarRoom())
</script>
