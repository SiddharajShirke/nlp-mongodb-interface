"use client"

import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { useAppContext } from "@/context/app-context"
import { Database, LogOut, LayoutDashboard } from "lucide-react"

/**
 * Navbar: Top navigation bar shown across all pages.
 * Displays logo + app name on the left, and auth controls on the right.
 */
export function Navbar() {
  const { user, isAuthenticated, isLoading, authError, authActionLoading, login, logout } = useAuth()
  const { isConnected } = useAppContext()

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-border bg-background/80 px-6 py-3 backdrop-blur-md">
      {/* Logo + Brand */}
      <Link href="/" className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Database className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="text-lg font-semibold tracking-tight text-foreground">
          MongoNL
        </span>
      </Link>

      {/* Auth Controls */}
      <nav className="flex items-center gap-4">
        {isLoading ? (
          <span className="text-sm text-muted-foreground">Loading...</span>
        ) : isAuthenticated ? (
          <>
            <Link
              href="/connector"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Connector
            </Link>
            {isConnected && (
              <Link
                href="/dashboard"
                className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <LayoutDashboard className="h-3.5 w-3.5" />
                Dashboard
              </Link>
            )}
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                {user?.avatar}
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" />
                <span className="sr-only">Sign out</span>
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-end gap-1.5">
            <button
              onClick={login}
              disabled={authActionLoading}
              className="flex items-center gap-2 rounded-lg border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-secondary/80 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
              {authActionLoading ? "Connecting..." : "Login with Google"}
            </button>
            {authError && (
              <p className="max-w-xs text-right text-xs text-destructive">{authError}</p>
            )}
          </div>
        )}
      </nav>
    </header>
  )
}
