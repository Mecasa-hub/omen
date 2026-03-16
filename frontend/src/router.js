import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('./views/Home.vue'), meta: { title: 'OMEN — The Oracle Machine' } },
  { path: '/dashboard', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: 'Dashboard — OMEN', requiresAuth: true } },
  { path: '/oracle', name: 'oracle', component: () => import('./views/Oracle.vue'), meta: { title: 'Oracle — OMEN', requiresAuth: true } },
  { path: '/whales', name: 'whales', component: () => import('./views/Whales.vue'), meta: { title: 'Whale Tracker — OMEN', requiresAuth: true } },
  { path: '/trades', name: 'trades', component: () => import('./views/Trades.vue'), meta: { title: 'Trade History — OMEN', requiresAuth: true } },
  { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue'), meta: { title: 'Settings — OMEN', requiresAuth: true } },
  { path: '/login', name: 'login', component: () => import('./views/Login.vue'), meta: { title: 'Sign In — OMEN' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title || 'OMEN'
  if (to.meta.requiresAuth && !localStorage.getItem('omen_token')) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }
  if (to.name === 'login' && localStorage.getItem('omen_token')) {
    return next({ name: 'dashboard' })
  }
  next()
})

export default router
