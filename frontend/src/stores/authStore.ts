import { create } from 'zustand'

interface Operator {
  operator_id: string
  email: string
  username: string
}

interface AuthState {
  operator: Operator | null
  isLoading: boolean
  setOperator: (operator: Operator | null) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  operator: null,
  isLoading: true,
  setOperator: (operator) => set({ operator, isLoading: false }),
  setLoading: (loading) => set({ isLoading: loading }),
  logout: () => set({ operator: null, isLoading: false }),
}))
