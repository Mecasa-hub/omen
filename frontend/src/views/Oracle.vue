<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-2">🔮 The Oracle</h1>
        <p class="text-sm text-gray-500 mt-1">Ask questions, get AI-powered predictions with live agent debates</p>
      </div>
      <div class="flex items-center gap-3">
        <button @click="showWarRoom = !showWarRoom" class="btn-ghost text-sm flex items-center gap-2">
          ⚔️ {{ showWarRoom ? 'Hide' : 'Show' }} War Room
        </button>
      </div>
    </div>

    <div class="flex gap-6" :class="showWarRoom ? 'flex-col lg:flex-row' : ''">
      <!-- Oracle chat - main panel -->
      <div class="flex-1">
        <div class="glass-card h-[calc(100vh-12rem)] flex flex-col">
          <OracleChat />
        </div>
      </div>

      <!-- War Room - side panel -->
      <transition name="slide-right">
        <div v-if="showWarRoom" class="lg:w-96 flex-shrink-0">
          <div class="glass-card h-[calc(100vh-12rem)] flex flex-col">
            <WarRoom />
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import OracleChat from '@/components/OracleChat.vue'
import WarRoom from '@/components/WarRoom.vue'

const showWarRoom = ref(true)
</script>

<style scoped>
.slide-right-enter-active, .slide-right-leave-active { transition: all 0.3s ease; }
.slide-right-enter-from, .slide-right-leave-to { opacity: 0; transform: translateX(20px); }
</style>
