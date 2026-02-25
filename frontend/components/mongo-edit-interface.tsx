"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import {
    Send,
    Loader2,
    Pencil,
    Plus,
    RefreshCw,
    Trash2,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    ChevronDown,
    ChevronUp,
    FileJson,
    Table2,
    MessageSquareText,
    Eye,
    PlusCircle,
    GitCommitHorizontal,
    X,
} from "lucide-react"
import { useAppContext } from "@/context/app-context"
import { useAuth } from "@/context/auth-context"
import {
    fetchSchema,
    previewMutation,
    commitMutation,
    estimateMutation,
    type MutationPlan,
    type MutationCommitResponse,
    type SchemaResponse,
} from "@/lib/api/gateway"

// ===================== Shared types =====================

type EditMode = "manual" | "query"

/** Workflow stages: idle → preview → added → committing → committed */
type WorkflowStage =
    | "loading"
    | "preview"
    | "added"
    | "committing"
    | "committed"
    | "error"

interface MutationEntry {
    id: string
    source: EditMode
    query: string
    timestamp: Date
    mutation: MutationPlan | null
    stage: WorkflowStage
    commitResult?: MutationCommitResponse
    error?: string
}

// ===================== Badge helpers =====================

function opColor(op: string) {
    switch (op) {
        case "insert":
            return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
        case "update":
            return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30"
        case "delete":
            return "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30"
        default:
            return "bg-muted text-muted-foreground border-border"
    }
}

function opIcon(op: string) {
    switch (op) {
        case "insert":
            return <Plus className="h-3.5 w-3.5" />
        case "update":
            return <RefreshCw className="h-3.5 w-3.5" />
        case "delete":
            return <Trash2 className="h-3.5 w-3.5" />
        default:
            return <Pencil className="h-3.5 w-3.5" />
    }
}

// ===================== Main Component =====================

