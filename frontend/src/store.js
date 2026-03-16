import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from './api.js'

// Auth Store
export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('omen_token') || null)
  const loading = ref(false)
  const error = ref(null)

  const isAuthenticated = computed(() => !!token.value)
  const username = computed(() => user.value?.username || 'User')
  const avatar = computed(() => user.value?.avatar || null)

  async function login(email, password) {
    loading.value = true; error.value = null
    try {
      const res = await api.login(email, password)
      token.value = res.data.access_token
      localStorage.setItem('omen_token', token.value)
      await fetchProfile()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      throw err
    } finally { loading.value = false }
  }

  async function register(uname, email, password) {
    loading.value = true; error.value = null
    try {
      await api.register(uname, email, password)
      await login(email, password)
    } catch (err) {
      error.value = err.response?.data?.detail || 'Registration failed'
      throw err
    } finally { loading.value = false }
  }

  async function fetchProfile() {
    try { const res = await api.getProfile(); user.value = res.data }
    catch (err) { console.error('Profile fetch failed:', err) }
  }

  function logout() {
    token.value = null; user.value = null
    localStorage.removeItem('omen_token')
  }

  if (token.value) fetchProfile()

  return { user, token, loading, error, isAuthenticated, username, avatar, login, register, fetchProfile, logout }
})

// Credit Store
export const useCreditStore = defineStore('credits', () => {
  const balance = ref(0)
  const loading = ref(false)
  const history = ref([])

  async function fetchBalance() {
    loading.value = true
    try { const res = await api.getCreditBalance(); balance.value = res.data.balance }
    catch (err) { console.error('Credits fetch failed:', err) }
    finally { loading.value = false }
  }

  async function fetchHistory() {
    try { const res = await api.getCreditHistory(); history.value = res.data }
    catch (err) { console.error('Credit history failed:', err) }
  }

  async function purchaseCredits(amount, paymentMethod) {
    loading.value = true
    try {
      const res = await api.purchaseCredits(amount, paymentMethod)
      balance.value = res.data.new_balance
      return res.data
    } catch (err) { throw err }
    finally { loading.value = false }
  }

  function deductCredit(amount = 1) { balance.value = Math.max(0, balance.value - amount) }

  return { balance, loading, history, fetchBalance, fetchHistory, purchaseCredits, deductCredit }
})

// Oracle Store
export const useOracleStore = defineStore('oracle', () => {
  const messages = ref([])
  const debates = ref([])
  const isTyping = ref(false)
  const ws = ref(null)
  const wsConnected = ref(false)
  const currentPrediction = ref(null)
  let reconnectAttempts = 0

  function addMessage(role, content, meta = {}) {
    messages.value.push({
      id: Date.now() + Math.random(), role, content, meta,
      timestamp: new Date().toISOString(),
    })
  }

  async function askOracle(question) {
    addMessage('user', question)
    isTyping.value = true
    try {
      const res = await api.askOracle(question)
      const d = res.data
      addMessage('assistant', d.answer, {
        prediction: d.prediction, confidence: d.confidence,
        market: d.market, sources: d.sources,
      })
      currentPrediction.value = d.prediction
      return d
    } catch (err) {
      addMessage('system', 'Oracle connection lost. Please try again.')
      throw err
    } finally { isTyping.value = false }
  }

  function connectWarRoom() {
    if (ws.value?.readyState === WebSocket.OPEN) return
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws.value = new WebSocket(`${protocol}//${location.host}/ws/warroom`)

    ws.value.onopen = () => { wsConnected.value = true; reconnectAttempts = 0 }
    ws.value.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'debate_message') {
          debates.value.push({
            id: Date.now() + Math.random(), agent: data.agent,
            content: data.content, confidence: data.confidence,
            timestamp: new Date().toISOString(),
          })
          if (debates.value.length > 100) debates.value = debates.value.slice(-100)
        }
      } catch (err) { console.error('[WarRoom] Parse error:', err) }
    }
    ws.value.onclose = () => {
      wsConnected.value = false
      if (reconnectAttempts < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts++), 30000)
        setTimeout(connectWarRoom, delay)
      }
    }
    ws.value.onerror = (err) => console.error('[WarRoom] Error:', err)
  }

  function disconnectWarRoom() { if (ws.value) { ws.value.close(); ws.value = null } }
  function clearChat() { messages.value = []; currentPrediction.value = null }

  return { messages, debates, isTyping, wsConnected, currentPrediction, addMessage, askOracle, connectWarRoom, disconnectWarRoom, clearChat }
})

// Whale Store
export const useWhaleStore = defineStore('whales', () => {
  const whales = ref([])
  const followedWhales = ref([])
  const loading = ref(false)
  const selectedWhale = ref(null)
  const sortBy = ref('roi')
  const sortOrder = ref('desc')

  const sortedWhales = computed(() => {
    return [...whales.value].sort((a, b) => {
      const aV = a[sortBy.value] || 0, bV = b[sortBy.value] || 0
      return sortOrder.value === 'desc' ? bV - aV : aV - bV
    })
  })

  async function fetchWhales() {
    loading.value = true
    try { whales.value = (await api.getWhales()).data }
    catch (err) { console.error('Whales fetch failed:', err) }
    finally { loading.value = false }
  }

  async function fetchFollowedWhales() {
    try { followedWhales.value = (await api.getFollowedWhales()).data }
    catch (err) { console.error('Followed whales failed:', err) }
  }

  async function followWhale(address) {
    await api.followWhale(address); followedWhales.value.push(address)
  }

  async function unfollowWhale(address) {
    await api.unfollowWhale(address)
    followedWhales.value = followedWhales.value.filter(a => a !== address)
  }

  function setSort(field) {
    if (sortBy.value === field) sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
    else { sortBy.value = field; sortOrder.value = 'desc' }
  }

  return { whales, followedWhales, loading, selectedWhale, sortBy, sortOrder, sortedWhales, fetchWhales, fetchFollowedWhales, followWhale, unfollowWhale, setSort }
})
