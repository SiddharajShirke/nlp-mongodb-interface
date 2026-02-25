"use client"

import { useEffect, useState, useCallback } from "react"
import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import {
    fetchActivityStats,
    type ActivityStatsResponse,
    type AnalyticsFilterParams,
} from "@/lib/api/gateway"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
    type ChartConfig,
} from "@/components/ui/chart"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts"
import { Activity, RefreshCw, Search, Stethoscope, GitCommitHorizontal } from "lucide-react"

const chartConfig: ChartConfig = {
    query: { label: "Queries", color: "var(--chart-1)" },
    diagnose: { label: "Diagnoses", color: "var(--chart-2)" },
    commit: { label: "Commits", color: "var(--chart-3)" },
}

const TIME_PRESETS = [
    { label: "5 min", minutes: 5 },
    { label: "30 min", minutes: 30 },
    { label: "1 hr", hours: 1 },
    { label: "6 hr", hours: 6 },
    { label: "24 hr", days: 1 },
    { label: "7 days", days: 7 },
    { label: "30 days", days: 30 },
    { label: "90 days", days: 90 },
    { label: "1 year", days: 365 },
] as const

export function ActivityOverviewChart() {
    const { user } = useAuth()
    const { connectionString, selectedDB } = useAppContext()

    const [stats, setStats] = useState<ActivityStatsResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [presetIdx, setPresetIdx] = useState(6) // default "30 days"

    const load = useCallback(async () => {
        if (!connectionString || !selectedDB) return
        setLoading(true)
        setError(null)
        try {
            const preset = TIME_PRESETS[presetIdx]
            const params: AnalyticsFilterParams = {
                mongoUri: connectionString,
                db: selectedDB,
                userEmail: user?.email,
            }
            if ("minutes" in preset) params.minutes = preset.minutes
            else if ("hours" in preset) params.hours = preset.hours
            else if ("days" in preset) params.days = preset.days

            const res = await fetchActivityStats(params)
            setStats(res)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load")
        } finally {
            setLoading(false)
        }
    }, [connectionString, selectedDB, user?.email, presetIdx])

    useEffect(() => {
        load()
    }, [load])

    const totals = stats?.totals ?? { query: 0, diagnose: 0, commit: 0 }
    const timeline = stats?.timeline ?? []
    const topCollections = stats?.top_collections ?? []
    const granularity = stats?.granularity ?? "day"
    const rangeLabel = TIME_PRESETS[presetIdx].label

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Activity className="h-4 w-4 text-primary" />
                            Activity Overview
                        </CardTitle>
                        <CardDescription>
                            Operations breakdown — last {rangeLabel} (per {granularity})
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <select
                            value={presetIdx}
                            onChange={(e) => setPresetIdx(Number(e.target.value))}
                            className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
                        >
                            {TIME_PRESETS.map((p, i) => (
                                <option key={i} value={i}>{p.label}</option>
                            ))}
                        </select>
                        <button
                            onClick={load}
                            disabled={loading}
                            className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-secondary text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                            aria-label="Refresh"
                        >
                            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        </button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {/* Summary Cards */}
                <div className="mb-4 grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-border bg-secondary/30 p-3 text-center">
                        <Search className="mx-auto mb-1 h-4 w-4 text-chart-1" />
                        <p className="text-2xl font-bold tabular-nums">{totals.query ?? 0}</p>
                        <p className="text-xs text-muted-foreground">Queries</p>
                    </div>
                    <div className="rounded-lg border border-border bg-secondary/30 p-3 text-center">
                        <Stethoscope className="mx-auto mb-1 h-4 w-4 text-chart-2" />
                        <p className="text-2xl font-bold tabular-nums">{totals.diagnose ?? 0}</p>
                        <p className="text-xs text-muted-foreground">Diagnoses</p>
                    </div>
                    <div className="rounded-lg border border-border bg-secondary/30 p-3 text-center">
                        <GitCommitHorizontal className="mx-auto mb-1 h-4 w-4 text-chart-3" />
                        <p className="text-2xl font-bold tabular-nums">{totals.commit ?? 0}</p>
                        <p className="text-xs text-muted-foreground">Commits</p>
                    </div>
                </div>

                {error ? (
                    <p className="py-8 text-center text-sm text-destructive">{error}</p>
                ) : timeline.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Activity className="mb-2 h-8 w-8 opacity-40" />
                        <p className="text-sm">No activity recorded yet</p>
                        <p className="text-xs">Start querying or editing data to see analytics</p>
                    </div>
                ) : (
                    <ChartContainer config={chartConfig} className="h-[250px] w-full">
                        <BarChart data={timeline} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis
                                dataKey="bucket"
                                tickLine={false}
                                axisLine={false}
                                tickMargin={8}
                                fontSize={11}
                            />
                            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tickMargin={4} fontSize={11} width={30} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <ChartLegend content={<ChartLegendContent />} />
                            <Bar dataKey="query" stackId="a" fill="var(--color-query)" radius={[0, 0, 0, 0]} />
                            <Bar dataKey="diagnose" stackId="a" fill="var(--color-diagnose)" radius={[0, 0, 0, 0]} />
                            <Bar dataKey="commit" stackId="a" fill="var(--color-commit)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ChartContainer>
                )}

                {/* Top Collections */}
                {topCollections.length > 0 && (
                    <div className="mt-4">
                        <p className="mb-2 text-xs font-medium text-muted-foreground">Top Collections</p>
                        <div className="space-y-1.5">
                            {topCollections.slice(0, 5).map((col) => {
                                const maxCount = topCollections[0]?.count ?? 1
                                const pct = Math.round((col.count / maxCount) * 100)
                                return (
                                    <div key={col.name} className="flex items-center gap-2">
                                        <span className="w-28 truncate text-xs font-medium">{col.name}</span>
                                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                                            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
                                        </div>
                                        <span className="w-8 text-right text-xs tabular-nums text-muted-foreground">{col.count}</span>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
