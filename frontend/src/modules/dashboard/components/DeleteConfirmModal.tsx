import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useDeleteLicense } from '../api/handlers/licenseHandler'

interface Props {
  licenseId: string
  licenseKey: string
  customerName: string
  onClose: () => void
  onSuccess: () => void
}

export function DeleteConfirmModal({ licenseId, licenseKey, customerName, onClose, onSuccess }: Props) {
  const { t } = useTranslation()
  const [confirm, setConfirm] = useState('')
  const deleteMutation = useDeleteLicense()

  const handleDelete = () => {
    if (confirm !== customerName) return
    deleteMutation.mutate(licenseId, { onSuccess: () => onSuccess() })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{t('licenseDetail.deleteModalTitle')}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 14, color: 'var(--danger)', marginBottom: 16 }}>
            {t('licenseDetail.deleteWarning')}
          </p>
          <div className="info-card" style={{ marginBottom: 16 }}>
            <div className="info-row">
              <span className="info-label">{t('licenseDetail.licenseKey')}</span>
              <span className="info-value">{licenseKey.slice(0, 16)}…</span>
            </div>
            <div className="info-row">
              <span className="info-label">{t('licenseDetail.customerName')}</span>
              <span className="info-value">{customerName}</span>
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="delete-confirm">{t('licenseDetail.deleteConfirmHint')}</label>
            <input
              id="delete-confirm"
              className="form-input"
              placeholder={t('licenseDetail.deleteConfirmPlaceholder')}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            {confirm.length > 0 && confirm !== customerName && (
              <p className="error-text">{t('licenseDetail.deleteConfirmError')}</p>
            )}
          </div>
          {deleteMutation.isError && (
            <p className="error-text" style={{ marginTop: 12 }}>
              {(deleteMutation.error as Error).message}
            </p>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={confirm !== customerName || deleteMutation.isPending}
          >
            {deleteMutation.isPending ? <span className="loading" /> : t('licenseDetail.delete')}
          </button>
        </div>
      </div>
    </div>
  )
}
