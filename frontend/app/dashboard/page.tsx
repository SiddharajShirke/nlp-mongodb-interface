"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { UserCredentialsCard } from "@/components/dashboard/user-credentials-card"
import { CommitTrackingChart } from "@/components/dashboard/commit-tracking-chart"
import { ActivityOverviewChart } from "@/components/dashboard/activity-overview-chart"
import { DiagnosisAnalyticsChart } from "@/components/dashboard/diagnosis-analytics-chart"
import { Loader2, LayoutDashboard } from "lucide-react"

export default function DashboardPage() {
    const router = useRouter()
    const { isAuthenticated, isLoading: authLoading } = useAuth()
    const { isConnected, selectedDB } = useAppContext()

    // Redirect if not authenticated or not connected
    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.replace("/")
        } else if (!authLoading && isAuthenticated && !isConnected) {
            router.replace("/connector")
        }
    }, [authLoading, isAuthenticated, isConnected, router])

    if (authLoading) {
        return (
            <div className="flex min-h-screen flex-col">
                <Navbar />
                <main className="flex flex-1 items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </main>
            </div>
        )
    }

    if (!isAuthenticated || !isConnected) {
        return null // Will redirect
    }

    return (
        <div className="flex min-h-screen flex-col">
            <Navbar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
                    {/* Header */}
                    <div className="mb-6 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
                            <LayoutDashboard className="h-5 w-5 text-primary-foreground" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
                            <p className="text-sm text-muted-foreground">
                                Analytics &amp; activity tracking for{" "}
                                <span className="font-medium text-foreground">{selectedDB ?? "your database"}</span>
                            </p>
                        </div>
                    </div>

                    {/* Dashboard Grid */}
                    <div className="grid gap-6">
                        {/* Row 1: User Credentials (full width) */}
                        <UserCredentialsCard />

                        {/* Row 2: Activity Overview + Commit Tracking side by side */}
                        <div className="grid gap-6 lg:grid-cols-2">
                            <ActivityOverviewChart />
                            <CommitTrackingChart />
                        </div>

                        {/* Row 3: Diagnosis Analytics (full width) */}
                        <DiagnosisAnalyticsChart />
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    )
}
