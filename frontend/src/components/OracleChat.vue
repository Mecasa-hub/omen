<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-purple-900/30">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-600 to-purple-900 flex items-center justify-center text-xl glow-purple">🔮</div>
        <div>
          <h3 class="text-sm font-semibold text-white">The Oracle</h3>
          <p class="text-xs text-green-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
            Online — Ready to predict
          </p>
        </div>
      </div>
      <button @click="oracleStore.clearChat()" class="text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-purple-900/20">Clear ✕</button>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-5 py-4 space-y-4 scroll-smooth">
      <!-- Welcome -->
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center py-12">
        <div class="text-5xl mb-4 animate-float">🔮</div>
        <h3 class="text-lg font-semibold text-gray-300 mb-2">Ask the Oracle Anything</h3>
        <p class="text-sm text-gray-500 max-w-xs">Ask about any Polymarket prediction. Get AI-powered analysis, confidence scores, and live War Room debates.</p>
        <div class="flex flex-wrap gap-2 mt-6 justify-center">
          <button v-for="s in suggestions" :key="s" @click="sendMessage(s)"
            class="px-3 py-1.5 text-xs rounded-full border border-purple-900/40 text-purple-300 hover:border-purple-600 hover:bg-purple-900/20 transition-all duration-200">
            {{ s }}
          </button>
        </div>
      </div>

      <template v-for="msg in messages" :key="msg.id">
        <!-- User message -->
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-purple-600/80 text-white text-sm">{{ msg.content }}</div>
        </div>
        <!-- Assistant message -->
        <div v-else-if="msg.role === 'assistant'" class="flex justify-start gap-3">
          <div class="w-8 h-8 rounded-full bg-dark-50 flex items-center justify-center text-sm flex-shrink-0 mt-0.5">🔮</div>
          <div class="max-w-[85%] space-y-3">
            <div class="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-dark-300 text-gray-200 text-sm leading-relaxed">{{ msg.content }}</div>
            <!-- Prediction card -->
            <div v-if="msg.meta?.prediction" class="glass-card p-4 space-y-3">
              <div class="flex items-center justify-between">
                <span class="badge-purple">🎯 Prediction</span>
                <span class="text-xs text-gray-500">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="text-sm font-medium text-white">{{ msg.meta.prediction.question }}</div>
              <div class="flex items-center gap-3">
                <div class="flex-1">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-gray-400">Confidence</span>
                    <span class="text-xs font-bold" :class="msg.meta.confidence >= 0.8 ? 'text-green-400' : msg.meta.confidence >= 0.6 ? 'text-gold-400' : 'text-red-400'">
                      {{ (msg.meta.confidence * 100).toFixed(0) }}%
                    </span>
                  </div>
                  <div class="h-2 rounded-full bg-dark overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-700 ease-out"
                      :class="msg.meta.confidence >= 0.8 ? 'bg-green-500' : msg.meta.confidence >= 0.6 ? 'bg-gold-500' : 'bg-red-500'"
                      :style="{ width: (msg.meta.confidence * 100) + '%' }" />
                  </div>
                </div>
                <div class="px-3 py-1 rounded-lg text-sm font-bold"
                  :class="msg.meta.prediction.direction === 'YES' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'">
                  {{ msg.meta.prediction.direction }}
                </div>
              </div>
              <div v-if="msg.meta.sources?.length" class="pt-2 border-t border-purple-900/20">
                <span class="text-xs text-gray-500">Sources:</span>
                <div class="flex flex-wrap gap-1 mt-1">
                  <span v-for="(src, i) in msg.meta.sources" :key="i" class="text-xs text-purple-400 bg-purple-900/20 px-2 py-0.5 rounded">{{ src }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <!-- System message -->
        <div v-else class="flex justify-center">
          <span class="text-xs text-gray-500 bg-dark-300 px-3 py-1 rounded-full">{{ msg.content }}</span>
        </div>
      </template>

      <!-- Typing indicator -->
      <div v-if="oracleStore.isTyping" class="flex justify-start gap-3">
        <div class="w-8 h-8 rounded-full bg-dark-50 flex items-center justify-center text-sm flex-shrink-0">🔮</div>
        <div class="px-4 py-3 rounded-2xl rounded-bl-sm bg-dark-300">
          <div class="flex gap-1.5">
            <span class="w-2 h-2 rounded-full bg-purple-400 typing-dot"></span>
            <span class="w-2 h-2 rounded-full bg-purple-400 typing-dot"></span>
            <span class="w-2 h-2 rounded-full bg-purple-400 typing-dot"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="px-5 py-4 border-t border-purple-900/30 bg-dark/50">
      <form @submit.prevent="handleSend" class="flex gap-3">
        <input v-model="inputText" type="text" placeholder="Ask the Oracle about any market..." class="input-dark flex-1" :disabled="oracleStore.isTyping" ref="inputRef" />
        <button type="submit" :disabled="!inputText.trim() || oracleStore.isTyping"
          class="btn-primary px-4 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2">
          <span>Send</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </form>
      <p class="text-xs text-gray-600 mt-2 text-center">Each oracle query costs 1 credit · Predictions are AI-generated, not financial advice</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useOracleStore } from '@/store.js'

const oracleStore = useOracleStore()
const inputText = ref('')
const inputRef = ref(null)
const messagesContainer = ref(null)
const messages = computed(() => oracleStore.messages)
const suggestions = ['Will BTC hit $150K in 2026?', 'Trump re-election odds?', 'Will ETH flip BTC by market cap?', 'Next Fed rate decision prediction']

function formatTime(ts) { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }

async function sendMessage(text) {
  const q = text || inputText.value.trim()
  if (!q) return
  inputText.value = ''
  try { await oracleStore.askOracle(q) } catch (err) { console.error('Oracle query failed:', err) }
}
function handleSend() { sendMessage() }

watch(messages, async () => {
  await nextTick()
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}, { deep: true })

onMounted(() => inputRef.value?.focus())
</script>
