import axios from 'axios'
import type { ActivityResponse, ActivityOut, EmissionOut, SummaryOut, ImprovementsOut, UserProfile, PortionEntry, RecurringActivity, UnknownItemOut, EmissionFactorOut, EmissionFactorCreate, EmissionFactorPatch } from '../types'

const rawApiUrl = import.meta.env.VITE_API_URL
const normalizedApiUrl = rawApiUrl
  ? rawApiUrl.startsWith('http') ? rawApiUrl : `https://${rawApiUrl}`
  : null
const baseURL = normalizedApiUrl ? `${normalizedApiUrl}/api` : '/api'

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
})

let _interceptorId: number | null = null

export function setupAuthInterceptor(getToken: () => Promise<string>) {
  if (_interceptorId !== null) {
    api.interceptors.request.eject(_interceptorId)
  }
  _interceptorId = api.interceptors.request.use(async (config) => {
    const token = await getToken()
    config.headers.Authorization = `Bearer ${token}`
    return config
  })
}

export const carbonApi = {
  postActivity: async (rawText: string): Promise<ActivityResponse> => {
    const { data } = await api.post<ActivityResponse>('/activity', { raw_text: rawText })
    return data
  },

  getHistory: async (limit = 200, dateFrom?: string, dateTo?: string): Promise<ActivityOut[]> => {
    const params: Record<string, unknown> = { limit }
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    const { data } = await api.get<ActivityOut[]>('/history', { params })
    return data
  },

  getSummary: async (periodDays = 30, annualGoalKg = 6000, dateFrom?: string, dateTo?: string): Promise<SummaryOut> => {
    const params: Record<string, unknown> = { period_days: periodDays, annual_goal_kg: annualGoalKg }
    if (dateFrom && dateTo) {
      params.date_from = dateFrom
      params.date_to = dateTo
    }
    const { data } = await api.get<SummaryOut>('/summary', { params })
    return data
  },

  deleteHistory: async (): Promise<void> => {
    await api.delete('/history')
  },

  deleteActivity: async (activityId: number): Promise<void> => {
    await api.delete(`/history/${activityId}`)
  },

  patchActivity: async (activityId: number, rawText: string, createdAt: string | null): Promise<ActivityOut> => {
    const { data } = await api.patch<ActivityOut>(`/history/${activityId}`, {
      raw_text: rawText,
      created_at: createdAt,
    })
    return data
  },

  patchEmissionQuantity: async (emissionId: number, quantity: number): Promise<EmissionOut> => {
    const { data } = await api.patch<EmissionOut>(`/emissions/${emissionId}`, { quantity })
    return data
  },

  getImprovements: async (periodDays = 30, annualGoalKg = 6000): Promise<ImprovementsOut> => {
    const { data } = await api.get<ImprovementsOut>('/improvements', {
      params: { period_days: periodDays, annual_goal_kg: annualGoalKg },
    })
    return data
  },

  getProfile: async (): Promise<UserProfile> => {
    const { data } = await api.get<UserProfile>('/profile')
    return data
  },

  updateProfile: async (profile: UserProfile): Promise<UserProfile> => {
    const { data } = await api.patch<UserProfile>('/profile', profile)
    return data
  },

  checkAddress: async (address: string): Promise<boolean> => {
    const { data } = await api.get<{ found: boolean }>('/geocode/check', { params: { address } })
    return data.found
  },

  getPortions: async (): Promise<PortionEntry[]> => {
    const { data } = await api.get<PortionEntry[]>('/portions')
    return data
  },

  updatePortions: async (portions: Record<string, number>): Promise<PortionEntry[]> => {
    const { data } = await api.patch<PortionEntry[]>('/portions', portions)
    return data
  },

  getRecurring: async (): Promise<RecurringActivity[]> => {
    const { data } = await api.get<RecurringActivity[]>('/recurring')
    return data
  },

  updateRecurring: async (items: RecurringActivity[]): Promise<RecurringActivity[]> => {
    const { data } = await api.patch<RecurringActivity[]>('/recurring', items)
    return data
  },

  applyRecurring: async (): Promise<{ applied: number }> => {
    const { data } = await api.post<{ applied: number }>('/recurring/apply')
    return data
  },

  // ── Admin ──────────────────────────────────────────────────────────────────
  getUnknownItems: async (status = 'pending'): Promise<UnknownItemOut[]> => {
    const { data } = await api.get<UnknownItemOut[]>('/admin/unknown-items', { params: { status, limit: 200 } })
    return data
  },

  deleteUnknownItem: async (id: number): Promise<void> => {
    await api.delete(`/admin/unknown-items/${id}`)
  },

  batchDeleteUnknownItems: async (ids: number[]): Promise<void> => {
    await api.delete('/admin/unknown-items', { data: ids })
  },

  updateUnknownItemStatus: async (id: number, status: string): Promise<UnknownItemOut> => {
    const { data } = await api.patch<UnknownItemOut>(`/admin/unknown-items/${id}`, null, { params: { status } })
    return data
  },

  listFactors: async (search = ''): Promise<EmissionFactorOut[]> => {
    const { data } = await api.get<EmissionFactorOut[]>('/admin/factors', { params: search ? { search } : {} })
    return data
  },

  createFactor: async (payload: EmissionFactorCreate): Promise<EmissionFactorOut> => {
    const { data } = await api.post<EmissionFactorOut>('/admin/factors', payload)
    return data
  },

  updateFactor: async (id: number, payload: EmissionFactorPatch): Promise<EmissionFactorOut> => {
    const { data } = await api.patch<EmissionFactorOut>(`/admin/factors/${id}`, payload)
    return data
  },

  deleteFactor: async (id: number): Promise<void> => {
    await api.delete(`/admin/factors/${id}`)
  },
}
