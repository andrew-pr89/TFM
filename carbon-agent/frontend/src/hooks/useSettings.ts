import { useState, useCallback } from 'react'

export interface UserSettings {
  annualGoalTonnes: number  // 2–8 toneladas/año
}

const STORAGE_KEY = 'planet_pulse_settings'
const DEFAULTS: UserSettings = { annualGoalTonnes: 6 }

function load(): UserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch {}
  return DEFAULTS
}

export function useSettings() {
  const [settings, setSettings] = useState<UserSettings>(load)

  const update = useCallback((patch: Partial<UserSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...patch }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const annualGoalKg = settings.annualGoalTonnes * 1000

  return { settings, update, annualGoalKg }
}
