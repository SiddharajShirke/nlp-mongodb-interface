"use client"

import { useState } from "react"
import {
    ChevronDown,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Database,
    FileSearch,
    Code2,
    ArrowRight,
    Shield,
    Play,
    BarChart3,
    Layers,
} from "lucide-react"
import type {
    DiagnoseSteps,
    DiagnoseStep0,
    DiagnoseStep1,
    DiagnoseStep2,
    DiagnoseStep3Entry,
    DiagnoseStep4,
    DiagnoseStep5,
    DiagnoseStep6,
    DiagnoseStep7,
} from "@/lib/api/gateway"

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function StatusBadge({ status }: { status?: string }) {
    if (status === "ok") {
        return (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2 py-0.5 text-[10px] font-semibold text-green-400">
                <CheckCircle2 className="h-3 w-3" /> Passed
            </span>
        )
    }
    if (status === "error") {
        return (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-400">
                <XCircle className="h-3 w-3" /> Error
            </span>
        )
    }
    return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
            <AlertTriangle className="h-3 w-3" /> Unknown
        </span>
    )
}

const TYPE_COLORS: Record<string, string> = {
    string: "bg-blue-500/15 text-blue-400",
    int: "bg-emerald-500/15 text-emerald-400",
    double: "bg-emerald-500/15 text-emerald-400",
    number: "bg-emerald-500/15 text-emerald-400",
    bool: "bg-purple-500/15 text-purple-400",
    date: "bg-orange-500/15 text-orange-400",
    objectId: "bg-pink-500/15 text-pink-400",
    object: "bg-yellow-500/15 text-yellow-400",
    array: "bg-cyan-500/15 text-cyan-400",
}

