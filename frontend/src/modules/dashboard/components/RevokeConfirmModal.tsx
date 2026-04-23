import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRevokeLicense } from '../api/handlers/licenseHandler'

interface Props {
  licenseId: string
  licenseKey: string
  customerName: string
  onClose: () => void
  onSuccess: () => void
}

export function RevokeConfirmModal({
  licenseId,
  licenseKey,
  customerName,
  onClose,
  onSuccess,
}: Props) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const revokeMutation = useRevokeLicense()

  const handleRevoke = () => {
    if (reason.trim().length < 5) return
    revokeMutation.mutate(
      { id: licenseId, reason: reason.trim() },
      {
        onSuccess: () => {
          onSuccess()
        },
      }
    )
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{t('licenseDetail.revokeModalTitle')}</h3>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>
            {t('licenseDetail.revokeWarning')}
          </p>

          <div className="info-card" style={{ marginBottom: 16 }}>
            <div className="info-row">
              <span className="info-label">{t('licenseDetail.licenseKey')}</span>
              <span className="info-value">{licenseKey}</span>
            </div>
            <div className="info-row">
              <span className="info-label">{t('licenseDetail.customerName')}</span>
              <span className="info-value">{customerName}</span>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="revoke-reason">{t('licenseDetail.revokeReason')} *</label>
            <input
              id="revoke-reason"
              className="form-input"
              placeholder={t('licenseDetail.revokeReasonPlaceholder')}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            {reason.trim().length > 0 && reason.trim().length < 5 && (
              <p className="error-text">{t('licenseDetail.revokeReasonMinLength')}</p>
            )}
          </div>

          {revokeMutation.isError && (
            <p className="error-text" style={{ marginTop: 12 }}>
              {(revokeMutation.error as Error).message}
            </p>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            className="btn btn-danger"
            onClick={handleRevoke}
            disabled={reason.trim().length < 5 || revokeMutation.isPending}
          >
            {revokeMutation.isPending ? <span className="loading" /> : t('common.confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
