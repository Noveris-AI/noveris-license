import { useMutation } from '@tanstack/react-query'
import { api } from '@/shared/api/client'
import type {
  OfflineActivationRequestBundle,
  OfflineActivationResponseBundle,
  OfflineRenewRequestBundle,
  OfflineRenewResponseBundle,
} from '../../types/license'

export function useProcessOfflineActivation() {
  return useMutation<OfflineActivationResponseBundle, Error, OfflineActivationRequestBundle>({
    mutationFn: (requestBundle) =>
      api.post('/licenses/offline/process-activation', { request_bundle: requestBundle }),
  })
}

export function useProcessOfflineRenewal() {
  return useMutation<OfflineRenewResponseBundle, Error, OfflineRenewRequestBundle>({
    mutationFn: (requestBundle) =>
      api.post('/licenses/offline/process-renewal', { request_bundle: requestBundle }),
  })
}
