import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { carbonApi } from '../services/api'

export const QUERY_KEYS = {
  history: (userId: string) => ['history', userId],
  summary: (userId: string) => ['summary', userId],
}

export function useHistory(userId = 'default') {
  return useQuery({
    queryKey: QUERY_KEYS.history(userId),
    queryFn: () => carbonApi.getHistory(userId),
    staleTime: 30_000,
  })
}

export function useSummary(userId = 'default') {
  return useQuery({
    queryKey: QUERY_KEYS.summary(userId),
    queryFn: () => carbonApi.getSummary(userId),
    staleTime: 30_000,
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