export function MongoEditInterface({
    db,
    collection,
}: {
    db: string
    collection: string
}) {
    const { connectionString } = useAppContext()
    const { user } = useAuth()

    // ---- Mode toggle ----
    const [mode, setMode] = useState<EditMode | null>(null)

    // ---- Schema (used by manual mode) ----
    const [schema, setSchema] = useState<SchemaResponse | null>(null)
    const [schemaLoading, setSchemaLoading] = useState(false)
    const [schemaError, setSchemaError] = useState("")

    // ---- Entries list (both modes push here) ----
    const [entries, setEntries] = useState<MutationEntry[]>([])
    const [expandedJson, setExpandedJson] = useState<Set<string>>(new Set())
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [entries])

    // ---- Load schema when mode becomes manual ----
    useEffect(() => {
        if (mode === "manual" && !schema && !schemaLoading && connectionString) {
            setSchemaLoading(true)
            setSchemaError("")
            fetchSchema({ mongoUri: connectionString, db, collection })
                .then((s) => setSchema(s))
                .catch((e) =>
                    setSchemaError(e instanceof Error ? e.message : "Failed to load schema"),
                )
                .finally(() => setSchemaLoading(false))
        }
    }, [mode, schema, schemaLoading, connectionString, db, collection])

    // ---- Connection guard ----
    if (!connectionString) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
                    <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-destructive" />
                    <p className="text-sm font-medium text-destructive">
                        Not connected to MongoDB
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                        Go to the Dashboard and connect to your cluster first.
                    </p>
                </div>
            </div>
        )
    }

    // ---- Workflow actions ----

    const addEntry = (entry: MutationEntry) =>
        setEntries((prev) => [...prev, entry])

    const updateEntry = (id: string, patch: Partial<MutationEntry>) =>
        setEntries((prev) =>
            prev.map((e) => (e.id === id ? { ...e, ...patch } : e)),
        )

    /** Preview → Add */
    const handleAdd = (id: string) => updateEntry(id, { stage: "added" })

    /** Add → Commit */
    const handleCommit = async (id: string) => {
        const entry = entries.find((e) => e.id === id)
        if (!entry?.mutation) return

        updateEntry(id, { stage: "committing" })
        try {
            const result = await commitMutation({
                mongoUri: connectionString,
                db,
                collection,
                mutation: entry.mutation,
                userEmail: user?.email,
            })
            updateEntry(id, { stage: "committed", commitResult: result })
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Commit failed"
            updateEntry(id, { stage: "error", error: msg })
        }
    }

    /** Cancel at any stage */
    const handleCancel = (id: string) =>
        setEntries((prev) => prev.filter((e) => e.id !== id))

    const toggleJson = (id: string) =>
        setExpandedJson((prev) => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })

    // ---- Mode selection screen ----
    if (mode === null) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="w-full max-w-xl px-6">
                    <div className="mb-8 text-center">
                        <Pencil className="mx-auto mb-4 h-10 w-10 text-primary/50" />
                        <h2 className="text-xl font-semibold text-foreground">
                            Mongo Edit
                        </h2>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Choose how you want to modify{" "}
                            <span className="font-mono text-foreground">{collection}</span>
                        </p>
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        {/* Manual option */}
                        <button
                            onClick={() => setMode("manual")}
                            className="group rounded-xl border-2 border-border bg-card p-6 text-left transition-all hover:border-primary/50 hover:shadow-md"
                        >
                            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                                <Table2 className="h-5 w-5 text-blue-500" />
                            </div>
                            <h3 className="mb-1 text-sm font-semibold text-foreground">
                                Manual Change
                            </h3>
                            <p className="text-xs leading-relaxed text-muted-foreground">
                                Fill in a table with your collection&apos;s columns. Manually
                                enter field values, then preview and commit.
                            </p>
                        </button>

                        {/* Query option */}
                        <button
                            onClick={() => setMode("query")}
                            className="group rounded-xl border-2 border-border bg-card p-6 text-left transition-all hover:border-primary/50 hover:shadow-md"
                        >
                            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
                                <MessageSquareText className="h-5 w-5 text-amber-500" />
                            </div>
                            <h3 className="mb-1 text-sm font-semibold text-foreground">
                                Query Dynamic Change
                            </h3>
                            <p className="text-xs leading-relaxed text-muted-foreground">
                                Describe changes in natural language. AI will process your query
                                and build the mutation automatically.
                            </p>
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // ---- Render active mode ----
    return (
        <div className="flex h-full flex-col">
            {/* Mode tabs + back */}
            <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-6 py-2">
                <button
                    onClick={() => setMode(null)}
                    className="mr-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                    &larr; Change Mode
                </button>
                <div className="h-4 w-px bg-border" />
                <button
                    onClick={() => setMode("manual")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${mode === "manual"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                        }`}
                >
                    <Table2 className="h-3.5 w-3.5" />
                    Manual
                </button>
                <button
                    onClick={() => setMode("query")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${mode === "query"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                        }`}
                >
                    <MessageSquareText className="h-3.5 w-3.5" />
                    Query
                </button>
            </div>

            {/* Input area (mode-specific) */}
            {mode === "manual" && (
                <ManualInputPanel
                    db={db}
                    collection={collection}
                    connectionString={connectionString}
                    schema={schema}
                    schemaLoading={schemaLoading}
                    schemaError={schemaError}
                    onEntry={addEntry}
                />
            )}
            {mode === "query" && (
                <QueryInputPanel
                    db={db}
                    collection={collection}
                    connectionString={connectionString}
                    entries={entries}
                    onEntry={addEntry}
                    onUpdateEntry={updateEntry}
                />
            )}

            {/* Entries list */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
                {entries.length === 0 ? (
                    <div className="flex h-full items-center justify-center">
                        <p className="text-sm text-muted-foreground">
                            {mode === "manual"
                                ? "Fill in the table above and click Execute & Preview to generate a mutation."
                                : "Type a query above to start editing your data."}
                        </p>
                    </div>
                ) : (
                    <div className="mx-auto flex max-w-4xl flex-col gap-4">
                        {entries.map((entry) => (
                            <MutationCard
                                key={entry.id}
                                entry={entry}
                                isJsonExpanded={expandedJson.has(entry.id)}
                                onToggleJson={() => toggleJson(entry.id)}
                                onAdd={() => handleAdd(entry.id)}
                                onCommit={() => handleCommit(entry.id)}
                                onCancel={() => handleCancel(entry.id)}
                            />
                        ))}
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>
        </div>
    )
}

// ===================== Manual Input Panel =====================

function ManualInputPanel({
    db,
    collection,
    connectionString,
    schema,
    schemaLoading,
    schemaError,
    onEntry,
}: {
    db: string
    collection: string
    connectionString: string
    schema: SchemaResponse | null
    schemaLoading: boolean
    schemaError: string
    onEntry: (e: MutationEntry) => void
}) {
    const [manualOp, setManualOp] = useState<"insert" | "update" | "delete">(
        "insert",
    )
    const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
    const [filterValues, setFilterValues] = useState<Record<string, string>>({})
    const [isExecuting, setIsExecuting] = useState(false)

    const fields = schema?.fields?.filter((f) => f !== "_id") ?? []
    const fieldTypes = schema?.field_types ?? {}

    const resetForm = () => {
        setFieldValues({})
        setFilterValues({})
    }

    const castValue = (field: string, raw: string): unknown => {
        const t = fieldTypes[field] ?? "str"
        if (raw === "") return undefined
        if (t === "int" || t === "float" || t === "number") {
            const n = Number(raw)
            return isNaN(n) ? raw : n
        }
        if (t === "bool") return raw.toLowerCase() === "true"
        return raw
    }

    const buildDocument = (
        vals: Record<string, string>,
    ): Record<string, unknown> => {
        const doc: Record<string, unknown> = {}
        for (const [k, v] of Object.entries(vals)) {
            if (v.trim() === "") continue
            const casted = castValue(k, v)
            if (casted !== undefined) doc[k] = casted
        }
        return doc
    }

    const handleExecute = async () => {
        if (!schema) return
        setIsExecuting(true)

        const id = `manual-${Date.now()}`
        let mutation: MutationPlan

        if (manualOp === "insert") {
            const doc = buildDocument(fieldValues)
            if (Object.keys(doc).length === 0) {
                onEntry({
                    id,
                    source: "manual",
                    query: "Manual insert",
                    timestamp: new Date(),
                    mutation: null,
                    stage: "error",
                    error: "Please fill in at least one field.",
                })
                setIsExecuting(false)
                return
            }
            mutation = {
                operation: "insert",
                description: `Insert a new document into ${collection}`,
                filter: null,
                update: null,
                document: doc,
                documents: null,
                multi: false,
                estimated_affected: null,
            }
        } else if (manualOp === "update") {
            const filter = buildDocument(filterValues)
            const updates = buildDocument(fieldValues)
            if (Object.keys(updates).length === 0) {
                onEntry({
                    id,
                    source: "manual",
                    query: "Manual update",
                    timestamp: new Date(),
                    mutation: null,
                    stage: "error",
                    error: "Please fill in at least one field to update.",
                })
                setIsExecuting(false)
                return
            }
            mutation = {
                operation: "update",
                description: `Update documents in ${collection} matching ${JSON.stringify(filter)}`,
                filter: Object.keys(filter).length > 0 ? filter : {},
                update: { $set: updates },
                document: null,
                documents: null,
                multi: Object.keys(filter).length === 0,
                estimated_affected: null,
            }
        } else {
            const filter = buildDocument(filterValues)
            if (Object.keys(filter).length === 0) {
                onEntry({
                    id,
                    source: "manual",
                    query: "Manual delete",
                    timestamp: new Date(),
                    mutation: null,
                    stage: "error",
                    error:
                        "Please specify at least one filter field to avoid deleting all documents.",
                })
                setIsExecuting(false)
                return
            }
            mutation = {
                operation: "delete",
                description: `Delete documents from ${collection} matching ${JSON.stringify(filter)}`,
                filter,
                update: null,
                document: null,
                documents: null,
                multi: true,
                estimated_affected: null,
            }
        }

        // Estimate affected count for update/delete (direct count — no LLM)
        if (manualOp !== "insert" && mutation.filter && Object.keys(mutation.filter).length > 0) {
            try {
                const result = await estimateMutation({
                    mongoUri: connectionString,
                    db,
                    collection,
                    filter: mutation.filter as Record<string, unknown>,
                })
                if (result.count != null)
                    mutation.estimated_affected = result.count
                if (result.sample_affected)
                    mutation.sample_affected = result.sample_affected
            } catch {
                // estimation failed — continue without it
            }
        }

        const opLabels = {
            insert: "Manual insert",
            update: "Manual update",
            delete: "Manual delete",
        }
        onEntry({
            id,
            source: "manual",
            query: opLabels[manualOp],
            timestamp: new Date(),
            mutation,
            stage: "preview",
        })

        resetForm()
        setIsExecuting(false)
    }

    // ---- Loading / error states ----

    if (schemaLoading) {
        return (
            <div className="border-b border-border bg-card px-6 py-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading collection schema…
                </div>
            </div>
        )
    }

    if (schemaError) {
        return (
            <div className="border-b border-border bg-card px-6 py-4">
                <div className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>Schema error: {schemaError}</span>
                </div>
            </div>
        )
    }

    if (!schema || fields.length === 0) {
        return (
            <div className="border-b border-border bg-card px-6 py-4">
                <p className="text-sm text-muted-foreground">
                    No schema fields detected.
                </p>
            </div>
        )
    }

    return (
        <div className="border-b border-border bg-card">
            {/* Operation selector */}
            <div className="flex items-center gap-2 border-b border-border px-6 py-2">
                <span className="text-xs font-medium text-muted-foreground">
                    Operation:
                </span>
                {(["insert", "update", "delete"] as const).map((op) => (
                    <button
                        key={op}
                        onClick={() => {
                            setManualOp(op)
                            resetForm()
                        }}
                        className={`inline-flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-medium capitalize transition-colors ${manualOp === op
                            ? `border ${opColor(op)}`
                            : "text-muted-foreground hover:text-foreground"
                            }`}
                    >
                        {opIcon(op)} {op}
                    </button>
                ))}
            </div>

            {/* Filter row (update / delete only) */}
            {manualOp !== "insert" && (
                <div className="border-b border-border px-6 py-3">
                    <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Filter — match documents where:
                    </p>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr>
                                    {fields.map((f) => (
                                        <th
                                            key={f}
                                            className="whitespace-nowrap border-b border-border px-2 py-1 text-left font-medium text-muted-foreground"
                                        >
                                            {f}
                                            <span className="ml-1 text-[10px] text-muted-foreground/60">
                                                ({fieldTypes[f] ?? "str"})
                                            </span>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    {fields.map((f) => (
                                        <td key={f} className="px-1 py-1">
                                            <input
                                                type="text"
                                                value={filterValues[f] ?? ""}
                                                onChange={(e) =>
                                                    setFilterValues((prev) => ({
                                                        ...prev,
                                                        [f]: e.target.value,
                                                    }))
                                                }
                                                placeholder="—"
                                                className="w-full min-w-[80px] rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none"
                                            />
                                        </td>
                                    ))}
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Values row (insert / update) */}
            {manualOp !== "delete" && (
                <div className="px-6 py-3">
                    <p className="mb-2 text-xs font-medium text-muted-foreground">
                        {manualOp === "insert" ? "New document values:" : "Set fields to:"}
                    </p>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr>
                                    {fields.map((f) => (
                                        <th
                                            key={f}
                                            className="whitespace-nowrap border-b border-border px-2 py-1 text-left font-medium text-muted-foreground"
                                        >
                                            {f}
                                            <span className="ml-1 text-[10px] text-muted-foreground/60">
                                                ({fieldTypes[f] ?? "str"})
                                            </span>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    {fields.map((f) => (
                                        <td key={f} className="px-1 py-1">
                                            <input
                                                type="text"
                                                value={fieldValues[f] ?? ""}
                                                onChange={(e) =>
                                                    setFieldValues((prev) => ({
                                                        ...prev,
                                                        [f]: e.target.value,
                                                    }))
                                                }
                                                placeholder="—"
                                                className="w-full min-w-[80px] rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground/40 focus:border-primary/50 focus:outline-none"
                                            />
                                        </td>
                                    ))}
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Execute button */}
            <div className="flex items-center gap-2 px-6 pb-3">
                <button
                    onClick={handleExecute}
                    disabled={isExecuting}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                >
                    {isExecuting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Eye className="h-4 w-4" />
                    )}
                    Execute &amp; Preview
                </button>
                <button
                    onClick={resetForm}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary px-3 py-2 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
                >
                    <X className="h-3.5 w-3.5" />
                    Clear
                </button>
            </div>
        </div>
    )
}

// ===================== Query Input Panel =====================

function QueryInputPanel({
    db,
    collection,
    connectionString,
    entries,
    onEntry,
    onUpdateEntry,
}: {
    db: string
    collection: string
    connectionString: string
    entries: MutationEntry[]
    onEntry: (e: MutationEntry) => void
    onUpdateEntry: (id: string, patch: Partial<MutationEntry>) => void
}) {
    const [input, setInput] = useState("")
    const inputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    const buildHistory = useCallback(() => {
        return entries
            .filter((e) => e.stage !== "loading")
            .flatMap(
                (e): Array<{ role: "user" | "assistant"; content: string }> => [
                    { role: "user", content: e.query },
                    {
                        role: "assistant",
                        content: e.mutation?.description ?? e.error ?? "No result",
                    },
                ],
            )
    }, [entries])

    const handleSend = async () => {
        const trimmed = input.trim()
        if (!trimmed) return

        const id = `query-${Date.now()}`
        onEntry({
            id,
            source: "query",
            query: trimmed,
            timestamp: new Date(),
            mutation: null,
            stage: "loading",
        })
        setInput("")

        try {
            const result = await previewMutation({
                mongoUri: connectionString,
                db,
                collection,
                query: trimmed,
                history: buildHistory(),
            })
            onUpdateEntry(id, { mutation: result.mutation, stage: "preview" })
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Preview failed"
            onUpdateEntry(id, { stage: "error", error: msg })
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="border-b border-border bg-card px-6 py-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
                Describe what you want to change in plain English:
            </p>
            <div className="flex items-center gap-3">
                <div className="flex flex-1 items-center rounded-xl border border-border bg-input px-4 py-2.5 focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-ring/30">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={`e.g. "Add a user named John" or "Delete all inactive users"…`}
                        className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                        aria-label="Mutation query input"
                    />
                </div>
                <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Preview mutation"
                >
                    <Send className="h-4 w-4" />
                </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
                {[
                    "Add a new user named John with email john@test.com",
                    "Update all orders with status pending to processing",
                    "Delete users where last_login is before 2023",
                ].map((s) => (
                    <button
                        key={s}
                        onClick={() => setInput(s)}
                        className="rounded-md border border-border bg-muted/50 px-2 py-0.5 font-mono text-[10px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                    >
                        {s}
                    </button>
                ))}
            </div>
        </div>
    )
}

// ===================== Mutation Card =====================
// Workflow: Preview → Add → Commit
//   preview:    shows mutation details + [Add] [Cancel]
//   added:      shows "Ready to Commit" + [Commit] [Cancel]
//   committing: spinner
//   committed:  green success summary
//   error:      red error card

function MutationCard({
    entry,
    isJsonExpanded,
    onToggleJson,
    onAdd,
    onCommit,
    onCancel,
}: {
    entry: MutationEntry
    isJsonExpanded: boolean
    onToggleJson: () => void
    onAdd: () => void
    onCommit: () => void
    onCancel: () => void
}) {
    const { stage, query, mutation, commitResult, error, source } = entry

    return (
        <div className="rounded-xl border border-border bg-card shadow-sm">
            {/* Header */}
            <div className="flex items-start gap-3 border-b border-border px-4 py-3">
                <span
                    className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${source === "manual"
                        ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                        : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                        }`}
                >
                    {source}
                </span>
                <p className="text-sm leading-relaxed text-foreground">{query}</p>
                <span className="ml-auto whitespace-nowrap text-[10px] font-medium uppercase text-muted-foreground">
                    {stage === "loading" && "Processing…"}
                    {stage === "preview" && "Preview"}
                    {stage === "added" && "Ready to Commit"}
                    {stage === "committing" && "Committing…"}
                    {stage === "committed" && "Committed ✓"}
                    {stage === "error" && "Error"}
                </span>
            </div>

            <div className="px-4 py-3">
                {/* Loading */}
                {(stage === "loading" || stage === "committing") && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {stage === "loading"
                            ? "AI is analysing your query and building a mutation plan…"
                            : "Executing mutation on MongoDB cluster…"}
                    </div>
                )}

                {/* Error */}
                {stage === "error" && (
                    <div className="space-y-2">
                        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>{error}</span>
                        </div>
                        <button
                            onClick={onCancel}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
                        >
                            <X className="h-3.5 w-3.5" />
                            Dismiss
                        </button>
                    </div>
                )}

                {/* Preview / Added / Committed */}
                {(stage === "preview" || stage === "added" || stage === "committed") &&
                    mutation && (
                        <>
                            {/* Operation badge */}
                            <div className="mb-3 flex flex-wrap items-center gap-2">
                                <span
                                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase ${opColor(mutation.operation)}`}
                                >
                                    {opIcon(mutation.operation)}
                                    {mutation.operation}
                                </span>
                                {mutation.multi && (
                                    <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                        Multi
                                    </span>
                                )}
                            </div>

                            <p className="mb-3 text-sm text-foreground">
                                {mutation.description}
                            </p>

                            {/* Estimated affected */}
                            {typeof mutation.estimated_affected === "number" && (
                                <div className="mb-3 flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-sm">
                                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                                    <span>
                                        <strong>{mutation.estimated_affected}</strong> document
                                        {mutation.estimated_affected !== 1 ? "s" : ""} will be
                                        affected
                                    </span>
                                </div>
                            )}

                            {/* Sample affected documents */}
                            {mutation.sample_affected &&
                                mutation.sample_affected.length > 0 && (
                                    <div className="mb-3">
                                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                                            Sample affected:
                                        </p>
                                        <div className="max-h-40 overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                            <pre className="text-xs leading-relaxed text-foreground/80">
                                                {JSON.stringify(mutation.sample_affected, null, 2)}
                                            </pre>
                                        </div>
                                    </div>
                                )}

                            {/* Insert document preview */}
                            {mutation.operation === "insert" && mutation.document && (
                                <div className="mb-3">
                                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                                        Document to insert:
                                    </p>
                                    <div className="max-h-40 overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                        <pre className="text-xs leading-relaxed text-foreground/80">
                                            {JSON.stringify(mutation.document, null, 2)}
                                        </pre>
                                    </div>
                                </div>
                            )}

                            {/* Update filter + update preview */}
                            {mutation.operation === "update" && (
                                <div className="mb-3 grid gap-2 sm:grid-cols-2">
                                    {mutation.filter && (
                                        <div>
                                            <p className="mb-1 text-xs font-medium text-muted-foreground">
                                                Filter:
                                            </p>
                                            <div className="overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                                <pre className="text-xs text-foreground/80">
                                                    {JSON.stringify(mutation.filter, null, 2)}
                                                </pre>
                                            </div>
                                        </div>
                                    )}
                                    {mutation.update && (
                                        <div>
                                            <p className="mb-1 text-xs font-medium text-muted-foreground">
                                                Update:
                                            </p>
                                            <div className="overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                                <pre className="text-xs text-foreground/80">
                                                    {JSON.stringify(mutation.update, null, 2)}
                                                </pre>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Delete filter preview */}
                            {mutation.operation === "delete" && mutation.filter && (
                                <div className="mb-3">
                                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                                        Delete filter:
                                    </p>
                                    <div className="overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                        <pre className="text-xs text-foreground/80">
                                            {JSON.stringify(mutation.filter, null, 2)}
                                        </pre>
                                    </div>
                                </div>
                            )}

                            {/* Raw JSON toggle */}
                            <button
                                onClick={onToggleJson}
                                className="mb-3 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                            >
                                <FileJson className="h-3.5 w-3.5" />
                                {isJsonExpanded ? "Hide" : "Show"} raw mutation
                                {isJsonExpanded ? (
                                    <ChevronUp className="h-3 w-3" />
                                ) : (
                                    <ChevronDown className="h-3 w-3" />
                                )}
                            </button>
                            {isJsonExpanded && (
                                <div className="mb-3 max-h-60 overflow-auto rounded-lg border border-border bg-muted/30 p-2">
                                    <pre className="text-xs leading-relaxed text-foreground/80">
                                        {JSON.stringify(mutation, null, 2)}
                                    </pre>
                                </div>
                            )}

                            {/* ===== Workflow buttons ===== */}

                            {/* Stage: Preview → [Add] [Cancel] */}
                            {stage === "preview" && (
                                <div className="flex items-center gap-2 pt-1">
                                    <button
                                        onClick={onAdd}
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                                    >
                                        <PlusCircle className="h-4 w-4" />
                                        Add
                                    </button>
                                    <button
                                        onClick={onCancel}
                                        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
                                    >
                                        <XCircle className="h-4 w-4" />
                                        Cancel
                                    </button>
                                </div>
                            )}

                            {/* Stage: Added → [Commit] [Cancel] */}
                            {stage === "added" && (
                                <div className="flex items-center gap-2 pt-1">
                                    <button
                                        onClick={onCommit}
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
                                    >
                                        <GitCommitHorizontal className="h-4 w-4" />
                                        Commit to MongoDB
                                    </button>
                                    <button
                                        onClick={onCancel}
                                        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
                                    >
                                        <XCircle className="h-4 w-4" />
                                        Cancel
                                    </button>
                                </div>
                            )}

                            {/* Stage: Committed */}
                            {stage === "committed" && commitResult && (
                                <div className="flex items-start gap-2 rounded-lg bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
                                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                                    <div>
                                        <span className="font-medium">
                                            Committed successfully — changes are live on MongoDB
                                            Console &amp; Cluster.
                                        </span>
                                        <ul className="mt-1 space-y-0.5 text-xs">
                                            {typeof commitResult.inserted_count === "number" && (
                                                <li>Inserted: {commitResult.inserted_count}</li>
                                            )}
                                            {typeof commitResult.matched_count === "number" && (
                                                <li>Matched: {commitResult.matched_count}</li>
                                            )}
                                            {typeof commitResult.modified_count === "number" && (
                                                <li>Modified: {commitResult.modified_count}</li>
                                            )}
                                            {typeof commitResult.deleted_count === "number" && (
                                                <li>Deleted: {commitResult.deleted_count}</li>
                                            )}
                                        </ul>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
            </div>
        </div>
    )
}
