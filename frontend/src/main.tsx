import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import './index.css'
import '@/shared/i18n'
import { licenseRouter } from './modules/link/AppRouter'
import { useThemeStore } from './stores/themeStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: (failureCount, error: any) => {
        if (error?.response?.status === 401) return false
        return failureCount < 3
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})

function ThemeInit() {
  useEffect(() => {
    useThemeStore.getState().init()
  }, [])
  return null
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeInit />
      <RouterProvider router={licenseRouter} />
    </QueryClientProvider>
  </StrictMode>,
)
