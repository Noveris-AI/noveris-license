import { create } from 'zustand'

type Theme = 'light' | 'dark' | 'system'

interface ThemeState {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (theme: Theme) => void
  init: () => void
}

const STORAGE_KEY = 'naviam-theme'

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(resolved: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', resolved)
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: 'system',
  resolvedTheme: 'light',

  setTheme: (theme) => {
    const resolved = theme === 'system' ? getSystemTheme() : theme
    applyTheme(resolved)
    localStorage.setItem(STORAGE_KEY, theme)
    set({ theme, resolvedTheme: resolved })
  },

  init: () => {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
    const theme = stored || 'system'
    const resolved = theme === 'system' ? getSystemTheme() : theme
    applyTheme(resolved)
    set({ theme, resolvedTheme: resolved })

    const listener = (e: MediaQueryListEvent) => {
      const current = useThemeStore.getState().theme
      if (current === 'system') {
        const resolved = e.matches ? 'dark' : 'light'
        applyTheme(resolved)
        set({ resolvedTheme: resolved })
      }
    }
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', listener)
  },
}))
