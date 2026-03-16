<template>
  <nav class="fixed top-0 left-0 right-0 z-50 bg-dark/80 backdrop-blur-xl border-b border-purple-900/30">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <router-link to="/dashboard" class="flex items-center gap-2.5 group">
          <img src="@/assets/logo.svg" alt="OMEN" class="w-8 h-8 transition-transform group-hover:scale-110" />
          <span class="text-xl font-bold text-gradient-main tracking-tight">OMEN</span>
        </router-link>

        <!-- Desktop nav -->
        <div class="hidden md:flex items-center gap-1">
          <router-link v-for="link in navLinks" :key="link.to" :to="link.to"
            class="px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200"
            :class="$route.path === link.to ? 'text-white bg-purple-900/40 shadow-inner' : 'text-gray-400 hover:text-white hover:bg-purple-900/20'">
            <span class="mr-1.5">{{ link.icon }}</span>{{ link.label }}
          </router-link>
        </div>

        <!-- Right side -->
        <div class="hidden md:flex items-center gap-4">
          <CreditBar />
          <div class="relative" ref="userMenuRef">
            <button @click="showUserMenu = !showUserMenu"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-purple-900/20 transition-colors">
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-gold-500 flex items-center justify-center text-sm font-bold">
                {{ userInitial }}
              </div>
              <svg class="w-4 h-4 text-gray-400 transition-transform" :class="{ 'rotate-180': showUserMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <transition name="slide-up">
              <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 glass-card shadow-xl shadow-purple-900/20 py-2 animate-slide-down">
                <router-link to="/settings" class="flex items-center gap-2 px-4 py-2 text-sm text-gray-300 hover:text-white hover:bg-purple-900/20 transition-colors" @click="showUserMenu = false">
                  ⚙️ Settings
                </router-link>
                <hr class="border-purple-900/30 my-1" />
                <button @click="handleLogout" class="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-red-900/10 transition-colors">
                  🚪 Sign Out
                </button>
              </div>
            </transition>
          </div>
        </div>

        <!-- Mobile hamburger -->
        <button @click="showMobileMenu = !showMobileMenu" class="md:hidden p-2 rounded-lg hover:bg-purple-900/20 transition-colors">
          <svg class="w-6 h-6 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path v-if="!showMobileMenu" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile menu -->
    <transition name="slide-up">
      <div v-if="showMobileMenu" class="md:hidden bg-dark-300 border-t border-purple-900/30 py-3 px-4 space-y-1">
        <router-link v-for="link in navLinks" :key="link.to" :to="link.to"
          class="block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          :class="$route.path === link.to ? 'text-white bg-purple-900/40' : 'text-gray-400 hover:text-white hover:bg-purple-900/20'"
          @click="showMobileMenu = false">
          <span class="mr-2">{{ link.icon }}</span>{{ link.label }}
        </router-link>
        <hr class="border-purple-900/30 my-2" />
        <div class="px-4 py-2"><CreditBar /></div>
      </div>
    </transition>
  </nav>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store.js'
import CreditBar from './CreditBar.vue'

const router = useRouter()
const authStore = useAuthStore()
const showUserMenu = ref(false)
const showMobileMenu = ref(false)
const userMenuRef = ref(null)

const navLinks = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/oracle', label: 'Oracle', icon: '🔮' },
  { to: '/whales', label: 'Whales', icon: '🐋' },
  { to: '/trades', label: 'Trades', icon: '📈' },
]

const userInitial = computed(() => authStore.username?.charAt(0)?.toUpperCase() || 'U')

function handleLogout() {
  showUserMenu.value = false
  authStore.logout()
  router.push('/login')
}

function handleClickOutside(e) {
  if (userMenuRef.value && !userMenuRef.value.contains(e.target)) showUserMenu.value = false
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>
