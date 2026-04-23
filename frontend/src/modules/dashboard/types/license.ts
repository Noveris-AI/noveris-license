export interface License {
  id: string
  license_key: string
  customer_name: string
  product_code: string
  edition: string
  cluster_id: string | null
  activation_mode: string
  binding_policy: string
  max_activations: number
  current_activations: number
  max_nodes: number
  max_gpus: number
  features: Record<string, unknown>
  valid_from: string | null
  issued_at: string
  expires_at: string
  latest_lease_expires_at: string | null
  used_at: string | null
  used_by_cluster_id: string | null
  revoked_at: string | null
  revoked_reason: string | null
  is_active: boolean
  created_at: string
  grace_period_days: number
  online_lease_ttl_hours: number
  offline_lease_ttl_days: number
  key_id: string
  schema_version: string
  status: 'active' | 'expired' | 'revoked' | 'not_started' | 'used'
}

export interface SignedDocument {
  schema_version: string
  kid: string
  payload: Record<string, unknown>
  signature: string
}

export interface OfflineActivationRequestBundle {
  license_key: string
  fingerprint?: string | null
  cluster_id?: string | null
  machine_name?: string | null
  install_public_key: string
  request_nonce: string
  request_time: string
  client_signature: string
}

export interface OfflineActivationResponseBundle {
  activation_certificate: SignedDocument
  lease: SignedDocument
  license_key: string
  activation_id: string
  issued_at: string
  expires_at: string
  bundle_format_version: string
}

export interface OfflineRenewRequestBundle {
  activation_id: string
  license_key: string
  current_lease_expires_at: string
  request_nonce: string
  request_time: string
  client_signature: string
}

export interface OfflineRenewResponseBundle {
  lease: SignedDocument
  license_key: string
  activation_id: string
  new_expires_at: string
  bundle_format_version: string
}

export interface VerifyLog {
  id: number
  license_key: string
  cluster_id: string | null
  client_ip: string | null
  result: string
  created_at: string
}

export interface LicenseListResponse {
  items: License[]
  total: number
  page: number
  size: number
  pages: number
}

export interface LicenseDetailResponse {
  license: License
  certificate?: SignedDocument
  verify_logs: VerifyLog[]
}

export interface IssueFormData {
  customer_name: string
  max_nodes: number
  max_gpus: number
  valid_from?: string | null
  expires_at: string
  cluster_id?: string | null
}
