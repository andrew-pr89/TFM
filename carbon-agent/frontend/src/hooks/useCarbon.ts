import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth0 } from '@auth0/auth0-react'
import { carbonApi } from '../services/api'
import type { UserProfile, ActivityOut } from '../types'

export const QUERY_KEYS = {
  history:      (userId: string) => ['history', userId],
  summary:      (userId: string) => ['summary', userId],
  improvements: (userId: string) => ['improvements', userId],
  profile:      (userId: string) => ['profile', userId],
  portions:     (userId: string) => ['portions', userId],
}

function useUserId() {
  const { user } = useAuth0()
  return user?.sub ?? 'unknown'
}

export function useHistory() {
  const userId = useUserId()
  return useQuery({
    queryKey: QUERY_KEYS.history(userId),
    queryFn: () => carbonApi.getHistory(),
    staleTime: 30_000,
    enabled: userId !== 'unknown',
  })
}

export function useSummary(annualGoalKg = 6000) {
  const userId = useUserId()
  return useQuery({
    queryKey: [...QUERY_KEYS.summary(userId), annualGoalKg],
    queryFn: () => carbonApi.getSummary(30, annualGoalKg),
    staleTime: 30_000,
    enabled: userId !== 'unknown',
  })
}

export function useImprovements(annualGoalKg = 6000) {
  const userId = useUserId()
  return useQuery({
    queryKey: [...QUERY_KEYS.improvements(userId), annualGoalKg],
    queryFn: () => carbonApi.getImprovements(30, annualGoalKg),
    staleTime: 60_000,
    enabled: userId !== 'unknown',
  })
}

export function usePostActivity() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => carbonApi.postActivity(text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useDeleteHistory() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => carbonApi.deleteHistory(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useDeleteActivity() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (activityId: number) => carbonApi.deleteActivity(activityId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.history(userId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.summary(userId) })
    },
  })
}

export function useEditActivity() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rawText, createdAt }: { id: number; rawText: string; createdAt: string | null }) =>
      carbonApi.patchActivity(id, rawText, createdAt),
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

export function useProfile() {
  const userId = useUserId()
  return useQuery({
    queryKey: QUERY_KEYS.profile(userId),
    queryFn: () => carbonApi.getProfile(),
    staleTime: 60_000,
    enabled: userId !== 'unknown',
  })
}

export function useUpdateProfile() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (profile: UserProfile) => carbonApi.updateProfile(profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.profile(userId) })
    },
  })
}

export function usePortions() {
  const userId = useUserId()
  return useQuery({
    queryKey: QUERY_KEYS.portions(userId),
    queryFn: () => carbonApi.getPortions(),
    staleTime: 60_000,
    enabled: userId !== 'unknown',
  })
}

export function useUpdatePortions() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (portions: Record<string, number>) => carbonApi.updatePortions(portions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.portions(userId) })
    },
  })
}