function TypeTag({ type }: { type: string }) {
    const color = TYPE_COLORS[type] ?? "bg-muted text-muted-foreground"
    return (
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${color}`}>
            {type}
        </span>
    )
}

function CodeBlock({ code, label }: { code: string | null | undefined; label?: string }) {
    if (!code) return null
    return (
        <div className="mt-1.5">
            {label && (
                <span className="mb-0.5 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    {label}
                </span>
            )}
            <pre className="overflow-x-auto rounded-md border border-border bg-background/60 p-2 font-mono text-[11px] leading-relaxed text-foreground">
                {code}
            </pre>
        </div>
    )
}

/* ------------------------------------------------------------------ */
/*  Collapsible Step Card                                              */
/* ------------------------------------------------------------------ */

function StepCard({
    stepNumber,
    title,
    icon: Icon,
    status,
    defaultOpen = false,
    children,
}: {
    stepNumber: number
    title: string
    icon: React.ComponentType<{ className?: string }>
    status?: string
    defaultOpen?: boolean
    children: React.ReactNode
}) {
    const [open, setOpen] = useState(defaultOpen)

    return (
        <div className="rounded-lg border border-border bg-card/50 overflow-hidden">
            <button
                onClick={() => setOpen((v) => !v)}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/30"
            >
                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-primary/10 text-[10px] font-bold text-primary">
                    {stepNumber}
                </span>
                <Icon className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                <span className="flex-1 text-xs font-medium text-foreground">{title}</span>
                <StatusBadge status={status} />
                <ChevronDown
                    className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
                />
            </button>
            {open && <div className="border-t border-border px-3 py-3">{children}</div>}
        </div>
    )
}

/* ------------------------------------------------------------------ */
/*  Individual Step Renderers                                          */
/* ------------------------------------------------------------------ */

function Step0Content({ data }: { data: DiagnoseStep0 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
                Total documents:{" "}
                <span className="font-semibold text-foreground">{data.total_documents ?? "?"}</span>
            </p>
            {data.sample_fields && (
                <div className="space-y-1">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Sample Fields
                    </span>
                    <div className="max-h-48 overflow-y-auto rounded-md border border-border bg-background/60 p-2">
                        {Object.entries(data.sample_fields).map(([field, desc]) => (
                            <div key={field} className="flex gap-2 py-0.5 text-[11px]">
                                <span className="font-mono font-medium text-foreground">{field}</span>
                                <span className="truncate text-muted-foreground">{desc}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

function Step1Content({ data }: { data: DiagnoseStep1 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
                Detected{" "}
                <span className="font-semibold text-foreground">{data.field_count ?? 0}</span> fields
            </p>
            {data.field_types && (
                <div className="flex flex-wrap gap-1.5">
                    {Object.entries(data.field_types).map(([field, type]) => (
                        <span
                            key={field}
                            className="inline-flex items-center gap-1 rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px]"
                        >
                            <span className="font-mono font-medium text-foreground">{field}</span>
                            <TypeTag type={type} />
                        </span>
                    ))}
                </div>
            )}
        </div>
    )
}

function Step2Content({ data }: { data: DiagnoseStep2 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    const ir = data.raw_ir
    return (
        <div className="space-y-2">
            <div className="flex items-center gap-3 text-xs">
                <span className="text-muted-foreground">
                    Parser:{" "}
                    <span className="font-semibold text-foreground">{data.parser ?? "unknown"}</span>
                </span>
                {ir?.operation && (
                    <span className="text-muted-foreground">
                        Operation:{" "}
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono font-semibold text-primary">
                            {ir.operation}
                        </span>
                    </span>
                )}
            </div>
            {ir?.conditions && ir.conditions.length > 0 && (
                <div className="space-y-1">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Conditions
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                        {ir.conditions.map((c, i) => (
                            <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded border border-border bg-background/60 px-2 py-1 text-[11px]"
                            >
                                <span className="font-mono font-medium text-foreground">{c.field}</span>
                                <span className="rounded bg-amber-500/15 px-1 font-mono text-[10px] font-bold text-amber-400">
                                    {c.operator}
                                </span>
                                <span className="text-muted-foreground">
                                    {typeof c.value === "object" ? JSON.stringify(c.value) : String(c.value ?? "")}
                                </span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
            {ir?.aggregation && (
                <p className="text-xs text-muted-foreground">
                    Aggregation:{" "}
                    <span className="font-semibold text-foreground">
                        {ir.aggregation.type}({ir.aggregation.field})
                    </span>
                </p>
            )}
            {ir?.sort && (
                <p className="text-xs text-muted-foreground">
                    Sort:{" "}
                    <span className="font-semibold text-foreground">
                        {ir.sort.field} {ir.sort.direction}
                    </span>
                </p>
            )}
            {typeof ir?.limit === "number" && (
                <p className="text-xs text-muted-foreground">
                    Limit: <span className="font-semibold text-foreground">{ir.limit}</span>
                </p>
            )}
        </div>
    )
}

function Step3Content({ data }: { data: DiagnoseStep3Entry[] }) {
    if (!data || data.length === 0) {
        return <p className="text-xs text-muted-foreground">No fields to resolve.</p>
    }
    return (
        <div className="space-y-1.5">
            {data.map((entry, i) => (
                <div
                    key={i}
                    className={`flex items-center gap-2 rounded border px-2 py-1.5 text-[11px] ${entry.matched
                            ? "border-green-500/30 bg-green-500/5"
                            : "border-red-500/30 bg-red-500/5"
                        }`}
                >
                    <span className="font-mono text-muted-foreground">{entry.raw_field}</span>
                    <ArrowRight className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                    <span
                        className={`font-mono font-medium ${entry.matched ? "text-green-400" : "text-red-400"
                            }`}
                    >
                        {entry.resolved_field ?? "(unresolved)"}
                    </span>
                    {entry.context && (
                        <span className="ml-auto rounded bg-muted px-1 text-[9px] text-muted-foreground">
                            {entry.context}
                        </span>
                    )}
                    {entry.matched ? (
                        <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-green-400" />
                    ) : (
                        <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-red-400" />
                    )}
                </div>
            ))}
        </div>
    )
}

function Step4Content({ data }: { data: DiagnoseStep4 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    return (
        <div className="space-y-2">
            <CodeBlock
                code={data.validated_ir ? JSON.stringify(data.validated_ir, null, 2) : null}
                label="Validated IR"
            />
        </div>
    )
}

function Step5Content({ data }: { data: DiagnoseStep5 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
                Query type:{" "}
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono font-semibold text-primary">
                    {data.type ?? "?"}
                </span>
            </p>
            <CodeBlock code={data.filter} label="Filter" />
            {data.sort && data.sort !== "None" && <CodeBlock code={data.sort} label="Sort" />}
            {typeof data.limit === "number" && (
                <p className="text-xs text-muted-foreground">
                    Limit: <span className="font-semibold text-foreground">{data.limit}</span>
                </p>
            )}
            <CodeBlock code={data.pipeline} label="Pipeline" />
        </div>
    )
}

function Step6Content({ data }: { data: DiagnoseStep6 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    return (
        <div className="space-y-2">
            <div className="flex items-center gap-6 text-xs">
                <span className="text-muted-foreground">
                    Total matched:{" "}
                    <span className="text-lg font-bold text-foreground">
                        {data.total_count ?? 0}
                    </span>
                </span>
                <span className="text-muted-foreground">
                    Returned:{" "}
                    <span className="font-semibold text-foreground">{data.returned ?? 0}</span>
                </span>
            </div>
            {data.sample_docs && data.sample_docs.length > 0 && (
                <div className="space-y-1">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Sample Documents
                    </span>
                    <div className="max-h-60 overflow-y-auto rounded-md border border-border bg-background/60 p-2">
                        {data.sample_docs.map((doc, i) => (
                            <pre
                                key={i}
                                className="mb-1.5 border-b border-border pb-1.5 font-mono text-[10px] leading-relaxed text-foreground last:mb-0 last:border-0 last:pb-0"
                            >
                                {JSON.stringify(doc, null, 2)}
                            </pre>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

function Step7Content({ data }: { data: DiagnoseStep7 }) {
    if (data.error) return <p className="text-xs text-red-400">{data.error}</p>
    const hasUnindexed = data.unindexed_fields && data.unindexed_fields.length > 0
    return (
        <div className="space-y-2">
            {data.indexed_fields && data.indexed_fields.length > 0 && (
                <div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Indexed Fields
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                        {data.indexed_fields.map((f) => (
                            <span
                                key={f}
                                className="rounded bg-green-500/15 px-1.5 py-0.5 font-mono text-[10px] text-green-400"
                            >
                                {f}
                            </span>
                        ))}
                    </div>
                </div>
            )}
            {data.queried_fields && data.queried_fields.length > 0 && (
                <div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                        Queried Fields
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                        {data.queried_fields.map((f) => (
                            <span
                                key={f}
                                className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${data.unindexed_fields?.includes(f)
                                        ? "bg-red-500/15 text-red-400"
                                        : "bg-green-500/15 text-green-400"
                                    }`}
                            >
                                {f}
                            </span>
                        ))}
                    </div>
                </div>
            )}
            {hasUnindexed && (
                <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
                    <p className="text-[11px] text-amber-300">
                        <span className="font-semibold">Performance warning:</span> Queried fields{" "}
                        <span className="font-mono font-medium">
                            {data.unindexed_fields?.join(", ")}
                        </span>{" "}
                        are not indexed. Consider adding indexes for better performance on large collections.
                    </p>
                </div>
            )}
        </div>
    )
}

