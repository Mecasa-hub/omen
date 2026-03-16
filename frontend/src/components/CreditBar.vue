<template>
  <div class="flex items-center gap-2">
    <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-300 border border-purple-900/30">
      <div class="relative">
        <span class="text-gold-400 text-lg">🪙</span>
        <transition name="fade">
          <span v-if="showPulse" class="absolute inset-0 rounded-full border-2 border-gold-400 animate-ping opacity-50" />
        </transition>
      </div>
      <transition name="fade" mode="out-in">
        <span :key="displayBalance" class="text-sm font-semibold text-gold-300 tabular-nums min-w-[3ch] text-right">{{ displayBalance }}</span>
      </transition>
      <span class="text-xs text-gray-500">credits</span>
    </div>
    <button @click="showBuyModal = true" class="px-3 py-1.5 text-xs font-semibold bg-gold-500/20 text-gold-400 border border-gold-500/30 rounded-lg hover:bg-gold-500/30 hover:border-gold-400/50 transition-all duration-200">
      + Buy
    </button>
    <teleport to="body">
      <transition name="fade">
        <div v-if="showBuyModal" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm" @click.self="showBuyModal = false">
          <div class="glass-card p-6 w-full max-w-sm mx-4 animate-slide-up">
            <h3 class="text-lg font-bold text-white mb-4">Buy Credits</h3>
            <div class="grid grid-cols-3 gap-3 mb-4">
              <button v-for="pkg in packages" :key="pkg.amount" @click="selectedPackage = pkg"
                class="p-3 rounded-lg border text-center transition-all duration-200"
                :class="selectedPackage?.amount === pkg.amount ? 'border-gold-400 bg-gold-500/10 shadow-lg shadow-gold-500/10' : 'border-purple-900/30 hover:border-purple-600/50'">
                <div class="text-2xl mb-1">🪙</div>
                <div class="text-sm font-bold text-white">{{ pkg.amount }}</div>
                <div class="text-xs text-gold-400">${{ pkg.price }}</div>
              </button>
            </div>
            <div class="flex gap-3">
              <button @click="showBuyModal = false" class="flex-1 btn-ghost text-sm py-2">Cancel</button>
              <button @click="handlePurchase" :disabled="!selectedPackage || purchasing" class="flex-1 btn-gold text-sm py-2 disabled:opacity-50">
                {{ purchasing ? 'Processing...' : 'Purchase' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useCreditStore } from '@/store.js'

const creditStore = useCreditStore()
const showBuyModal = ref(false)
const showPulse = ref(false)
const selectedPackage = ref(null)
const purchasing = ref(false)
const packages = [{ amount: 50, price: 5 }, { amount: 200, price: 15 }, { amount: 500, price: 30 }]
const displayBalance = computed(() => creditStore.balance)

watch(() => creditStore.balance, () => { showPulse.value = true; setTimeout(() => showPulse.value = false, 1000) })

async function handlePurchase() {
  if (!selectedPackage.value) return
  purchasing.value = true
  try { await creditStore.purchaseCredits(selectedPackage.value.amount, 'card'); showBuyModal.value = false; selectedPackage.value = null }
  catch (err) { console.error('Purchase failed:', err) }
  finally { purchasing.value = false }
}

onMounted(() => creditStore.fetchBalance())
</script>
