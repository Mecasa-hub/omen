<template>
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden px-4">
    <!-- Mystical background -->
    <div class="absolute inset-0 bg-gradient-to-br from-dark via-purple-950/20 to-dark" />
    <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,0.15)_0%,transparent_60%)]" />
    <div class="absolute inset-0 opacity-[0.02]" style="background-image: linear-gradient(rgba(124,58,237,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.4) 1px, transparent 1px); background-size: 40px 40px;" />
    <!-- Floating orbs -->
    <div class="absolute top-20 left-20 w-64 h-64 bg-purple-600/10 rounded-full blur-3xl animate-pulse" />
    <div class="absolute bottom-20 right-20 w-48 h-48 bg-gold-500/5 rounded-full blur-3xl animate-pulse" style="animation-delay: 1s;" />
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-500/5 rounded-full blur-3xl" />

    <!-- Auth card -->
    <div class="relative z-10 w-full max-w-md">
      <!-- Logo -->
      <div class="text-center mb-8">
        <router-link to="/" class="inline-flex items-center gap-3">
          <img src="@/assets/logo.svg" alt="OMEN" class="w-12 h-12" />
          <span class="text-3xl font-black text-gradient-main tracking-tight">OMEN</span>
        </router-link>
        <p class="text-sm text-gray-500 mt-2">The Oracle Machine</p>
      </div>

      <div class="glass-card p-8">
        <!-- Tab toggle -->
        <div class="flex bg-dark rounded-lg p-1 mb-6">
          <button @click="isLogin = true" class="flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200"
            :class="isLogin ? 'bg-purple-600 text-white shadow' : 'text-gray-400 hover:text-gray-300'">
            Sign In
          </button>
          <button @click="isLogin = false" class="flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200"
            :class="!isLogin ? 'bg-purple-600 text-white shadow' : 'text-gray-400 hover:text-gray-300'">
            Register
          </button>
        </div>

        <!-- Error message -->
        <transition name="slide-up">
          <div v-if="authStore.error" class="mb-4 p-3 rounded-lg bg-red-900/20 border border-red-900/30 text-sm text-red-400 flex items-center gap-2">
            <span>⚠️</span> {{ authStore.error }}
          </div>
        </transition>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- Username field (register only) -->
          <transition name="slide-up">
            <div v-if="!isLogin">
              <label class="text-sm text-gray-400 mb-1 block">Username</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">👤</span>
                <input v-model="form.username" type="text" placeholder="Choose a username" class="input-dark pl-10" required />
              </div>
            </div>
          </transition>

          <div>
            <label class="text-sm text-gray-400 mb-1 block">Email</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">✉️</span>
              <input v-model="form.email" type="email" placeholder="your@email.com" class="input-dark pl-10" required />
            </div>
          </div>

          <div>
            <label class="text-sm text-gray-400 mb-1 block">Password</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔒</span>
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" placeholder="••••••••" class="input-dark pl-10 pr-10" required />
              <button type="button" @click="showPassword = !showPassword" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors">
                {{ showPassword ? '🙈' : '👁️' }}
              </button>
            </div>
          </div>

          <!-- Confirm password (register only) -->
          <transition name="slide-up">
            <div v-if="!isLogin">
              <label class="text-sm text-gray-400 mb-1 block">Confirm Password</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔒</span>
                <input v-model="form.confirmPassword" :type="showPassword ? 'text' : 'password'" placeholder="••••••••" class="input-dark pl-10" required />
              </div>
              <p v-if="form.confirmPassword && form.password !== form.confirmPassword" class="text-xs text-red-400 mt-1">Passwords don't match</p>
            </div>
          </transition>

          <div v-if="isLogin" class="flex items-center justify-between">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.remember" class="w-4 h-4 rounded border-purple-900/50 bg-dark text-purple-600 focus:ring-purple-500" />
              <span class="text-xs text-gray-400">Remember me</span>
            </label>
            <a href="#" class="text-xs text-purple-400 hover:text-purple-300 transition-colors">Forgot password?</a>
          </div>

          <button type="submit" :disabled="authStore.loading || (!isLogin && form.password !== form.confirmPassword)"
            class="w-full btn-primary py-3 text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
            <svg v-if="authStore.loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            {{ authStore.loading ? 'Processing...' : isLogin ? 'Sign In to OMEN' : 'Create Account' }}
          </button>
        </form>

        <!-- Divider -->
        <div class="flex items-center gap-3 my-6">
          <div class="flex-1 border-t border-purple-900/30" />
          <span class="text-xs text-gray-600">or</span>
          <div class="flex-1 border-t border-purple-900/30" />
        </div>

        <!-- Social login -->
        <button @click="connectWallet" class="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg border border-purple-900/30 text-sm text-gray-300 hover:bg-purple-900/10 hover:border-purple-700/40 transition-all">
          💳 Connect Wallet
        </button>
      </div>

      <!-- Bottom text -->
      <p class="text-center text-xs text-gray-600 mt-6">
        By continuing, you agree to OMEN's
        <a href="#" class="text-purple-400 hover:underline">Terms</a> and
        <a href="#" class="text-purple-400 hover:underline">Privacy Policy</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store.js'

const router = useRouter()
const authStore = useAuthStore()
const isLogin = ref(true)
const showPassword = ref(false)
const form = reactive({ username: '', email: '', password: '', confirmPassword: '', remember: false })

async function handleSubmit() {
  try {
    if (isLogin.value) {
      await authStore.login(form.email, form.password)
    } else {
      if (form.password !== form.confirmPassword) return
      await authStore.register(form.username, form.email, form.password)
    }
    router.push('/dashboard')
  } catch (err) {
    console.error('Auth failed:', err)
  }
}

function connectWallet() { console.log('Wallet connect flow'); router.push('/dashboard') }
</script>