/* ------------------------------------------------------------------ */
/*  Main DiagnoseTrace Component                                       */
/* ------------------------------------------------------------------ */

export function DiagnoseTrace({
    query,
    steps,
}: {
    query: string
    steps: DiagnoseSteps
}) {
    const step0 = steps["0_raw_sample"]
    const step1 = steps["1_schema"]
    const step2 = steps["2_parse"]
    const step3 = steps["3_resolve"]
    const step4 = steps["4_validate"]
    const step5 = steps["5_compile"]
    const step6 = steps["6_execute_preview"]
    const step7 = steps["7_index_info"]

    const stepStatus = (step?: { status?: string; error?: string } | null) => {
        if (!step) return undefined
        if ("error" in step && step.error) return "error"
        return step.status
    }

    return (
        <div className="mt-2 space-y-2">
            <div className="flex items-center gap-2 rounded-md bg-muted/30 px-3 py-2">
                <Layers className="h-4 w-4 text-primary" />
                <span className="text-xs font-medium text-foreground">Pipeline Trace</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                    &ldquo;{query}&rdquo;
                </span>
            </div>

            <div className="space-y-1.5">
                {step0 && (
                    <StepCard
                        stepNumber={0}
                        title="Collection Inspection"
                        icon={Database}
                        status={step0.error ? "error" : "ok"}
                    >
                        <Step0Content data={step0} />
                    </StepCard>
                )}
                {step1 && (
                    <StepCard
                        stepNumber={1}
                        title="Schema Detection"
                        icon={FileSearch}
                        status={stepStatus(step1)}
                    >
                        <Step1Content data={step1} />
                    </StepCard>
                )}
                {step2 && (
                    <StepCard
                        stepNumber={2}
                        title="NL Parse"
                        icon={Code2}
                        status={stepStatus(step2)}
                        defaultOpen
                    >
                        <Step2Content data={step2} />
                    </StepCard>
                )}
                {step3 && (
                    <StepCard
                        stepNumber={3}
                        title="Field Resolution"
                        icon={ArrowRight}
                        status={
                            Array.isArray(step3)
                                ? step3.every((e) => e.matched)
                                    ? "ok"
                                    : step3.some((e) => !e.matched)
                                        ? "error"
                                        : "ok"
                                : undefined
                        }
                    >
                        <Step3Content data={step3} />
                    </StepCard>
                )}
                {step4 && (
                    <StepCard
                        stepNumber={4}
                        title="IR Validation"
                        icon={Shield}
                        status={stepStatus(step4)}
                    >
                        <Step4Content data={step4} />
                    </StepCard>
                )}
                {step5 && (
                    <StepCard
                        stepNumber={5}
                        title="MongoDB Compilation"
                        icon={Code2}
                        status={stepStatus(step5)}
                    >
                        <Step5Content data={step5} />
                    </StepCard>
                )}
                {step6 && (
                    <StepCard
                        stepNumber={6}
                        title="Execution Preview"
                        icon={Play}
                        status={stepStatus(step6)}
                        defaultOpen
                    >
                        <Step6Content data={step6} />
                    </StepCard>
                )}
                {step7 && (
                    <StepCard
                        stepNumber={7}
                        title="Index Analysis"
                        icon={BarChart3}
                        status={
                            step7.error
                                ? "error"
                                : step7.unindexed_fields && step7.unindexed_fields.length > 0
                                    ? "ok" // still ok but with warning inside
                                    : "ok"
                        }
                    >
                        <Step7Content data={step7} />
                    </StepCard>
                )}
            </div>
        </div>
    )
}
