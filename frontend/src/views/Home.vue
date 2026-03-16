<template>
  <div class="min-h-screen bg-dark">
    <!-- Hero Section -->
    <section class="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-4">
      <!-- Background gradient layers -->
      <div class="absolute inset-0 bg-gradient-to-b from-purple-950/40 via-dark to-dark" />
      <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(124,58,237,0.15)_0%,transparent_70%)]" />
      <!-- Grid pattern -->
      <div class="absolute inset-0 opacity-[0.03]" style="background-image: linear-gradient(rgba(124,58,237,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.3) 1px, transparent 1px); background-size: 60px 60px;" />
      <!-- Floating particles -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div v-for="i in 20" :key="i" class="absolute rounded-full bg-purple-500/20 animate-float-particle"
          :style="{ width: Math.random() * 4 + 2 + 'px', height: Math.random() * 4 + 2 + 'px', left: Math.random() * 100 + '%', top: Math.random() * 100 + '%', animationDelay: Math.random() * 5 + 's', animationDuration: Math.random() * 10 + 10 + 's' }" />
      </div>

      <!-- Oracle Eye -->
      <div class="relative z-10 mb-8">
        <div class="oracle-eye-container">
          <!-- Outer glow rings -->
          <div class="absolute inset-0 rounded-full border border-purple-500/20 animate-pulse-slow scale-150" />
          <div class="absolute inset-0 rounded-full border border-purple-500/10 animate-pulse-slow scale-[2] animation-delay-1000" />
          <div class="absolute inset-0 rounded-full border border-purple-500/5 animate-pulse-slow scale-[2.5] animation-delay-2000" />
          <!-- Main eye -->
          <div class="relative w-32 h-32 md:w-40 md:h-40">
            <!-- Rotating outer ring -->
            <div class="absolute inset-0 rounded-full border-2 border-dashed border-purple-500/30 animate-spin-slow" />
            <!-- Eye background -->
            <div class="absolute inset-2 rounded-full bg-gradient-to-br from-purple-900/80 to-dark glow-purple-strong flex items-center justify-center">
              <!-- Iris -->
              <div class="w-20 h-20 md:w-24 md:h-24 rounded-full bg-gradient-to-br from-purple-600 to-purple-900 flex items-center justify-center animate-iris-pulse shadow-inner">
                <!-- Pupil -->
                <div class="w-10 h-10 md:w-12 md:h-12 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center shadow-lg glow-gold animate-pupil-track">
                  <div class="w-5 h-5 md:w-6 md:h-6 rounded-full bg-dark" />
                </div>
              </div>
            </div>
            <!-- Light reflection -->
            <div class="absolute top-6 left-8 w-4 h-4 rounded-full bg-white/20 blur-[2px]" />
          </div>
        </div>
      </div>

      <!-- Hero text -->
      <div class="relative z-10 text-center max-w-4xl mx-auto">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-900/20 text-xs text-purple-300 mb-6 animate-fade-in">
          <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Live on Polymarket · AI-Powered Predictions
        </div>
        <h1 class="text-5xl md:text-7xl lg:text-8xl font-black text-white mb-6 tracking-tight animate-title-in">
          <span class="text-gradient-main">OMEN</span>
        </h1>
        <p class="text-xl md:text-2xl text-gray-400 mb-2 font-light animate-subtitle-in">The Oracle Machine</p>
        <p class="text-base md:text-lg text-gray-500 mb-10 max-w-2xl mx-auto animate-subtitle-in animation-delay-200">
          Ask the AI Oracle. Watch agents debate. Copy whale traders.<br class="hidden md:block" />
          Predict the future on Polymarket — powered by artificial intelligence.
        </p>

        <div class="flex flex-col sm:flex-row items-center justify-center gap-4 animate-cta-in">
          <router-link to="/oracle" class="group relative inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-purple-600 to-purple-500 text-white text-lg font-bold rounded-xl shadow-2xl shadow-purple-900/50 hover:shadow-purple-700/50 transition-all duration-300 hover:scale-[1.02]">
            <span class="absolute inset-0 rounded-xl bg-gradient-to-r from-gold-500/0 via-gold-500/10 to-gold-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <span class="relative">🔮 Ask the Oracle</span>
            <svg class="w-5 h-5 relative group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
          </router-link>
          <router-link to="/whales" class="btn-ghost text-lg px-8 py-4">
            🐋 View Whale Board
          </router-link>
        </div>
      </div>

      <!-- Scroll indicator -->
      <div class="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <svg class="w-6 h-6 text-purple-500/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
      </div>
    </section>

    <!-- Stats ribbon -->
    <section class="relative py-12 border-y border-purple-900/20 bg-card/30">
      <div class="max-w-6xl mx-auto px-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div v-for="stat in stats" :key="stat.label">
            <div class="text-3xl md:text-4xl font-black text-gradient-purple mb-1">{{ stat.value }}</div>
            <div class="text-sm text-gray-500">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Features grid -->
    <section class="py-24 px-4">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-16">
          <span class="badge-purple mb-4 inline-block">Features</span>
          <h2 class="text-3xl md:text-5xl font-black text-white mb-4">Your Unfair <span class="text-gradient-main">Advantage</span></h2>
          <p class="text-gray-500 max-w-xl mx-auto">Everything you need to dominate prediction markets, powered by cutting-edge AI.</p>
        </div>
        <div class="grid md:grid-cols-3 gap-6">
          <div v-for="f in features" :key="f.title" class="glass-card-hover p-6 group">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center text-2xl mb-4 group-hover:scale-110 transition-transform" :class="f.bgClass">{{ f.icon }}</div>
            <h3 class="text-lg font-bold text-white mb-2">{{ f.title }}</h3>
            <p class="text-sm text-gray-400 leading-relaxed">{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section class="py-24 px-4 bg-card/20">
      <div class="max-w-5xl mx-auto">
        <div class="text-center mb-16">
          <span class="badge-gold mb-4 inline-block">How It Works</span>
          <h2 class="text-3xl md:text-5xl font-black text-white mb-4">Three Steps to <span class="text-gradient-gold">Profit</span></h2>
        </div>
        <div class="grid md:grid-cols-3 gap-8">
          <div v-for="(step, idx) in steps" :key="idx" class="relative text-center">
            <div class="w-16 h-16 rounded-full bg-gradient-to-br from-purple-600 to-gold-500 flex items-center justify-center text-2xl font-black text-white mx-auto mb-6 glow-purple">
              {{ idx + 1 }}
            </div>
            <h3 class="text-lg font-bold text-white mb-2">{{ step.title }}</h3>
            <p class="text-sm text-gray-400">{{ step.desc }}</p>
            <div v-if="idx < 2" class="hidden md:block absolute top-8 left-[60%] w-[80%] border-t border-dashed border-purple-700/30" />
          </div>
        </div>
      </div>
    </section>

    <!-- Pricing -->
    <section class="py-24 px-4">
      <div class="max-w-5xl mx-auto">
        <div class="text-center mb-16">
          <span class="badge-purple mb-4 inline-block">Pricing</span>
          <h2 class="text-3xl md:text-5xl font-black text-white mb-4">Simple <span class="text-gradient-main">Credits</span></h2>
          <p class="text-gray-500">No subscriptions. Buy credits, use them when you want.</p>
        </div>
        <div class="grid md:grid-cols-3 gap-6">
          <div v-for="plan in plans" :key="plan.name" class="glass-card p-6 relative" :class="{ 'border-gold-500/50 glow-gold': plan.popular }">
            <div v-if="plan.popular" class="absolute -top-3 left-1/2 -translate-x-1/2 badge-gold text-xs px-3 py-1">Most Popular</div>
            <div class="text-center mb-6">
              <span class="text-3xl">{{ plan.icon }}</span>
              <h3 class="text-xl font-bold text-white mt-3">{{ plan.name }}</h3>
              <div class="mt-2"><span class="text-4xl font-black text-white">${{ plan.price }}</span></div>
              <p class="text-sm text-gray-500 mt-1">{{ plan.credits }} credits</p>
            </div>
            <ul class="space-y-2 mb-6">
              <li v-for="f in plan.features" :key="f" class="flex items-center gap-2 text-sm text-gray-400">
                <span class="text-purple-400">✓</span> {{ f }}
              </li>
            </ul>
            <button class="w-full" :class="plan.popular ? 'btn-gold' : 'btn-ghost'">Get Started</button>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="py-24 px-4">
      <div class="max-w-3xl mx-auto text-center">
        <div class="glass-card p-12 relative overflow-hidden">
          <div class="absolute inset-0 bg-gradient-to-br from-purple-600/10 to-gold-500/5" />
          <div class="relative">
            <span class="text-5xl mb-6 block">🔮</span>
            <h2 class="text-3xl md:text-4xl font-black text-white mb-4">Ready to See the Future?</h2>
            <p class="text-gray-400 mb-8 max-w-lg mx-auto">Join thousands of traders using OMEN to gain an edge on Polymarket. Start with 10 free credits.</p>
            <router-link to="/login" class="btn-primary text-lg px-10 py-4 inline-flex items-center gap-2">
              Start Predicting — Free <span class="text-gold-400">→</span>
            </router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-purple-900/20 py-12 px-4">
      <div class="max-w-6xl mx-auto">
        <div class="grid md:grid-cols-4 gap-8 mb-8">
          <div>
            <div class="flex items-center gap-2 mb-4">
              <img src="@/assets/logo.svg" class="w-8 h-8" />
              <span class="text-lg font-bold text-gradient-main">OMEN</span>
            </div>
            <p class="text-sm text-gray-500">AI-powered prediction intelligence for Polymarket.</p>
          </div>
          <div v-for="col in footerCols" :key="col.title">
            <h4 class="text-sm font-semibold text-gray-300 mb-3">{{ col.title }}</h4>
            <ul class="space-y-2">
              <li v-for="link in col.links" :key="link">
                <a href="#" class="text-sm text-gray-500 hover:text-purple-400 transition-colors">{{ link }}</a>
              </li>
            </ul>
          </div>
        </div>
        <div class="border-t border-purple-900/20 pt-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <p class="text-xs text-gray-600">© 2026 OMEN — The Oracle Machine. Not financial advice.</p>
          <div class="flex items-center gap-4">
            <a href="#" class="text-gray-600 hover:text-purple-400 transition-colors">𝕏</a>
            <a href="#" class="text-gray-600 hover:text-purple-400 transition-colors">Discord</a>
            <a href="#" class="text-gray-600 hover:text-purple-400 transition-colors">Docs</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
const stats = [
  { value: '47K+', label: 'Predictions Made' },
  { value: '73%', label: 'Avg Win Rate' },
  { value: '$2.4M', label: 'Whale Volume Tracked' },
  { value: '1,200+', label: 'Active Traders' },
]

const features = [
  { icon: '🔮', title: 'AI Oracle', desc: 'Ask any question about Polymarket outcomes. Our multi-agent AI analyzes on-chain data, news, and sentiment to deliver predictions with confidence scores.', bgClass: 'from-purple-600/20 to-purple-900/20' },
  { icon: '⚔️', title: 'War Room Debates', desc: 'Watch Bull, Bear, and Analyst AI agents debate in real-time. See their arguments, confidence levels, and vote tallies before you trade.', bgClass: 'from-red-600/20 to-red-900/20' },
  { icon: '🐋', title: 'Whale Tracking', desc: 'Follow the smartest wallets on Polymarket. See their ROI, win rates, and positions. One click to copy their trades.', bgClass: 'from-blue-600/20 to-blue-900/20' },
  { icon: '🤖', title: 'AutoPilot Trading', desc: 'Set your risk level, pick your whales, and let AI execute trades automatically. Smart position sizing and daily limits keep you safe.', bgClass: 'from-gold-600/20 to-gold-900/20' },
  { icon: '🏆', title: 'Brag Cards', desc: 'Won big? Generate a shareable brag card with your prediction, confidence score, and profit. Flex on 𝕏 with one click.', bgClass: 'from-green-600/20 to-green-900/20' },
  { icon: '📊', title: 'Portfolio Dashboard', desc: 'Track every trade, see your P&L over time, manage positions, and monitor your prediction accuracy with detailed analytics.', bgClass: 'from-pink-600/20 to-pink-900/20' },
]

const steps = [
  { title: 'Ask the Oracle', desc: 'Type any Polymarket question. AI agents research, analyze, and debate to form a prediction with a confidence score.' },
  { title: 'Follow the Whales', desc: 'Browse the leaderboard of top-performing wallets. See their track record and copy their trades with one click.' },
  { title: 'Profit & Brag', desc: 'When your prediction wins, generate a brag card and share it. Build your rep as a prediction market oracle.' },
]

const plans = [
  { name: 'Starter', icon: '⚡', price: 5, credits: 50, popular: false, features: ['50 Oracle queries', 'Whale leaderboard access', 'Basic trade history', 'Community support'] },
  { name: 'Pro', icon: '🔮', price: 15, credits: 200, popular: true, features: ['200 Oracle queries', 'War Room live debates', 'AutoPilot copy trading', 'Priority AI models', 'Brag card generator'] },
  { name: 'Whale', icon: '🐋', price: 30, credits: 500, popular: false, features: ['500 Oracle queries', 'Everything in Pro', 'Advanced whale analytics', 'API access', 'Custom alerts'] },
]

const footerCols = [
  { title: 'Product', links: ['Oracle', 'Whale Board', 'AutoPilot', 'Pricing'] },
  { title: 'Resources', links: ['Documentation', 'API Reference', 'Blog', 'Changelog'] },
  { title: 'Company', links: ['About', 'Terms of Service', 'Privacy Policy', 'Contact'] },
]
</script>

<style scoped>
@keyframes float-particle { 0%, 100% { transform: translateY(0) translateX(0); opacity: 0; } 10% { opacity: 1; } 90% { opacity: 1; } 50% { transform: translateY(-100px) translateX(20px); } }
@keyframes spin-slow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes iris-pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(0.95); } }
@keyframes pupil-track { 0%, 100% { transform: translate(0, 0); } 25% { transform: translate(2px, -1px); } 50% { transform: translate(-1px, 2px); } 75% { transform: translate(-2px, -1px); } }
@keyframes pulse-slow { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 0.6; transform: scale(1.05); } }
@keyframes fade-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes title-in { from { opacity: 0; transform: translateY(20px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }

.animate-float-particle { animation: float-particle linear infinite; }
.animate-spin-slow { animation: spin-slow 20s linear infinite; }
.animate-iris-pulse { animation: iris-pulse 4s ease-in-out infinite; }
.animate-pupil-track { animation: pupil-track 6s ease-in-out infinite; }
.animate-pulse-slow { animation: pulse-slow 3s ease-in-out infinite; }
.animate-fade-in { animation: fade-in 0.8s ease-out forwards; }
.animate-title-in { animation: title-in 1s ease-out forwards; }
.animate-subtitle-in { animation: fade-in 1s ease-out 0.3s both; }
.animate-cta-in { animation: fade-in 1s ease-out 0.6s both; }
.animation-delay-200 { animation-delay: 0.5s; }
.animation-delay-1000 { animation-delay: 1s; }
.animation-delay-2000 { animation-delay: 2s; }
.animate-float { animation: iris-pulse 3s ease-in-out infinite; }
.oracle-eye-container { position: relative; display: flex; align-items: center; justify-content: center; }
</style>
