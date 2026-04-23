import { useTranslation } from 'react-i18next'
import type { License, LicenseListResponse } from '../types/license'

// Access i18n for locale formatting
import i18n from '@/shared/i18n'

interface Props {
  data: LicenseListResponse
  page: number
  onPageChange: (page: number) => void
  onSelectLicense: (id: string) => void
}

export function LicenseTable({ data, page, onPageChange, onSelectLicense }: Props) {
  const { t } = useTranslation()

  const getStatusBadge = (license: License) => {
    const status = license.status
    const map: Record<string, string> = {
      active: 'status-active',
      expired: 'status-expired',
      revoked: 'status-revoked',
      not_started: 'status-pending',
      used: 'status-used',
    }
    const labelMap: Record<string, string> = {
      active: t('status.active'),
      expired: t('status.expired'),
      revoked: t('status.revoked'),
      not_started: t('status.not_started'),
      used: t('status.used'),
    }
    return <span className={`status-badge ${map[status] || ''}`}>{labelMap[status] || status}</span>
  }

  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    const totalPages = data.pages
    const current = page

    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      pages.push(1)
      if (current > 3) pages.push('...')
      for (let i = Math.max(2, current - 1); i <= Math.min(totalPages - 1, current + 1); i++) {
        pages.push(i)
      }
      if (current < totalPages - 2) pages.push('...')
      pages.push(totalPages)
    }
    return pages
  }

  return (
    <div>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>{t('table.no')}</th>
              <th>{t('table.customer')}</th>
              <th>{t('table.licenseKey')}</th>
              <th>{t('table.status')}</th>
              <th>{t('table.expiresAt')}</th>
              <th>{t('table.action')}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <div className="empty-state">
                    <p>{t('table.empty')}</p>
                  </div>
                </td>
              </tr>
            )}
            {data.items.map((license, index) => (
              <tr key={license.id}>
                <td>{(page - 1) * data.size + index + 1}</td>
                <td>{license.customer_name}</td>
                <td title={license.license_key}>
                  {license.license_key.slice(0, 12)}...
                </td>
                <td>{getStatusBadge(license)}</td>
                <td>{new Date(license.expires_at).toLocaleDateString(i18n.language === 'zh' ? 'zh-CN' : 'en-US')}</td>
                <td>
                  <button className="btn-link" onClick={() => onSelectLicense(license.id)}>
                    {t('common.detail')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.pages > 1 && (
        <div className="pagination">
          <button
            className="page-btn"
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
          >
            ‹
          </button>
          {getPageNumbers().map((p, i) => (
            p === '...' ? (
              <span key={`ellipsis-${i}`} className="page-btn" style={{ cursor: 'default' }}>...</span>
            ) : (
              <button
                key={p}
                className={`page-btn ${p === page ? 'active' : ''}`}
                onClick={() => onPageChange(p as number)}
              >
                {p}
              </button>
            )
          ))}
          <button
            className="page-btn"
            onClick={() => onPageChange(page + 1)}
            disabled={page === data.pages}
          >
            ›
          </button>
          <span style={{ fontSize: 14, color: 'var(--text-secondary)', marginLeft: 12 }}>
            {t('table.total', { count: data.total })}
          </span>
        </div>
      )}
    </div>
  )
}
