import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLicenseDetail } from '../api/handlers/licenseHandler'
import { RevokeConfirmModal } from './RevokeConfirmModal'
import { DeleteConfirmModal } from './DeleteConfirmModal'
import type { License } from '../types/license'

interface Props {
  licenseId: string | null
  onClose: () => void
  onRevoked: () => void
  onDeleted: () => void
}

export function LicenseDetailDrawer({ licenseId, onClose, onRevoked, onDeleted }: Props) {
  const { t, i18n } = useTranslation()
  const { data, isLoading } = useLicenseDetail(licenseId)
  const [showRevokeModal, setShowRevokeModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const handleDownload = (license: License) => {
    const exportData = data?.certificate ?? {
      license_key: license.license_key,
      payload: {
        license_key: license.license_key,
        customer_name: license.customer_name,
        cluster_id: license.cluster_id,
        max_nodes: license.max_nodes,
        max_gpus: license.max_gpus,
        expires_at: license.expires_at,
        issued_at: license.issued_at,
      },
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${license.customer_name}_${license.license_key.slice(0, 12)}.license`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const getStatusBadge = (status: string) => {
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

  const fmt = (d: string) => new Date(d).toLocaleString(i18n.language === 'zh' ? 'zh-CN' : 'en-US')

  if (!licenseId) return null

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-header">
          <h3>{t('licenseDetail.title')}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="drawer-body">
          {isLoading && (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <div className="loading" style={{ width: 32, height: 32, borderWidth: 3, borderColor: 'rgba(0,0,0,0.1)', borderTopColor: '#2fb67a' }} />
            </div>
          )}

          {data && (
            <>
              <div style={{ marginBottom: 20 }}>
                {getStatusBadge(data.license.status)}
              </div>

              <div className="info-card">
                <h4>{t('licenseDetail.basicInfo')}</h4>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.licenseKey')}</span>
                  <span className="info-value">
                    {data.license.license_key.slice(0, 16)}...
                    <button className="copy-btn" onClick={() => handleCopy(data.license.license_key)}>{t('common.copy')}</button>
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.customerName')}</span>
                  <span className="info-value">{data.license.customer_name}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.clusterId')}</span>
                  <span className="info-value">{data.license.cluster_id || '-'}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.maxNodes')}</span>
                  <span className="info-value">{data.license.max_nodes}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.maxGpus')}</span>
                  <span className="info-value">{data.license.max_gpus}</span>
                </div>
                {data.license.valid_from && (
                  <div className="info-row">
                    <span className="info-label">{t('licenseDetail.validFrom')}</span>
                    <span className="info-value">{fmt(data.license.valid_from)}</span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.issuedAt')}</span>
                  <span className="info-value">{fmt(data.license.issued_at)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('licenseDetail.expiresAt')}</span>
                  <span className="info-value">{fmt(data.license.expires_at)}</span>
                </div>
                {data.license.used_at && (
                  <div className="info-row">
                    <span className="info-label">{t('licenseDetail.usedAt')}</span>
                    <span className="info-value" style={{ color: 'var(--text-info)' }}>
                      {fmt(data.license.used_at)}
                    </span>
                  </div>
                )}
                {data.license.used_by_cluster_id && (
                  <div className="info-row">
                    <span className="info-label">{t('licenseDetail.usedByCluster')}</span>
                    <span className="info-value" style={{ color: 'var(--text-info)' }}>
                      {data.license.used_by_cluster_id}
                    </span>
                  </div>
                )}
                {data.license.revoked_at && (
                  <div className="info-row">
                    <span className="info-label">{t('licenseDetail.revokedAt')}</span>
                    <span className="info-value" style={{ color: 'var(--danger)' }}>
                      {fmt(data.license.revoked_at)}
                    </span>
                  </div>
                )}
                {data.license.revoked_reason && (
                  <div className="info-row">
                    <span className="info-label">{t('licenseDetail.revokedReason')}</span>
                    <span className="info-value" style={{ color: 'var(--danger)' }}>
                      {data.license.revoked_reason}
                    </span>
                  </div>
                )}
                <div className="info-row" style={{ borderTop: '2px solid var(--border-light)', marginTop: 8, paddingTop: 12 }}>
                  <span className="info-label">{t('licenseDetail.usageType')}</span>
                  <span className="info-value" style={{ fontWeight: 600, color: 'var(--text-warning)' }}>
                    {`${data.license.activation_mode.toUpperCase()} / ${data.license.current_activations}/${data.license.max_activations}`}
                  </span>
                </div>
              </div>

              <div className="info-card">
                <h4 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {t('licenseDetail.signatureData')}
                  <button className="copy-btn" onClick={() => handleDownload(data.license)}>{t('common.download')}</button>
                </h4>
                <pre className="code-block">
                  {JSON.stringify(
                    data.certificate ?? {
                      license_key: data.license.license_key,
                      customer_name: data.license.customer_name,
                      max_nodes: data.license.max_nodes,
                      max_gpus: data.license.max_gpus,
                      expires_at: data.license.expires_at,
                      issued_at: data.license.issued_at,
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>

              {data.verify_logs.length > 0 && (
                <div className="info-card">
                  <h4>{t('licenseDetail.verifyHistory', { count: data.verify_logs.length })}</h4>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>{t('licenseDetail.time')}</th>
                        <th>{t('licenseDetail.result')}</th>
                        <th>{t('licenseDetail.cluster')}</th>
                        <th>{t('licenseDetail.ip')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.verify_logs.map((log: { id: number; created_at: string; result: string; cluster_id: string | null; client_ip: string | null }) => (
                        <tr key={log.id}>
                          <td>{fmt(log.created_at)}</td>
                          <td>
                            <span className={`status-badge ${
                              log.result === 'success' || log.result.startsWith('activated') || log.result.startsWith('renewal')
                                ? 'status-active'
                                : log.result === 'expired' || log.result.includes('deadline')
                                ? 'status-expired'
                                : 'status-revoked'
                            }`}>
                              {t(`verifyResult.${log.result}`, {
                                defaultValue: log.result.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
                              })}
                            </span>
                          </td>
                          <td>{log.cluster_id || '-'}</td>
                          <td>{log.client_ip || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        <div className="drawer-footer" style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {data && (
            <button
              className="btn btn-secondary"
              style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
              onClick={() => setShowDeleteModal(true)}
            >
              {t('licenseDetail.delete')}
            </button>
          )}
          {data && data.license.status !== 'revoked' && (
            <button className="btn btn-danger" onClick={() => setShowRevokeModal(true)}>
              {t('licenseDetail.revoke')}
            </button>
          )}
        </div>
      </div>

      {showRevokeModal && data && (
        <RevokeConfirmModal
          licenseId={data.license.id}
          licenseKey={data.license.license_key}
          customerName={data.license.customer_name}
          onClose={() => setShowRevokeModal(false)}
          onSuccess={() => {
            setShowRevokeModal(false)
            onRevoked()
          }}
        />
      )}

      {showDeleteModal && data && (
        <DeleteConfirmModal
          licenseId={data.license.id}
          licenseKey={data.license.license_key}
          customerName={data.license.customer_name}
          onClose={() => setShowDeleteModal(false)}
          onSuccess={() => {
            setShowDeleteModal(false)
            onDeleted()
          }}
        />
      )}
    </>
  )
}
