"use client"

import { useEffect, useState, useCallback } from "react"
import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import {
    fetchCommitTimeline,
    type CommitTimelineEntry,
    type AnalyticsFilterParams,
} from "@/lib/api/gateway"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    type ChartConfig,
} from "@/components/ui/chart"
import { AreaChart, Area, XAxis, YAxis, CartesianGrid } from "recharts"
import { GitCommitHorizontal, RefreshCw } from "lucide-react"

const chartConfig: ChartConfig = {
    commits: {
        label: "Commits",
        color: "var(--chart-1)",
    },
}

/** Preset time ranges */
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

interface TimelinePoint {
    time: string
    commits: number
}

export function CommitTrackingChart() {
    const { user } = useAuth()
    const { connectionString, selectedDB } = useAppContext()

    const [timeline, setTimeline] = useState<CommitTimelineEntry[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [presetIdx, setPresetIdx] = useState(5) // default "7 days"

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

            const res = await fetchCommitTimeline(params)
            setTimeline(res.timeline ?? [])
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load")
        } finally {
            setLoading(false)
        }
    }, [connectionString, selectedDB, user?.email, presetIdx])

    useEffect(() => {
        load()
    }, [load])

    // Aggregate timeline entries by bucket for the area chart
    const chartData: TimelinePoint[] = (() => {
        const byBucket = new Map<string, number>()
        for (const entry of timeline) {
            const ts = new Date(entry.timestamp)
            // Auto-detect bucket size from preset
            const preset = TIME_PRESETS[presetIdx]
            const totalMins = "minutes" in preset ? preset.minutes : "hours" in preset ? preset.hours * 60 : preset.days * 1440
            let label: string
            if (totalMins <= 120) {
                label = ts.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
            } else if (totalMins <= 72 * 60) {
                label = ts.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit" })
            } else if (totalMins <= 90 * 1440) {
                label = ts.toLocaleDateString("en-US", { month: "short", day: "numeric" })
            } else {
                label = ts.toLocaleDateString("en-US", { year: "numeric", month: "short" })
            }
            byBucket.set(label, (byBucket.get(label) ?? 0) + 1)
        }
        return Array.from(byBucket.entries()).map(([time, commits]) => ({ time, commits }))
    })()

    const preset = TIME_PRESETS[presetIdx]
    const rangeLabel = preset.label

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <GitCommitHorizontal className="h-4 w-4 text-primary" />
                            Commit Timeline
                        </CardTitle>
                        <CardDescription>
                            Database mutations — last {rangeLabel}
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
                {error ? (
                    <p className="py-8 text-center text-sm text-destructive">{error}</p>
                ) : chartData.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <GitCommitHorizontal className="mb-2 h-8 w-8 opacity-40" />
                        <p className="text-sm">No commits recorded yet</p>
                        <p className="text-xs">Mutations you make will appear here</p>
                    </div>
                ) : (
                    <ChartContainer config={chartConfig} className="h-[250px] w-full">
                        <AreaChart data={chartData} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                            <defs>
                                <linearGradient id="commitGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--color-commits)" stopOpacity={0.4} />
                                    <stop offset="95%" stopColor="var(--color-commits)" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
                            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tickMargin={4} fontSize={11} width={30} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Area type="monotone" dataKey="commits" stroke="var(--color-commits)" strokeWidth={2} fill="url(#commitGradient)" />
                        </AreaChart>
                    </ChartContainer>
                )}

                {/* Recent Commits Table */}
                {timeline.length > 0 && (
                    <div className="mt-4 max-h-48 overflow-y-auto rounded-md border border-border">
                        <table className="w-full text-xs">
                            <thead className="sticky top-0 bg-secondary text-muted-foreground">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium">Time</th>
                                    <th className="px-3 py-2 text-left font-medium">Collection</th>
                                    <th className="px-3 py-2 text-left font-medium">Operation</th>
                                    <th className="px-3 py-2 text-left font-medium">User</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {timeline.slice(0, 50).map((entry, i) => (
                                    <tr key={i} className="hover:bg-secondary/50">
                                        <td className="whitespace-nowrap px-3 py-1.5 font-mono text-muted-foreground">
                                            {new Date(entry.timestamp).toLocaleString("en-US", {
                                                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                                            })}
                                        </td>
                                        <td className="px-3 py-1.5 font-medium">{entry.collection_name}</td>
                                        <td className="px-3 py-1.5">
                                            <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-primary">
                                                {(entry.details?.operation as string) ?? "commit"}
                                            </span>
                                        </td>
                                        <td className="px-3 py-1.5 text-muted-foreground">{entry.user_email ?? "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
