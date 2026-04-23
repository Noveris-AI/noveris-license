import { create } from 'zustand'
import i18n from '@/shared/i18n'

type LangMode = 'system' | 'zh' | 'en'

const LANG_MODE_KEY = 'naviam-lang-mode'
const LANG_KEY = 'naviam-language'

function getSystemLang(): 'zh' | 'en' {
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function getInitialLangMode(): LangMode {
  const stored = localStorage.getItem(LANG_MODE_KEY) as LangMode | null
  if (stored === 'zh' || stored === 'en' || stored === 'system') return stored
  // Migrate: if naviam-language was explicitly set by the old toggle, treat it as explicit
  const lang = localStorage.getItem(LANG_KEY)
  if (lang === 'zh') return 'zh'
  if (lang === 'en') return 'en'
  return 'system'
}

interface LangState {
  langMode: LangMode
  setLangMode: (mode: LangMode) => void
}

export const useLangStore = create<LangState>()((set) => ({
  langMode: getInitialLangMode(),
  setLangMode: (mode) => {
    localStorage.setItem(LANG_MODE_KEY, mode)
    if (mode === 'system') {
      localStorage.removeItem(LANG_KEY)
      i18n.changeLanguage(getSystemLang())
    } else {
      localStorage.setItem(LANG_KEY, mode)
      i18n.changeLanguage(mode)
    }
    set({ langMode: mode })
  },
}))
