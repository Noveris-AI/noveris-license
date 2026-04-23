import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { useIssueLicense } from '../api/handlers/licenseHandler'

export function LicenseIssueForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation()
  const issueMutation = useIssueLicense()
  const [result, setResult] = useState<{
    license_key: string
    payload: Record<string, unknown>
    signature: string
  } | null>(null)

  const issueSchema = z.object({
    customer_name: z.string().min(1, t('issueForm.customerNameRequired')).max(255),
    max_nodes: z.coerce.number().int().min(1, t('issueForm.maxNodesRequired')).max(100),
    max_gpus: z.coerce.number().int().min(0).max(1000),
    valid_from: z.string().optional(),
    expires_at: z.string().min(1, t('issueForm.expiresAtRequired')),
    cluster_id: z.string().max(64).optional(),
  })

  type IssueForm = z.infer<typeof issueSchema>

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<IssueForm>({
    resolver: zodResolver(issueSchema),
    defaultValues: {
      max_nodes: 10,
      max_gpus: 0,
    },
  })

  const onSubmit = (data: IssueForm) => {
    issueMutation.mutate(
      {
        ...data,
        valid_from: data.valid_from?.trim() || null,
        cluster_id: data.cluster_id?.trim() || null,
      },
      {
        onSuccess: (res: any) => {
          setResult(res)
        },
      },
    )
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const handleDownload = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${result.license_key}.license`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (result) {
    return (
      <div>
        <div className="result-box">
          <h4>{t('issueForm.issueSuccess')}</h4>
          <div className="key-display">
            <span>{result.license_key}</span>
            <button
              className="copy-btn"
              onClick={() => handleCopy(result.license_key)}
            >
              {t('common.copy')}
            </button>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <button className="btn btn-secondary btn-small" onClick={handleDownload}>
            {t('issueForm.downloadFile')}
          </button>
        </div>
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <button className="btn btn-primary btn-small" onClick={onSuccess}>
            {t('issueForm.done')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className="form-group">
        <label>{t('issueForm.customerName')} *</label>
        <input
          className={`form-input ${errors.customer_name ? 'error' : ''}`}
          placeholder={t('issueForm.customerNamePlaceholder')}
          {...register('customer_name')}
        />
        {errors.customer_name && (
          <p className="error-text">{errors.customer_name.message}</p>
        )}
      </div>

      <div className="form-group">
        <label>{t('issueForm.maxNodes')} *</label>
        <input
          type="number"
          className={`form-input ${errors.max_nodes ? 'error' : ''}`}
          {...register('max_nodes')}
        />
        {errors.max_nodes && (
          <p className="error-text">{errors.max_nodes.message}</p>
        )}
      </div>

      <div className="form-group">
        <label>{t('issueForm.maxGpus')}</label>
        <input
          type="number"
          className={`form-input ${errors.max_gpus ? 'error' : ''}`}
          {...register('max_gpus')}
        />
        {errors.max_gpus && (
          <p className="error-text">{errors.max_gpus.message}</p>
        )}
      </div>

      <div className="form-group">
        <label>{t('issueForm.validFrom')}</label>
        <input
          type="datetime-local"
          className="form-input"
          {...register('valid_from')}
        />
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
          {t('issueForm.validFromHint')}
        </p>
      </div>

      <div className="form-group">
        <label>{t('issueForm.expiresAt')} *</label>
        <input
          type="datetime-local"
          className={`form-input ${errors.expires_at ? 'error' : ''}`}
          {...register('expires_at')}
        />
        {errors.expires_at && (
          <p className="error-text">{errors.expires_at.message}</p>
        )}
      </div>

      <div className="form-group">
        <label>{t('issueForm.clusterId')}</label>
        <input
          className="form-input"
          placeholder={t('issueForm.clusterIdPlaceholder')}
          {...register('cluster_id')}
        />
      </div>

      {issueMutation.isError && (
        <p className="error-text" style={{ marginBottom: 16 }}>
          {(issueMutation.error as Error).message}
        </p>
      )}

      <div className="modal-footer" style={{ padding: '16px 0 0' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onSuccess}
        >
          {t('common.cancel')}
        </button>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={issueMutation.isPending}
        >
          {issueMutation.isPending ? <span className="loading" /> : t('issueForm.issueButton')}
        </button>
      </div>
    </form>
  )
}
