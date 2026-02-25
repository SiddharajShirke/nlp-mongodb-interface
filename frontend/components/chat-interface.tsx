"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2, Sparkles, Search, Trash2 } from "lucide-react"
import { useAppContext } from "@/context/app-context"
import { useAuth } from "@/context/auth-context"
import { MessageBubble } from "@/components/message-bubble"
import { sendQuery, diagnoseQuery, clearCache } from "@/lib/api/gateway"

/**
 * ChatInterface: The main chat panel for querying MongoDB collections.
 * Displays message history and an input box at the bottom.
 *
 * Data flow: User input -> sendQuery(gateway) -> API Gateway -> NLP -> MongoDB -> response
 */
export function ChatInterface({
  db,
  collection,
}: {
  db: string
  collection: string
}) {
  const { chatMessages, addChatMessage, connectionString } = useAppContext()
  const { user } = useAuth()
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isDiagnosing, setIsDiagnosing] = useState(false)
  const [isClearingCache, setIsClearingCache] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatMessages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    // Build history from existing chat messages
    const history = chatMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    // Add user message
    addChatMessage({
      id: `msg-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    })
    setInput("")
    setIsLoading(true)

    try {
      // Send to API gateway -> NLP service -> MongoDB
      const result = await sendQuery({
        mongoUri: connectionString,
        db,
        collection,
        query: trimmed,
        history,
        userEmail: user?.email,
      })
      addChatMessage({
        id: `msg-${Date.now()}-res`,
        role: "assistant",
        content:
          result.interpretation ||
          (typeof result.result === "number"
            ? `Result: ${result.result}`
            : JSON.stringify(result, null, 2)),
        timestamp: new Date(),
        queryResult: {
          data: result.data,
          result: result.result,
          result_count: result.result_count,
          total_results: result.total_results,
          page: result.page,
          page_size: result.page_size,
          warning: result.warning,
          value_hint: result.value_hint,
        },
      })
    } catch {
      // Simulated fallback for demo when backend is not available
      addChatMessage({
        id: `msg-${Date.now()}-res`,
        role: "assistant",
        content: `Processed query on ${db}.${collection}: "${trimmed}"\n\nResult:\n${JSON.stringify(
          {
            matched: Math.floor(Math.random() * 100),
            documents: [
              { _id: "64a7f2...", status: "active", created: "2025-01-15" },
              { _id: "64a7f3...", status: "pending", created: "2025-02-20" },
            ],
          },
          null,
          2
        )}`,
        timestamp: new Date(),
        queryResult: {
          data: [
            { _id: "64a7f2...", status: "active", created: "2025-01-15" },
            { _id: "64a7f3...", status: "pending", created: "2025-02-20" },
          ],
          total_results: 2,
          result_count: 2,
          page: 1,
          page_size: 20,
        },
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleDiagnose = async () => {
    const trimmed = input.trim()
    if (!trimmed || isDiagnosing) return

    // Build history from existing chat messages
    const history = chatMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    setIsDiagnosing(true)
    try {
      const result = await diagnoseQuery({
        mongoUri: connectionString,
        db,
        collection,
        query: trimmed,
        history,
        userEmail: user?.email,
      })

      const steps = result.steps || {}
      const parseStep = steps["2_parse"]
      const executeStep = steps["6_execute_preview"]

      const summaryParts: string[] = [`Diagnosis for: "${trimmed}"`]
      if (parseStep?.parser) summaryParts.push(`Parser: ${parseStep.parser}`)
      if (parseStep?.raw_ir?.operation) summaryParts.push(`Operation: ${parseStep.raw_ir.operation}`)
      if (typeof executeStep?.total_count === "number")
        summaryParts.push(`Matched: ${executeStep.total_count} documents`)

      addChatMessage({
        id: `msg-${Date.now()}-diag`,
        role: "assistant",
        content: summaryParts.join(" | "),
        timestamp: new Date(),
        diagnoseResult: {
          query: trimmed,
          steps,
        },
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Diagnosis failed"
      addChatMessage({
        id: `msg-${Date.now()}-diag-err`,
        role: "assistant",
        content: `Diagnosis failed: ${message}`,
        timestamp: new Date(),
      })
    } finally {
      setIsDiagnosing(false)
    }
  }

  const handleClearCache = async () => {
    if (isClearingCache) return
    setIsClearingCache(true)
    try {
      const result = await clearCache()
      addChatMessage({
        id: `msg-${Date.now()}-cache`,
        role: "assistant",
        content: result.message || "Schema cache cleared. Next query will use a fresh schema sample.",
        timestamp: new Date(),
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to clear cache"
      addChatMessage({
        id: `msg-${Date.now()}-cache-err`,
        role: "assistant",
        content: `Cache clear failed: ${message}`,
        timestamp: new Date(),
      })
    } finally {
      setIsClearingCache(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {chatMessages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <Sparkles className="mx-auto mb-4 h-10 w-10 text-primary/40" />
              <h3 className="mb-2 text-lg font-medium text-foreground">
                Query {collection} with natural language
              </h3>
              <p className="mx-auto max-w-sm text-sm leading-relaxed text-muted-foreground">
                Ask questions about your data in plain English. The NLP engine
                will translate your query into MongoDB operations.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  "Show all active users",
                  "Count documents created this month",
                  "Find records where status is pending",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="rounded-lg border border-border bg-card px-3 py-1.5 font-mono text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {chatMessages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                  <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" />
                </div>
                <div className="rounded-xl border border-border bg-card px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"
                      style={{ animationDelay: "300ms" }}
                    />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-background p-4">
        <div className="mx-auto mb-2 flex max-w-3xl items-center gap-2">
          <button
            onClick={handleDiagnose}
            disabled={!input.trim() || isLoading || isDiagnosing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs text-card-foreground transition-colors hover:bg-card/80 disabled:cursor-not-allowed disabled:opacity-40"
            title="Run full pipeline diagnosis for current query"
          >
            {isDiagnosing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            Diagnose
          </button>
          <button
            onClick={handleClearCache}
            disabled={isClearingCache}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs text-card-foreground transition-colors hover:bg-card/80 disabled:cursor-not-allowed disabled:opacity-40"
            title="Clear schema cache on backend"
          >
            {isClearingCache ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Clear Cache
          </button>
        </div>
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="flex flex-1 items-center rounded-xl border border-border bg-input px-4 py-2.5 focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-ring/30">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask about ${collection}...`}
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              disabled={isLoading}
              aria-label="Chat message input"
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
