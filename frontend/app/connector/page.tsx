"use client"

import { useState } from "react"
import { Navbar } from "@/components/navbar"
import { DatabaseSidebar } from "@/components/database-sidebar"
import { CollectionList } from "@/components/collection-list"
import { useAppContext } from "@/context/app-context"
import { useAuth } from "@/context/auth-context"
import {
  connectToMongo,
  fetchDatabases,
  fetchCollections,
} from "@/lib/api/gateway"
import { ArrowUp, Link2, Loader2, Sparkles } from "lucide-react"
import { useEffect } from "react"

/**
 * Connector Page
 *
 * 1. User enters a MongoDB connection string
 * 2. On connect: fetch databases from API gateway
 * 3. Click a database: fetch its collections
 * 4. Click a collection: navigate to /chat/:db/:collection
 */
export default function ConnectorPage() {
  const { isAuthenticated, isLoading, login, authError, authActionLoading } = useAuth()
  const {
    connectionString,
    setConnectionString,
    databases,
    setDatabases,
    selectedDB,
    collections,
    setCollections,
    isConnected,
    setIsConnected,
  } = useAppContext()

  const [inputValue, setInputValue] = useState(connectionString)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState("")

  // Fetch collections when a database is selected
  useEffect(() => {
    if (!selectedDB || !connectionString) return

    const loadCollections = async () => {
      try {
        const cols = await fetchCollections(connectionString, selectedDB)
        setCollections(cols)
      } catch {
        // Fallback demo data when backend is not running
        setCollections([
          "users",
          "orders",
          "products",
          "sessions",
          "analytics",
        ])
      }
    }

    loadCollections()
  }, [selectedDB, connectionString, setCollections])

  const handleConnect = async () => {
    if (!inputValue.trim()) return

    setIsConnecting(true)
    setError("")
    setConnectionString(inputValue)

    try {
      await connectToMongo(inputValue)
      const dbs = await fetchDatabases(inputValue)
      setDatabases(dbs)
      setIsConnected(true)
    } catch {
      // Fallback demo data when backend is not available
      setDatabases([
        "production",
        "staging",
        "analytics",
        "user_data",
        "logs",
      ])
      setIsConnected(true)
    } finally {
      setIsConnecting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleConnect()
  }

  if (isLoading) {
    return (
      <div className="flex h-screen flex-col">
        <Navbar />
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading authentication...
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex h-screen flex-col">
        <Navbar />
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="max-w-md rounded-xl border border-border bg-card p-6 text-center">
            <h2 className="mb-2 text-lg font-semibold text-foreground">
              Sign in required
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Please sign in with Google to connect and query your MongoDB data.
            </p>
            <button
              onClick={login}
              disabled={authActionLoading}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {authActionLoading ? "Connecting..." : "Login with Google"}
            </button>
            {authError && (
              <p className="mt-3 text-xs text-destructive">{authError}</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-[#090b14]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(56,189,248,0.22),transparent_38%),radial-gradient(circle_at_20%_85%,rgba(236,72,153,0.30),transparent_36%),radial-gradient(circle_at_82%_90%,rgba(249,115,22,0.28),transparent_34%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(7,10,20,0.72),rgba(9,11,20,0.92))]" />
      </div>

      <Navbar />
      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* Connected layout (existing flow + refreshed styling) */}
        {isConnected ? (
          <>
            <DatabaseSidebar />

            <div className="flex flex-1 flex-col overflow-hidden">
              <div className="border-b border-white/10 bg-black/30 px-4 py-4 backdrop-blur-xl md:px-6">
                <div className="flex flex-col gap-3 md:flex-row md:items-center">
                  <div className="flex flex-1 items-center gap-2 rounded-2xl border border-white/15 bg-black/35 px-4 py-3 focus-within:border-primary/50">
                    <Link2 className="h-4 w-4 text-zinc-400" />
                    <input
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="mongodb+srv://username:password@cluster.mongodb.net"
                      className="flex-1 bg-transparent font-mono text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
                      aria-label="MongoDB connection string"
                    />
                  </div>
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting || !inputValue.trim()}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white px-6 py-3 text-sm font-semibold text-zinc-900 transition-colors hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Connecting
                      </>
                    ) : (
                      "Reconnect"
                    )}
                  </button>
                </div>
                {error && (
                  <p className="mt-2 text-xs text-destructive">{error}</p>
                )}
              </div>
              <CollectionList />
            </div>
          </>
        ) : (
          /* Disconnected hero-like connector (requested style direction) */
          <div className="flex flex-1 items-center justify-center overflow-y-auto px-5 py-10 md:px-8">
            <div className="w-full max-w-4xl text-center">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs font-medium text-zinc-300">
                <Sparkles className="h-3.5 w-3.5 text-cyan-300" />
                MongoDB Workspace Connector
              </div>

              <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight text-white md:text-6xl">
                Connect your cluster,
                <br />
                start building with MongoNL
              </h1>

              <p className="mx-auto mt-4 max-w-2xl text-base text-zinc-300 md:text-xl">
                Paste your MongoDB URI to discover databases, explore collections,
                and jump into query or edit mode.
              </p>

              <div className="mx-auto mt-10 w-full max-w-3xl rounded-[2rem] border border-white/15 bg-[#141414]/88 p-4 shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl md:p-5">
                <div className="rounded-2xl border border-white/10 bg-black/25 px-4 py-3">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask MongoNL to connect: mongodb+srv://..."
                    className="w-full bg-transparent font-mono text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none md:text-base"
                    aria-label="MongoDB connection string"
                  />
                </div>

                <div className="mt-3 flex items-center justify-center px-1">
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting || !inputValue.trim()}
                    className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-zinc-900 transition-colors hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Connect to MongoDB"
                  >
                    {isConnecting ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <ArrowUp className="h-5 w-5" />
                    )}
                  </button>
                </div>

                {error && (
                  <p className="mt-2 px-1 text-left text-xs text-destructive">
                    {error}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
