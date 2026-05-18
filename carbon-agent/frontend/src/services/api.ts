import axios from 'axios'
import type { ActivityResponse, ActivityOut, SummaryOut, ImprovementsOut, UserProfile } from '../types'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const carbonApi = {
  postActivity: async (rawText: string, userId = 'default'): Promise<ActivityResponse> => {
    const { data } = await api.post<ActivityResponse>('/activity', {
      raw_text: rawText,
      user_id: userId,
    })
    return data
  },

  getHistory: async (userId = 'default', limit = 50): Promise<ActivityOut[]> => {
    const { data } = await api.get<ActivityOut[]>('/history', {
      params: { user_id: userId, limit },
    })
    return data
  },

  getSummary: async (userId = 'default', periodDays = 30, annualGoalKg = 6000): Promise<SummaryOut> => {
    const { data } = await api.get<SummaryOut>('/summary', {
      params: { user_id: userId, period_days: periodDays, annual_goal_kg: annualGoalKg },
    })
    return data
  },

  deleteHistory: async (userId = 'default'): Promise<void> => {
    await api.delete('/history', { params: { user_id: userId } })
  },

  deleteActivity: async (activityId: number, userId = 'default'): Promise<void> => {
    await api.delete(`/history/${activityId}`, { params: { user_id: userId } })
  },

  patchActivity: async (activityId: number, rawText: string, createdAt: string | null, userId = 'default'): Promise<ActivityOut> => {
    const { data } = await api.patch<ActivityOut>(`/history/${activityId}`, {
      raw_text: rawText,
      created_at: createdAt,
    }, { params: { user_id: userId } })
    return data
  },

  getImprovements: async (userId = 'default', periodDays = 30, annualGoalKg = 6000): Promise<ImprovementsOut> => {
    const { data } = await api.get<ImprovementsOut>('/improvements', {
      params: { user_id: userId, period_days: periodDays, annual_goal_kg: annualGoalKg },
    })
    return data
  },

  getProfile: async (userId = 'default'): Promise<UserProfile> => {
    const { data } = await api.get<UserProfile>('/profile', { params: { user_id: userId } })
    return data
  },

  updateProfile: async (profile: UserProfile, userId = 'default'): Promise<UserProfile> => {
    const { data } = await api.patch<UserProfile>('/profile', profile, { params: { user_id: userId } })
    return data
  },
}