<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">⚙️ Settings</h1>
      <p class="text-sm text-gray-500 mt-1">Manage your account, AutoPilot, and preferences</p>
    </div>

    <div class="grid lg:grid-cols-3 gap-6">
      <!-- Left column: Profile + Notifications + Wallet -->
      <div class="lg:col-span-2 space-y-6">
        <!-- Profile -->
        <div class="glass-card p-6">
          <h2 class="text-base font-semibold text-white mb-5 flex items-center gap-2">👤 Profile</h2>
          <div class="space-y-4">
            <div>
              <label class="text-sm text-gray-400 mb-1 block">Username</label>
              <input v-model="profile.username" type="text" class="input-dark" />
            </div>
            <div>
              <label class="text-sm text-gray-400 mb-1 block">Email</label>
              <input v-model="profile.email" type="email" class="input-dark" />
            </div>
            <button @click="saveProfile" :disabled="savingProfile" class="btn-primary text-sm">
              {{ savingProfile ? 'Saving...' : profileSaved ? '✅ Saved' : 'Save Profile' }}
            </button>
          </div>
        </div>

        <!-- Notifications -->
        <div class="glass-card p-6">
          <h2 class="text-base font-semibold text-white mb-5 flex items-center gap-2">🔔 Notifications</h2>
          <div class="space-y-4">
            <div v-for="pref in notifPrefs" :key="pref.key" class="flex items-center justify-between p-3 rounded-lg bg-dark">
              <div>
                <p class="text-sm text-white">{{ pref.label }}</p>
                <p class="text-xs text-gray-500">{{ pref.desc }}</p>
              </div>
              <button @click="pref.enabled = !pref.enabled" class="relative w-11 h-6 rounded-full transition-colors duration-300"
                :class="pref.enabled ? 'bg-purple-600' : 'bg-gray-700'">
                <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                  :class="pref.enabled ? 'translate-x-5' : 'translate-x-0.5'" />
              </button>
            </div>
            <button @click="saveNotifs" class="btn-ghost text-sm">Save Notification Preferences</button>
          </div>
        </div>

        <!-- Wallet -->
        <div class="glass-card p-6">
          <h2 class="text-base font-semibold text-white mb-5 flex items-center gap-2">💳 Wallet Connection</h2>
          <div v-if="wallet.connected" class="p-4 rounded-lg bg-dark border border-green-900/30">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-green-500 to-green-700 flex items-center justify-center text-lg">✓</div>
                <div>
                  <p class="text-sm font-medium text-white">Connected</p>
                  <p class="text-xs text-gray-400 font-mono">{{ wallet.address }}</p>
                </div>
              </div>
              <button @click="disconnectWallet" class="btn-ghost text-xs py-1.5 px-3 text-red-400 border-red-900/30 hover:bg-red-900/10">Disconnect</button>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <span class="text-4xl mb-4 block">💳</span>
            <p class="text-sm text-gray-400 mb-4">Connect your Polymarket wallet to enable trading</p>
            <button @click="connectWallet" class="btn-primary text-sm">Connect Wallet</button>
          </div>
        </div>

        <!-- API Keys -->
        <div class="glass-card p-6">
          <h2 class="text-base font-semibold text-white mb-5 flex items-center gap-2">🔑 API Keys</h2>
          <div class="space-y-3">
            <div class="p-3 rounded-lg bg-dark">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-gray-300">API Key</span>
                <button @click="toggleShowKey" class="text-xs text-purple-400 hover:text-purple-300">{{ showApiKey ? 'Hide' : 'Show' }}</button>
              </div>
              <div class="flex items-center gap-2">
                <code class="flex-1 text-xs text-gray-400 font-mono bg-dark-300 px-3 py-2 rounded">{{ showApiKey ? apiKey : '••••••••••••••••••••••••••••••••' }}</code>
                <button @click="copyApiKey" class="text-xs text-gray-500 hover:text-gray-300 px-2">{{ copiedKey ? '✅' : '📋' }}</button>
              </div>
            </div>
            <button class="btn-ghost text-sm">Generate New Key</button>
          </div>
        </div>

        <!-- Danger zone -->
        <div class="glass-card p-6 border border-red-900/20">
          <h2 class="text-base font-semibold text-red-400 mb-3">⚠️ Danger Zone</h2>
          <p class="text-sm text-gray-500 mb-4">Permanently delete your account and all associated data.</p>
          <button class="btn-danger text-sm">Delete Account</button>
        </div>
      </div>

      <!-- Right column: AutoPilot -->
      <div>
        <AutoPilot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import AutoPilot from '@/components/AutoPilot.vue'

const savingProfile = ref(false)
const profileSaved = ref(false)
const showApiKey = ref(false)
const copiedKey = ref(false)
const apiKey = 'omen_sk_7x3k9m2p5n8q1w4r6t0y_live'

const profile = reactive({ username: 'CryptoOracle', email: 'oracle@omen.ai' })

const wallet = reactive({ connected: true, address: '0x1a2b...ef12' })

const notifPrefs = reactive([
  { key: 'predictions', label: 'Prediction Results', desc: 'Get notified when your predictions resolve', enabled: true },
  { key: 'whale_moves', label: 'Whale Moves', desc: 'Alert when followed whales make trades', enabled: true },
  { key: 'autopilot', label: 'AutoPilot Trades', desc: 'Notifications for auto-executed trades', enabled: true },
  { key: 'credits_low', label: 'Low Credits', desc: 'Alert when credits fall below 10', enabled: false },
  { key: 'war_room', label: 'War Room Updates', desc: 'Live debate notifications', enabled: false },
])

async function saveProfile() {
  savingProfile.value = true
  await new Promise(r => setTimeout(r, 1000))
  savingProfile.value = false; profileSaved.value = true
  setTimeout(() => profileSaved.value = false, 2000)
}

function saveNotifs() { console.log('Saving notification prefs:', notifPrefs) }
function connectWallet() { wallet.connected = true; wallet.address = '0x1a2b...ef12' }
function disconnectWallet() { wallet.connected = false; wallet.address = '' }
function toggleShowKey() { showApiKey.value = !showApiKey.value }
function copyApiKey() { navigator.clipboard.writeText(apiKey); copiedKey.value = true; setTimeout(() => copiedKey.value = false, 2000) }
</script>
