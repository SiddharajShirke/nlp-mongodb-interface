"use client"

import { useEffect, useState, useCallback } from "react"
import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import {
    fetchDiagnosisMonthly,
    type DiagnosisMonthlyEntry,
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
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    PieChart,
    Pie,
    Cell,
    LineChart,
    Line,
} from "recharts"
import { Stethoscope, RefreshCw, TrendingUp, ShieldCheck, ShieldAlert, ShieldX } from "lucide-react"

const severityChartConfig: ChartConfig = {
    ok: { label: "OK", color: "oklch(0.72 0.19 155)" },
    warning: { label: "Warning", color: "oklch(0.75 0.18 80)" },
    error: { label: "Error", color: "oklch(0.55 0.22 27)" },
}

const monthlyChartConfig: ChartConfig = {
    total: { label: "Total", color: "var(--chart-2)" },
    score: { label: "Health Score", color: "var(--chart-1)" },
}

const PIE_COLORS = [
    "oklch(0.72 0.19 155)",
    "oklch(0.75 0.18 80)",
    "oklch(0.55 0.22 27)",
]

const MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

export function DiagnosisAnalyticsChart() {
    const { user } = useAuth()
    const { connectionString, selectedDB } = useAppContext()

    const [monthly, setMonthly] = useState<DiagnosisMonthlyEntry[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Granular filters
    const currentYear = new Date().getFullYear()
    const [selectedYear, setSelectedYear] = useState(currentYear)
    const [selectedMonth, setSelectedMonth] = useState<number | "">("") // 1-12 or ""=all
    const [selectedDay, setSelectedDay] = useState<number | "">("") // 1-31 or ""=all

    const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - i)

    const load = useCallback(async () => {
        if (!connectionString || !selectedDB) return
        setLoading(true)
        setError(null)
        try {
            const params: AnalyticsFilterParams = {
                mongoUri: connectionString,
                db: selectedDB,
                userEmail: user?.email,
                year: selectedYear,
            }
            if (selectedMonth !== "") params.month = selectedMonth
            if (selectedDay !== "") params.day = selectedDay

            // Auto granularity: year→month, month→day, day→hour
            if (selectedDay !== "") params.granularity = "hour"
            else if (selectedMonth !== "") params.granularity = "day"
            else params.granularity = "month"

            const res = await fetchDiagnosisMonthly(params)
            setMonthly(res.monthly ?? [])
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load")
        } finally {
            setLoading(false)
        }
    }, [connectionString, selectedDB, user?.email, selectedYear, selectedMonth, selectedDay])

    useEffect(() => {
        load()
    }, [load])

    // Reset dependent filters on parent change
    const handleYearChange = (y: number) => {
        setSelectedYear(y)
        setSelectedMonth("")
        setSelectedDay("")
    }
    const handleMonthChange = (m: number | "") => {
        setSelectedMonth(m)
        setSelectedDay("")
    }

    // Build filter description
    const filterDesc = (() => {
        let s = `${selectedYear}`
        if (selectedMonth !== "") s += ` / ${MONTH_NAMES[selectedMonth - 1]}`
        if (selectedDay !== "") s += ` / ${selectedDay}`
        const gran = selectedDay !== "" ? "hour" : selectedMonth !== "" ? "day" : "month"
        return `${s} (per ${gran})`
    })()

    // Summary aggregates
    const totalDiagnoses = monthly.reduce((s, m) => s + m.total, 0)
    const totalOk = monthly.reduce((s, m) => s + m.ok, 0)
    const totalWarning = monthly.reduce((s, m) => s + m.warning, 0)
    const totalError = monthly.reduce((s, m) => s + m.error, 0)
    const avgScore = monthly.length > 0
        ? Math.round(monthly.reduce((s, m) => s + m.score, 0) / monthly.length)
        : 0

    // Pie data
    const pieData = [
        { name: "OK", value: totalOk },
        { name: "Warning", value: totalWarning },
        { name: "Error", value: totalError },
    ].filter((d) => d.value > 0)

    // Days in selected month (for day dropdown)
    const daysInMonth = selectedMonth !== ""
        ? new Date(selectedYear, selectedMonth, 0).getDate()
        : 31

    return (
        <Card className="col-span-full">
            <CardHeader>
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Stethoscope className="h-4 w-4 text-primary" />
                            Diagnosis Analytics
                        </CardTitle>
                        <CardDescription>
                            Severity &amp; health scores — {filterDesc}
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Year */}
                        <select
                            value={selectedYear}
                            onChange={(e) => handleYearChange(Number(e.target.value))}
                            className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
                        >
                            {yearOptions.map((y) => (
                                <option key={y} value={y}>{y}</option>
                            ))}
                        </select>
                        {/* Month */}
                        <select
                            value={selectedMonth}
                            onChange={(e) => handleMonthChange(e.target.value === "" ? "" : Number(e.target.value))}
                            className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
                        >
                            <option value="">All months</option>
                            {MONTH_NAMES.map((n, i) => (
                                <option key={i} value={i + 1}>{n}</option>
                            ))}
                        </select>
                        {/* Day (only when month selected) */}
                        {selectedMonth !== "" && (
                            <select
                                value={selectedDay}
                                onChange={(e) => setSelectedDay(e.target.value === "" ? "" : Number(e.target.value))}
                                className="h-8 rounded-md border border-border bg-secondary px-2 text-xs text-foreground"
                            >
                                <option value="">All days</option>
                                {Array.from({ length: daysInMonth }, (_, i) => (
                                    <option key={i} value={i + 1}>{i + 1}</option>
                                ))}
                            </select>
                        )}
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
                ) : monthly.length === 0 && !loading ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Stethoscope className="mb-2 h-8 w-8 opacity-40" />
                        <p className="text-sm">No diagnosis data for this period</p>
                        <p className="text-xs">Run query diagnoses to see analytics here</p>
                    </div>
                ) : (
                    <>
                        {/* Severity Summary + Pie */}
                        <div className="mb-6 grid gap-4 sm:grid-cols-2">
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-lg border border-border bg-secondary/30 p-3">
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                        <TrendingUp className="h-3.5 w-3.5" /> Total Diagnoses
                                    </div>
                                    <p className="mt-1 text-2xl font-bold tabular-nums">{totalDiagnoses}</p>
                                </div>
                                <div className="rounded-lg border border-border bg-secondary/30 p-3">
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                        <ShieldCheck className="h-3.5 w-3.5" /> Avg Health Score
                                    </div>
                                    <p className={`mt-1 text-2xl font-bold tabular-nums ${avgScore >= 80 ? "text-green-400" : avgScore >= 50 ? "text-yellow-400" : "text-red-400"
                                        }`}>{avgScore}%</p>
                                </div>
                                <div className="rounded-lg border border-border bg-secondary/30 p-3">
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                        <ShieldAlert className="h-3.5 w-3.5 text-yellow-400" /> Warnings
                                    </div>
                                    <p className="mt-1 text-xl font-bold tabular-nums text-yellow-400">{totalWarning}</p>
                                </div>
                                <div className="rounded-lg border border-border bg-secondary/30 p-3">
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                        <ShieldX className="h-3.5 w-3.5 text-red-400" /> Errors
                                    </div>
                                    <p className="mt-1 text-xl font-bold tabular-nums text-red-400">{totalError}</p>
                                </div>
                            </div>

                            {pieData.length > 0 && (
                                <div className="flex flex-col items-center justify-center">
                                    <p className="mb-2 text-xs font-medium text-muted-foreground">Severity Distribution</p>
                                    <ChartContainer config={severityChartConfig} className="h-[180px] w-[180px]">
                                        <PieChart>
                                            <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={3} dataKey="value" nameKey="name" strokeWidth={0}>
                                                {pieData.map((_, idx) => (
                                                    <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <ChartTooltip content={<ChartTooltipContent />} />
                                        </PieChart>
                                    </ChartContainer>
                                    <div className="mt-1 flex gap-3 text-xs">
                                        {pieData.map((d, i) => (
                                            <span key={d.name} className="flex items-center gap-1">
                                                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: PIE_COLORS[i] }} />
                                                {d.name}: {d.value}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Stacked Bar: ok/warning/error */}
                        <div className="mb-6">
                            <p className="mb-2 text-xs font-medium text-muted-foreground">Severity Breakdown</p>
                            <ChartContainer config={severityChartConfig} className="h-[220px] w-full">
                                <BarChart data={monthly} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="bucket" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
                                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} tickMargin={4} fontSize={11} width={30} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <ChartLegend content={<ChartLegendContent />} />
                                    <Bar dataKey="ok" stackId="sev" fill="oklch(0.72 0.19 155)" radius={[0, 0, 0, 0]} />
                                    <Bar dataKey="warning" stackId="sev" fill="oklch(0.75 0.18 80)" radius={[0, 0, 0, 0]} />
                                    <Bar dataKey="error" stackId="sev" fill="oklch(0.55 0.22 27)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ChartContainer>
                        </div>

                        {/* Health Score Line Chart */}
                        <div>
                            <p className="mb-2 text-xs font-medium text-muted-foreground">Health Score Trend</p>
                            <ChartContainer config={monthlyChartConfig} className="h-[200px] w-full">
                                <LineChart data={monthly} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="bucket" tickLine={false} axisLine={false} tickMargin={8} fontSize={11} />
                                    <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tickMargin={4} fontSize={11} width={30} tickFormatter={(v: number) => `${v}%`} />
                                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => [`${value}%`, "Health Score"]} />} />
                                    <Line type="monotone" dataKey="score" stroke="var(--color-score)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--color-score)" }} activeDot={{ r: 6 }} />
                                </LineChart>
                            </ChartContainer>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    )
}
