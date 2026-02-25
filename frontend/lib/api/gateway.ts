/**
 * API Gateway client for the existing Express routes:
 *   /api/nlq/connect-cluster
 *   /api/nlq/get-collections
 *   /api/nlq/run-nlp
 *   /api/nlq/diagnose
 *   /api/nlq/clear-cache
 */

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api/nlq"
const API_BASE = RAW_API_BASE.endsWith("/api/nlq")
  ? RAW_API_BASE
  : `${RAW_API_BASE.replace(/\/$/, "")}/api/nlq`

interface ConnectClusterResponse {
  databases: string[]
  total_databases: number
  message?: string
}

interface CollectionInfo {
  name: string
  document_count: number
}

interface GetCollectionsResponse {
  collections: CollectionInfo[]
}

export interface RunNLPResponse {
  interpretation?: string
  data?: Record<string, unknown>[]
  result?: number
  result_count?: number
  total_results?: number
  page?: number
  page_size?: number
  warning?: string
  value_hint?: string
  indexes?: Array<{ name: string; unique?: boolean }>
  interpreted_ir?: {
    operation?: string
    conditions?: Array<{ field?: string; operator?: string; value?: unknown }>
  }
}

export interface DiagnoseStep0 {
  total_documents?: number
  sample_fields?: Record<string, string> | null
  error?: string
}

export interface DiagnoseStep1 {
  status?: string
  allowed_fields?: string[]
  numeric_fields?: string[]
  field_types?: Record<string, string>
  field_count?: number
  error?: string
}

export interface DiagnoseStep2 {
  status?: string
  parser?: string
  raw_ir?: {
    operation?: string
    conditions?: Array<{ field?: string; operator?: string; value?: unknown }>
    aggregation?: { type?: string; field?: string } | null
    sort?: { field?: string; direction?: string } | null
    limit?: number | null
    projection?: string[] | null
  }
  error?: string
}

export interface DiagnoseStep3Entry {
  raw_field?: string
  resolved_field?: string | null
  context?: string
  matched?: boolean
}

export interface DiagnoseStep4 {
  status?: string
  validated_ir?: Record<string, unknown>
  error?: string
}

export interface DiagnoseStep5 {
  status?: string
  type?: string
  filter?: string
  sort?: string
  limit?: number | null
  pipeline?: string | null
  error?: string
}

export interface DiagnoseStep6 {
  status?: string
  total_count?: number
  returned?: number
  sample_docs?: Record<string, unknown>[]
  error?: string
}

export interface DiagnoseStep7 {
  indexes?: string[]
  indexed_fields?: string[]
  queried_fields?: string[]
  unindexed_fields?: string[]
  error?: string
}

export interface DiagnoseSteps {
  "0_raw_sample"?: DiagnoseStep0
  "1_schema"?: DiagnoseStep1
  "2_parse"?: DiagnoseStep2
  "3_resolve"?: DiagnoseStep3Entry[]
  "4_validate"?: DiagnoseStep4
  "5_compile"?: DiagnoseStep5
  "6_execute_preview"?: DiagnoseStep6
  "7_index_info"?: DiagnoseStep7
}

export interface DiagnoseResponse {
  query?: string
  steps?: DiagnoseSteps
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object") {
    const maybeDetail = (data as { detail?: unknown }).detail
    const maybeError = (data as { error?: unknown }).error
    if (typeof maybeDetail === "string") return maybeDetail
    if (typeof maybeError === "string") return maybeError
  }
  return fallback
}

async function postJSON<T>(path: string, body: Record<string, unknown>, fallbackError: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })

  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new Error(extractErrorMessage(data, fallbackError))
  }

  return data as T
}

export async function connectToMongo(mongoUri: string): Promise<ConnectClusterResponse> {
  return postJSON<ConnectClusterResponse>(
    "/connect-cluster",
    { mongo_uri: mongoUri },
    "Failed to connect to MongoDB cluster"
  )
}

export async function fetchDatabases(mongoUri: string): Promise<string[]> {
  const result = await connectToMongo(mongoUri)
  return result.databases || []
}

export async function fetchCollections(mongoUri: string, db: string): Promise<string[]> {
  const result = await postJSON<GetCollectionsResponse>(
    "/get-collections",
    { mongo_uri: mongoUri, database_name: db },
    "Failed to fetch collections"
  )

  return (result.collections || []).map((col) => col.name)
}

export async function sendQuery(params: {
  mongoUri: string
  db: string
  collection: string
  query: string
  page?: number
  pageSize?: number
  history?: Array<{ role: "user" | "assistant"; content: string }>
  userEmail?: string
}): Promise<RunNLPResponse> {
  const { mongoUri, db, collection, query, page = 1, pageSize = 20, history, userEmail } = params

  const body: Record<string, unknown> = {
    mongo_uri: mongoUri,
    database_name: db,
    collection_name: collection,
    query,
    page,
    page_size: pageSize,
  }
  if (history && history.length > 0) {
    body.history = history
  }
  if (userEmail) body.user_email = userEmail

  return postJSON<RunNLPResponse>("/run-nlp", body, "Query failed")
}

export async function diagnoseQuery(params: {
  mongoUri: string
  db: string
  collection: string
  query: string
  history?: Array<{ role: "user" | "assistant"; content: string }>
  userEmail?: string
}): Promise<DiagnoseResponse> {
  const { mongoUri, db, collection, query, history, userEmail } = params

  const body: Record<string, unknown> = {
    mongo_uri: mongoUri,
    database_name: db,
    collection_name: collection,
    query,
  }
  if (history && history.length > 0) {
    body.history = history
  }
  if (userEmail) body.user_email = userEmail

  return postJSON<DiagnoseResponse>("/diagnose", body, "Diagnosis failed")
}

