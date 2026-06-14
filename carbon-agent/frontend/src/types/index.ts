// Tipos que mapean 1:1 con los schemas Pydantic del backend

export interface EmissionFactor {
  id: number
  category: string
  main_category: string
  display_name: string
  unit: string
  factor_kg_co2e: number
  source: string | null
}

export interface EmissionOut {
  id: number
  factor: EmissionFactor
  quantity: number
  amount_kg_co2e: number
  description: string | null
}

export interface ActivityOut {
  id: number
  user_id: string
  raw_text: string
  created_at: string
  main_category: string
  emissions: EmissionOut[]
}

export interface ActivityResponse {
  activity: ActivityOut
  total_kg_co2e: number
  message: string                 // recomendación o pregunta aclaratoria según is_question
  is_question: boolean
  clarifying_question?: string
}

export interface SummaryOut {
  user_id: string
  total_activities: number
  total_kg_co2e: number
  top_categories: { category: string; total_kg_co2e: number }[]
  period_days: number
  budget_kg_co2e: number
}

export interface ImprovementSuggestion {
  category: string
  current_kg: number
  pct_of_total: number
  action: string
  tip: string
  potential_saving_pct: number
}

export interface ImprovementsOut {
  suggestions: ImprovementSuggestion[]
  total_kg: number
  budget_kg: number
  period_days: number
}

export interface UserProfile {
  home_city?: string | null
  work_place?: string | null
  display_name?: string | null
}

export interface PortionEntry {
  category: string
  display_name: string
  unit: string
  default_quantity: number
  user_quantity: number | null
}

export interface UnknownItemOut {
  id: number
  user_id: string
  raw_term: string
  context: string | null
  guessed_category: string | null
  status: 'pending' | 'added' | 'rejected'
  created_at: string
}

export interface EmissionFactorOut {
  id: number
  category: string
  main_category: string
  display_name: string
  unit: string
  factor_kg_co2e: number
  default_quantity: number | null
  source_name: string | null
  source_year: number | null
  source_type: string | null
  source_detail: string | null
  source_url: string | null
  notes: string | null
}

export interface EmissionFactorCreate {
  category: string
  main_category: string
  display_name: string
  unit: string
  factor_kg_co2e: number
  default_quantity?: number | null
  source_name?: string | null
  source_year?: number | null
  source_type?: string | null
  source_detail?: string | null
  source_url?: string | null
  notes?: string | null
}

export interface EmissionFactorPatch {
  display_name?: string
  main_category?: string
  unit?: string
  factor_kg_co2e?: number
  default_quantity?: number | null
  source_name?: string | null
  source_year?: number | null
  source_type?: string | null
  source_detail?: string | null
  source_url?: string | null
  notes?: string | null
}

// Estado del chat
export type MessageRole = 'user' | 'assistant' | 'error'

export interface ChatMessage {
  id: string
  role: MessageRole
  text: string
  data?: ActivityResponse
  timestamp: Date
}
