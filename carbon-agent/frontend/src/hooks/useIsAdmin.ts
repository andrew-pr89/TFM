import { useAuth0 } from '@auth0/auth0-react'

const ROLES_CLAIM = 'https://planet-pulse-api/roles'

export function useIsAdmin(): boolean {
  const { user } = useAuth0()
  const roles: string[] = user?.[ROLES_CLAIM] ?? []
  return roles.includes('admin')
}
