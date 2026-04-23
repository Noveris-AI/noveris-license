import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/shared/api/client'
import type {
  IssueFormData,
  LicenseDetailResponse,
  LicenseListResponse,
} from '../../types/license'

const LICENSES_KEY = 'licenses'

export function useLicenses(page: number, size: number = 20) {
  return useQuery<LicenseListResponse>({
    queryKey: [LICENSES_KEY, page, size],
    queryFn: () => api.get(`/licenses?page=${page}&size=${size}`),
  })
}

export function useLicenseDetail(licenseId: string | null) {
  return useQuery<LicenseDetailResponse>({
    queryKey: [LICENSES_KEY, 'detail', licenseId],
    queryFn: () => api.get(`/licenses/${licenseId}`),
    enabled: !!licenseId,
  })
}

export function useIssueLicense() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IssueFormData) =>
      api.post('/license/issue', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LICENSES_KEY] })
    },
  })
}

export function useRevokeLicense() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.post(`/licenses/${id}/revoke`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LICENSES_KEY] })
    },
  })
}

export function useDeleteLicense() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/licenses/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LICENSES_KEY] })
    },
  })
}
