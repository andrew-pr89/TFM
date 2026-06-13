import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { carbonApi } from '../services/api'
import type { UserProfile, ActivityOut } from '../types'

export const QUERY_KEYS = {
  history: (userId: string) => ['history', userId],
  summary: (userId: string) => ['summary', userId],
  improvements: (userId: string) => ['improvements', userId],
  profile: (userId: string) => ['profile', userId],
  portions: (userId: string) => ['portions', userId],
}

export function useHistory(userId = 'default') {
  return useQuery({
    queryKey: QUERY_KEYS.history(userId),
    queryFn: () => carbonApi.getHistory(userId),
    staleTime: 30_000,
  })
}

export function useSummary(userId = 'default', annualGoalKg = 6000) {
  return useQuery({
    queryKey: [...QUERY_KEYS.summary(userId), annualGoalKg],
    queryFn: () => carbonApi.getSummary(userId, 30, annualGoalKg),
    staleTime: 30_000,
  })
}

export function useImprovements(userId = 'default', annualGoalKg = 6000) {
  return useQuery({
    queryKey: [...QUERY_KEYS.improvements(userId), annualGoalKg],
    queryFn: () => carbonApi.getImprovements(userId, 30, annualGoalKg),
    staleTime: 60_000,
  })
}

export function usePostActivity(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => carbonApi.postActivity(text, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useDeleteHistory(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => carbonApi.deleteHistory(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useDeleteActivity(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (activityId: number) => carbonApi.deleteActivity(activityId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useEditActivity(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rawText, createdAt }: { id: number; rawText: string; createdAt: string | null }) =>
      carbonApi.patchActivity(id, rawText, createdAt, userId),
    onSuccess: (updated: ActivityOut) => {
      queryClient.setQueryData(
        QUERY_KEYS.history(userId),
        (old: ActivityOut[] | undefined) =>
          old?.map(a => a.id === updated.id ? updated : a) ?? [updated],
      )
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useProfile(userId = 'default') {
  return useQuery({
    queryKey: QUERY_KEYS.profile(userId),
    queryFn: () => carbonApi.getProfile(userId),
    staleTime: 60_000,
  })
}

export function useUpdateProfile(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (profile: UserProfile) => carbonApi.updateProfile(profile, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.profile(userId) })
    },
  })
}

export function usePortions(userId = 'default') {
  return useQuery({
    queryKey: QUERY_KEYS.portions(userId),
    queryFn: () => carbonApi.getPortions(userId),
    staleTime: 60_000,
  })
}

export function useUpdatePortions(userId = 'default') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (portions: Record<string, number>) => carbonApi.updatePortions(portions, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.portions(userId) })
    },
  })
}