export async function clearCache(): Promise<{ status?: string; message?: string }> {
  return postJSON<{ status?: string; message?: string }>(
    "/clear-cache",
    {},
    "Failed to clear cache"
  )
}

// ====================== Mongo Edit — CRUD Mutations ======================

export interface SchemaResponse {
  fields: string[]
  numeric_fields: string[]
  field_types: Record<string, string>
  total_fields: number
}

export async function fetchSchema(params: {
  mongoUri: string
  db: string
  collection: string
}): Promise<SchemaResponse> {
  return postJSON<SchemaResponse>(
    "/get-schema",
    {
      mongo_uri: params.mongoUri,
      database_name: params.db,
      collection_name: params.collection,
    },
    "Failed to fetch schema"
  )
}

export interface MutationEstimateResponse {
  count: number | null
  sample_affected: Record<string, unknown>[]
  error?: string
}

export async function estimateMutation(params: {
  mongoUri: string
  db: string
  collection: string
  filter: Record<string, unknown>
}): Promise<MutationEstimateResponse> {
  return postJSON<MutationEstimateResponse>(
    "/mutation-estimate",
    {
      mongo_uri: params.mongoUri,
      database_name: params.db,
      collection_name: params.collection,
      filter: params.filter,
    },
    "Mutation estimate failed"
  )
}

export interface MutationPlan {
  operation: "insert" | "update" | "delete"
  description: string
  filter?: Record<string, unknown> | null
  update?: Record<string, unknown> | null
  document?: Record<string, unknown> | null
  documents?: Record<string, unknown>[] | null
  multi?: boolean
  estimated_affected?: number | null
  sample_affected?: Record<string, unknown>[]
}

export interface MutationPreviewResponse {
  status: "preview"
  query: string
  mutation: MutationPlan
}

export interface MutationCommitResponse {
  operation: string
  status: string
  inserted_count?: number
  inserted_id?: string
  inserted_ids?: string[]
  matched_count?: number
  modified_count?: number
  deleted_count?: number
}

export async function previewMutation(params: {
  mongoUri: string
  db: string
  collection: string
  query: string
  history?: Array<{ role: "user" | "assistant"; content: string }>
}): Promise<MutationPreviewResponse> {
  const { mongoUri, db, collection, query, history } = params
  const body: Record<string, unknown> = {
    mongo_uri: mongoUri,
    database_name: db,
    collection_name: collection,
    query,
  }
  if (history && history.length > 0) body.history = history

  return postJSON<MutationPreviewResponse>(
    "/mutation-preview",
    body,
    "Mutation preview failed"
  )
}

export async function commitMutation(params: {
  mongoUri: string
  db: string
  collection: string
  mutation: MutationPlan
  userEmail?: string
}): Promise<MutationCommitResponse> {
  const body: Record<string, unknown> = {
    mongo_uri: params.mongoUri,
    database_name: params.db,
    collection_name: params.collection,
    mutation: params.mutation,
  }
  if (params.userEmail) body.user_email = params.userEmail
  return postJSON<MutationCommitResponse>(
    "/mutation-commit",
    body,
    "Mutation commit failed"
  )
}

// ====================== Analytics / Dashboard ======================

export interface CommitTimelineEntry {
  activity_type: string
  collection_name: string
  user_email: string
  query: string
  timestamp: string
  details: Record<string, unknown>
}

export interface CommitTimelineResponse {
  timeline: CommitTimelineEntry[]
  count: number
}

export interface ActivityStatsResponse {
  totals: Record<string, number>
  timeline: Array<{
    bucket: string
    query: number
    diagnose: number
    commit: number
  }>
  severity: Record<string, number>
  top_collections: Array<{ name: string; count: number }>
  granularity: string
}

export interface DiagnosisMonthlyEntry {
  bucket: string
  total: number
  ok: number
  error: number
  warning: number
  score: number
}

export interface DiagnosisMonthlyResponse {
  monthly: DiagnosisMonthlyEntry[]
}

/** Shared analytics filter params */
export interface AnalyticsFilterParams {
  mongoUri: string
  db: string
  userEmail?: string
  year?: number
  month?: number
  day?: number
  days?: number
  hours?: number
  minutes?: number
  granularity?: "auto" | "minute" | "hour" | "day" | "month"
}

function _buildAnalyticsBody(params: AnalyticsFilterParams): Record<string, unknown> {
  const body: Record<string, unknown> = {
    mongo_uri: params.mongoUri,
    database_name: params.db,
  }
  if (params.userEmail) body.user_email = params.userEmail
  if (params.year != null) body.year = params.year
  if (params.month != null) body.month = params.month
  if (params.day != null) body.day = params.day
  if (params.days != null) body.days = params.days
  if (params.hours != null) body.hours = params.hours
  if (params.minutes != null) body.minutes = params.minutes
  if (params.granularity) body.granularity = params.granularity
  return body
}

export async function fetchCommitTimeline(
  params: AnalyticsFilterParams,
): Promise<CommitTimelineResponse> {
  return postJSON<CommitTimelineResponse>(
    "/analytics/commit-timeline",
    _buildAnalyticsBody(params),
    "Failed to load commit timeline"
  )
}

export async function fetchActivityStats(
  params: AnalyticsFilterParams,
): Promise<ActivityStatsResponse> {
  return postJSON<ActivityStatsResponse>(
    "/analytics/stats",
    _buildAnalyticsBody(params),
    "Failed to load activity stats"
  )
}

export async function fetchDiagnosisMonthly(
  params: AnalyticsFilterParams,
): Promise<DiagnosisMonthlyResponse> {
  return postJSON<DiagnosisMonthlyResponse>(
    "/analytics/diagnosis-monthly",
    _buildAnalyticsBody(params),
    "Failed to load diagnosis data"
  )
}
