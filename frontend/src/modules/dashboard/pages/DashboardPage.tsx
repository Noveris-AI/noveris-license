import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import { useThemeStore } from '@/stores/themeStore'
import { useLangStore } from '@/stores/langStore'
import { useLicenses } from '../api/handlers/licenseHandler'
import { LicenseTable } from '../components/LicenseTable'
import { LicenseIssueForm } from '../components/LicenseIssueForm'
import { LicenseDetailDrawer } from '../components/LicenseDetailDrawer'
import { OfflineActivationModal } from '../components/OfflineActivationModal'
import { api } from '@/shared/api/client'

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

function MonitorIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const operator = useAuthStore((s) => s.operator)
  const logout = useAuthStore((s) => s.logout)
  const theme = useThemeStore((s) => s.theme)
  const resolvedTheme = useThemeStore((s) => s.resolvedTheme)
  const setTheme = useThemeStore((s) => s.setTheme)
  const langMode = useLangStore((s) => s.langMode)
  const setLangMode = useLangStore((s) => s.setLangMode)
  const [page, setPage] = useState(1)
  const [showIssueModal, setShowIssueModal] = useState(false)
  const [showOfflineModal, setShowOfflineModal] = useState(false)
  const [selectedLicenseId, setSelectedLicenseId] = useState<string | null>(null)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showThemeMenu, setShowThemeMenu] = useState(false)
  const [showLangMenu, setShowLangMenu] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const themeMenuRef = useRef<HTMLDivElement>(null)
  const langMenuRef = useRef<HTMLDivElement>(null)

  const { data, isLoading, error } = useLicenses(page)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false)
      }
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target as Node)) {
        setShowThemeMenu(false)
      }
      if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
        setShowLangMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // ignore
    }
    logout()
    navigate('/login', { replace: true })
  }

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const ThemeIcon = resolvedTheme === 'dark' ? MoonIcon : SunIcon

  const langLabel = langMode === 'system' ? <GlobeIcon /> : langMode === 'zh' ? '中' : 'EN'

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <span className="header-logo">{t('common.naviam')}</span>
          <span className="header-title">{t('dashboard.title')}</span>
        </div>
        <div className="header-right">
          <div className="header-actions">
            {/* Language dropdown */}
            <div className="user-menu" ref={langMenuRef}>
              <button className="icon-btn" onClick={() => setShowLangMenu(!showLangMenu)} title="Language">
                {langLabel}
              </button>
              {showLangMenu && (
                <div className="dropdown-menu" style={{ minWidth: 148 }}>
                  <div className={`dropdown-item ${langMode === 'system' ? 'active' : ''}`} onClick={() => { setLangMode('system'); setShowLangMenu(false) }}>
                    <GlobeIcon /> {t('common.lang_system')}
                  </div>
                  <div className={`dropdown-item ${langMode === 'zh' ? 'active' : ''}`} onClick={() => { setLangMode('zh'); setShowLangMenu(false) }}>
                    中 {t('common.lang_zh')}
                  </div>
                  <div className={`dropdown-item ${langMode === 'en' ? 'active' : ''}`} onClick={() => { setLangMode('en'); setShowLangMenu(false) }}>
                    EN {t('common.lang_en')}
                  </div>
                </div>
              )}
            </div>

            {/* Theme dropdown */}
            <div className="user-menu" ref={themeMenuRef}>
              <button className="icon-btn" onClick={() => setShowThemeMenu(!showThemeMenu)} title={theme}>
                <ThemeIcon />
              </button>
              {showThemeMenu && (
                <div className="dropdown-menu" style={{ minWidth: 148 }}>
                  <div className={`dropdown-item ${theme === 'light' ? 'active' : ''}`} onClick={() => { setTheme('light'); setShowThemeMenu(false) }}>
                    <SunIcon /> {t('common.theme_light')}
                  </div>
                  <div className={`dropdown-item ${theme === 'dark' ? 'active' : ''}`} onClick={() => { setTheme('dark'); setShowThemeMenu(false) }}>
                    <MoonIcon /> {t('common.theme_dark')}
                  </div>
                  <div className={`dropdown-item ${theme === 'system' ? 'active' : ''}`} onClick={() => { setTheme('system'); setShowThemeMenu(false) }}>
                    <MonitorIcon /> {t('common.theme_system')}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="user-menu" ref={userMenuRef}>
            <div className="user-trigger" onClick={() => setShowUserMenu(!showUserMenu)}>
              <span>{operator?.username || operator?.email}</span>
              <span>▼</span>
            </div>
            {showUserMenu && (
              <div className="dropdown-menu">
                <div className="dropdown-item" style={{ color: 'var(--text-secondary)', cursor: 'default' }}>
                  {operator?.email}
                </div>
                <div className="dropdown-divider" />
                <div className="dropdown-item logout-btn" onClick={handleLogout}>
                  {t('auth.logout')}
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="dashboard">
        <div className="action-bar">
          <h2>{t('dashboard.pageTitle')}</h2>
          <div className="action-bar-actions">
            <button className="btn btn-secondary btn-small" onClick={() => setShowOfflineModal(true)}>
              {t('dashboard.offlineProcess')}
            </button>
            <button className="btn btn-primary btn-small" onClick={() => setShowIssueModal(true)}>
              + {t('dashboard.issueNew')}
            </button>
          </div>
        </div>

        {isLoading && (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <div className="loading" style={{ width: 40, height: 40, borderWidth: 3, borderColor: 'rgba(0,0,0,0.1)', borderTopColor: '#2fb67a' }} />
          </div>
        )}

        {error && (
          <div className="empty-state">
            <p style={{ color: 'var(--danger)' }}>{t('dashboard.loadError')}: {(error as Error).message}</p>
          </div>
        )}

        {data && (
          <LicenseTable
            data={data}
            page={page}
            onPageChange={setPage}
            onSelectLicense={setSelectedLicenseId}
          />
        )}
      </main>

      {showIssueModal && (
        <div className="modal-overlay" onClick={() => setShowIssueModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{t('dashboard.issueModalTitle')}</h3>
              <button className="modal-close" onClick={() => setShowIssueModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <LicenseIssueForm
                onSuccess={() => {
                  setShowIssueModal(false)
                  showToast(t('dashboard.issueSuccess'))
                }}
              />
            </div>
          </div>
        </div>
      )}

      {showOfflineModal && (
        <OfflineActivationModal onClose={() => setShowOfflineModal(false)} />
      )}

      <LicenseDetailDrawer
        licenseId={selectedLicenseId}
        onClose={() => setSelectedLicenseId(null)}
        onRevoked={() => {
          setSelectedLicenseId(null)
          showToast(t('dashboard.revokeSuccess'))
        }}
        onDeleted={() => {
          setSelectedLicenseId(null)
          showToast(t('dashboard.deleteSuccess'))
        }}
      />

      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>{toast.message}</div>
        </div>
      )}
    </div>
  )
}
