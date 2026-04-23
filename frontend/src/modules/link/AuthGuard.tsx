import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/shared/api/client'

export function AuthGuard() {
  const { operator, isLoading, setOperator, setLoading } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    if (operator) return

    api.get<{ operator_id: string; email: string; username: string }>('/auth/me')
      .then((data) => {
        setOperator({
          operator_id: data.operator_id,
          email: data.email,
          username: data.username,
        })
      })
      .catch(() => {
        setLoading(false)
      })
  }, [operator, setOperator, setLoading])

  if (isLoading && !operator) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="loading" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
    )
  }

  if (!operator) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
