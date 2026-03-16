import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000, headers: { 'Content-Type': 'application/json' } })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('omen_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}, (error) => Promise.reject(error))

api.interceptors.response.use((r) => r, (error) => {
  if (error.response?.status === 401) {
    localStorage.removeItem('omen_token')
    if (window.location.pathname !== '/login') window.location.href = '/login'
  }
  return Promise.reject(error)
})

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password })
export const register = (username, email, password) => api.post('/auth/register', { username, email, password })
export const getProfile = () => api.get('/auth/profile')
export const updateProfile = (data) => api.put('/auth/profile', data)

// Credits
export const getCreditBalance = () => api.get('/credits/balance')
export const getCreditHistory = () => api.get('/credits/history')
export const purchaseCredits = (amount, paymentMethod) => api.post('/credits/purchase', { amount, payment_method: paymentMethod })

// Oracle
export const askOracle = (question) => api.post('/oracle/ask', { question })
export const getOracleHistory = () => api.get('/oracle/history')
export const getPrediction = (id) => api.get(`/oracle/prediction/${id}`)

// Whales
export const getWhales = () => api.get('/whale/leaderboard')
export const getWhaleDetail = (address) => api.get(`/whale/${address}`)
export const getFollowedWhales = () => api.get('/whale/followed')
export const followWhale = (address) => api.post(`/whale/${address}/follow`)
export const unfollowWhale = (address) => api.delete(`/whale/${address}/follow`)
export const getWhaleActivity = (address) => api.get(`/whale/${address}/activity`)

// Trading
export const getTrades = (params = {}) => api.get('/trading/history', { params })
export const getTradeDetail = (id) => api.get(`/trading/${id}`)
export const getPositions = () => api.get('/trading/positions')
export const getTradeStats = () => api.get('/trading/stats')
export const getAutoPilotConfig = () => api.get('/trading/autopilot')
export const updateAutoPilotConfig = (config) => api.put('/trading/autopilot', config)
export const toggleAutoPilot = (enabled) => api.post('/trading/autopilot/toggle', { enabled })

// Social
export const shareTrade = (tradeId) => api.post(`/social/share/${tradeId}`)
export const getBragCard = (tradeId) => api.get(`/social/brag/${tradeId}`)

// Settings
export const getNotificationPrefs = () => api.get('/auth/notifications')
export const updateNotificationPrefs = (prefs) => api.put('/auth/notifications', prefs)
export const connectWallet = (walletAddress, signature) => api.post('/auth/wallet', { wallet_address: walletAddress, signature })

export default {
  login, register, getProfile, updateProfile,
  getCreditBalance, getCreditHistory, purchaseCredits,
  askOracle, getOracleHistory, getPrediction,
  getWhales, getWhaleDetail, getFollowedWhales, followWhale, unfollowWhale, getWhaleActivity,
  getTrades, getTradeDetail, getPositions, getTradeStats, getAutoPilotConfig, updateAutoPilotConfig, toggleAutoPilot,
  shareTrade, getBragCard, getNotificationPrefs, updateNotificationPrefs, connectWallet,
}
