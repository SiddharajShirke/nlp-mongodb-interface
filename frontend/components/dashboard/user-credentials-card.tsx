"use client"

import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database, Mail, User, Globe } from "lucide-react"

export function UserCredentialsCard() {
    const { user } = useAuth()
    const { connectionString, selectedDB, databases } = useAppContext()

    // Mask the connection string for display
    const maskedUri = connectionString
        ? connectionString.replace(/:([^@/:]+)@/, ":****@")
        : "Not connected"

    return (
        <Card className="col-span-full">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                    <User className="h-5 w-5 text-primary" />
                    User Profile
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {/* Name */}
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 px-4 py-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                            {user?.avatar ?? "U"}
                        </div>
                        <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">Name</p>
                            <p className="truncate text-sm font-medium">{user?.name ?? "Anonymous"}</p>
                        </div>
                    </div>

                    {/* Email */}
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 px-4 py-3">
                        <Mail className="h-5 w-5 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">Email</p>
                            <p className="truncate text-sm font-medium">{user?.email ?? "—"}</p>
                        </div>
                    </div>

                    {/* Current Database */}
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 px-4 py-3">
                        <Database className="h-5 w-5 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">Active Database</p>
                            <p className="truncate text-sm font-medium">{selectedDB ?? "None selected"}</p>
                        </div>
                    </div>

                    {/* Connection */}
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 px-4 py-3">
                        <Globe className="h-5 w-5 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">Cluster</p>
                            <p className="truncate text-sm font-mono text-xs">{maskedUri}</p>
                        </div>
                    </div>
                </div>

                {/* Database list badge strip */}
                {databases.length > 0 && (
                    <div className="mt-4">
                        <p className="mb-2 text-xs text-muted-foreground">Available Databases ({databases.length})</p>
                        <div className="flex flex-wrap gap-1.5">
                            {databases.map((db) => (
                                <span
                                    key={db}
                                    className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${db === selectedDB
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-secondary text-secondary-foreground"
                                        }`}
                                >
                                    {db}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
