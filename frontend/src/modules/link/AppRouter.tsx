import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AuthGuard } from './AuthGuard'
import { MainLayout } from './MainLayout'
import { LoginPage } from '../login/pages/LoginPage'
import { DashboardPage } from '../dashboard/pages/DashboardPage'

export const licenseRouter = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      {
        element: <AuthGuard />,
        children: [
          { path: '', element: <DashboardPage /> },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
