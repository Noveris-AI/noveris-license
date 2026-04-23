import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/shared/api/client'

const loginSchema = z.object({
  email: z.string().min(1, '请输入邮箱'),
  password: z.string().min(1, '请输入密码'),
})

type LoginForm = z.infer<typeof loginSchema>

export function LoginPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const setOperator = useAuthStore((s) => s.setOperator)
  const [serverError, setServerError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    setIsSubmitting(true)
    setServerError('')
    try {
      const result = await api.post<{ email: string; username: string }>('/auth/login', data)
      setOperator({
        operator_id: '',
        email: result.email,
        username: result.username,
      })
      navigate('/', { replace: true })
    } catch (err: any) {
      setServerError(err.message || t('auth.loginError'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">
          <h1>{t('common.naviam')}</h1>
          <p>{t('auth.loginTitle')}</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="form-group">
            <label htmlFor="email">{t('auth.email')}</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className={`form-input ${errors.email ? 'error' : ''}`}
              placeholder="admin@naviam.ai"
              {...register('email')}
            />
            {errors.email && <p className="error-text">{errors.email.message}</p>}
          </div>

          <div className="form-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className={`form-input ${errors.password ? 'error' : ''}`}
              placeholder={t('auth.password')}
              {...register('password')}
            />
            {errors.password && <p className="error-text">{errors.password.message}</p>}
          </div>

          {serverError && <p className="error-text" style={{ marginBottom: 16 }}>{serverError}</p>}

          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? <span className="loading" /> : t('auth.loginButton')}
          </button>
        </form>
      </div>
    </div>
  )
}
