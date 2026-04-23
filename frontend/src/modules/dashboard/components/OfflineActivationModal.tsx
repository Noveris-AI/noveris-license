import { useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useProcessOfflineActivation,
  useProcessOfflineRenewal,
} from '../api/handlers/offlineHandler'
import type {
  OfflineActivationRequestBundle,
  OfflineActivationResponseBundle,
  OfflineRenewRequestBundle,
  OfflineRenewResponseBundle,
} from '../types/license'

type OfflineTab = 'activation' | 'renewal'
type OfflineResponse = OfflineActivationResponseBundle | OfflineRenewResponseBundle

interface Props {
  onClose: () => void
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function extractRequestBundle(value: unknown): unknown {
  if (isRecord(value) && isRecord(value.request_bundle)) {
    return value.request_bundle
  }
  return value
}

const ACTIVATION_REQUIRED = ['license_key', 'request_nonce', 'client_signature', 'install_public_key']
const RENEWAL_REQUIRED = ['activation_id', 'license_key', 'request_nonce', 'client_signature']

function validateBundleFields(bundle: unknown, tab: OfflineTab): { key: string; fields?: string } | null {
  if (!isRecord(bundle)) return { key: 'invalidJson' }
  const required = tab === 'activation' ? ACTIVATION_REQUIRED : RENEWAL_REQUIRED
  const missing = required.filter((f) => !(f in bundle))
  if (missing.length > 0) return { key: 'missingFields', fields: missing.join(', ') }
  return null
}

function downloadJson(bundle: OfflineResponse) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `naviam-license-response-${bundle.license_key}-${timestamp}.json`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function OfflineActivationModal({ onClose }: Props) {
  const { t } = useTranslation()
  const activationMutation = useProcessOfflineActivation()
  const renewalMutation = useProcessOfflineRenewal()
  const [activeTab, setActiveTab] = useState<OfflineTab>('activation')
  const [activationBundle, setActivationBundle] = useState<OfflineActivationRequestBundle | null>(null)
  const [renewalBundle, setRenewalBundle] = useState<OfflineRenewRequestBundle | null>(null)
  const [activationResponse, setActivationResponse] = useState<OfflineActivationResponseBundle | null>(null)
  const [renewalResponse, setRenewalResponse] = useState<OfflineRenewResponseBundle | null>(null)
  const [fileName, setFileName] = useState('')
  const [parseError, setParseError] = useState('')

  const currentBundle = activeTab === 'activation' ? activationBundle : renewalBundle
  const currentResponse = activeTab === 'activation' ? activationResponse : renewalResponse
  const currentError = activeTab === 'activation' ? activationMutation.error : renewalMutation.error
  const isPending = activeTab === 'activation' ? activationMutation.isPending : renewalMutation.isPending

  const resetTabState = (tab: OfflineTab) => {
    setActiveTab(tab)
    setFileName('')
    setParseError('')
  }

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setFileName(file.name)
    setParseError('')

    try {
      const parsed = JSON.parse(await file.text())
      const bundle = extractRequestBundle(parsed)
      const fieldError = validateBundleFields(bundle, activeTab)
      if (fieldError) {
        if (fieldError.key === 'invalidJson') {
          throw new Error(t('offlineModal.invalidJson'))
        }
        throw new Error(t('offlineModal.missingFields', { fields: fieldError.fields }))
      }
      if (activeTab === 'activation') {
        setActivationBundle(bundle as unknown as OfflineActivationRequestBundle)
        setActivationResponse(null)
      } else {
        setRenewalBundle(bundle as unknown as OfflineRenewRequestBundle)
        setRenewalResponse(null)
      }
    } catch (error) {
      if (activeTab === 'activation') {
        setActivationBundle(null)
        setActivationResponse(null)
      } else {
        setRenewalBundle(null)
        setRenewalResponse(null)
      }
      setParseError(error instanceof Error ? error.message : t('offlineModal.invalidJson'))
    }
  }

  const handleProcess = () => {
    if (activeTab === 'activation' && activationBundle) {
      activationMutation.mutate(activationBundle, {
        onSuccess: setActivationResponse,
      })
      return
    }
    if (activeTab === 'renewal' && renewalBundle) {
      renewalMutation.mutate(renewalBundle, {
        onSuccess: setRenewalResponse,
      })
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal offline-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>{t('offlineModal.title')}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="modal-tabs">
            <button
              className={`modal-tab ${activeTab === 'activation' ? 'active' : ''}`}
              onClick={() => resetTabState('activation')}
              type="button"
            >
              {t('offlineModal.activationTab')}
            </button>
            <button
              className={`modal-tab ${activeTab === 'renewal' ? 'active' : ''}`}
              onClick={() => resetTabState('renewal')}
              type="button"
            >
              {t('offlineModal.renewalTab')}
            </button>
          </div>

          <p className="offline-modal-hint">{t('offlineModal.hint')}</p>

          <label className="offline-upload">
            <input type="file" accept=".json,application/json" onChange={handleFileChange} />
            <span className="offline-upload-title">{t('offlineModal.uploadTitle')}</span>
            <span className="offline-upload-subtitle">{t('offlineModal.uploadSubtitle')}</span>
          </label>

          {fileName && <p className="offline-file-name">{fileName}</p>}
          {parseError && <p className="error-text">{parseError}</p>}

          {currentBundle && (
            <div className="offline-preview">
              <h4>{t('offlineModal.requestPreview')}</h4>
              <pre className="code-block">{JSON.stringify(currentBundle, null, 2)}</pre>
            </div>
          )}

          {currentError && (
            <p className="error-text" style={{ marginTop: 12 }}>
              {currentError.message}
            </p>
          )}

          {currentResponse && (
            <div className="result-box">
              <h4>{t('offlineModal.responseReady')}</h4>
              <div className="key-display">
                <span>{currentResponse.license_key}</span>
                <button className="copy-btn" onClick={() => downloadJson(currentResponse)}>
                  {t('offlineModal.downloadResponse')}
                </button>
              </div>
              <pre className="code-block offline-response-code">
                {JSON.stringify(currentResponse, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} type="button">
            {t('common.close')}
          </button>
          <button
            className="btn btn-primary"
            disabled={!currentBundle || isPending}
            onClick={handleProcess}
            type="button"
          >
            {isPending ? <span className="loading" /> : t('offlineModal.processButton')}
          </button>
        </div>
      </div>
    </div>
  )
}
