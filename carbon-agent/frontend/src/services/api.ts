import axios from 'axios'
import type { ActivityResponse, ActivityOut, SummaryOut, ImprovementsOut, UserProfile, PortionEntry } from '../types'

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

  getHistory: async (limit = 50): Promise<ActivityOut[]> => {
    const { data } = await api.get<ActivityOut[]>('/history', { params: { limit } })
    return data
  },

  getSummary: async (periodDays = 30, annualGoalKg = 6000): Promise<SummaryOut> => {
    const { data } = await api.get<SummaryOut>('/summary', {
      params: { period_days: periodDays, annual_goal_kg: annualGoalKg },
    })
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

  getPortions: async (): Promise<PortionEntry[]> => {
    const { data } = await api.get<PortionEntry[]>('/portions')
    return data
  },

  updatePortions: async (portions: Record<string, number>): Promise<PortionEntry[]> => {
    const { data } = await api.patch<PortionEntry[]>('/portions', portions)
    return data
  },
}
