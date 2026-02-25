"use client"

import { use, useEffect } from "react"
import { Navbar } from "@/components/navbar"
import { ChatInterface } from "@/components/chat-interface"
import { ChatHistoryPanel } from "@/components/chat-history-panel"
import { useAppContext } from "@/context/app-context"
import { Database, Table2, ArrowLeft, Pencil } from "lucide-react"
import Link from "next/link"

/**
 * Chat Page: /chat/:db/:collection
 *
 * ChatGPT-like interface for querying a specific MongoDB collection
 * using natural language. The NLP service translates queries to
 * MongoDB operations and returns results.
 *
 * Left sidebar: Chat history panel (session list, new/rename/delete).
 * Right panel: ChatInterface (messages + input).
 */
export default function ChatPage({
  params,
}: {
  params: Promise<{ db: string; collection: string }>
}) {
  const { db, collection } = use(params)
  const { chatSessions, activeChatSessionId, createNewChat, switchChat } = useAppContext()

  // Auto-create a session when landing on the page if none exists for this db/collection
  useEffect(() => {
    const relevant = chatSessions.filter(
      (s) => s.db === db && s.collection === collection,
    )
    if (relevant.length === 0) {
      createNewChat(db, collection)
    } else {
      // If there are sessions but the active one doesn't belong to this db/collection, switch
      const activeIsRelevant = relevant.some((s) => s.id === activeChatSessionId)
      if (!activeIsRelevant) {
        switchChat(relevant[0].id)
      }
    }
  }, [db, collection]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-screen flex-col">
      <Navbar />

      {/* Chat header: shows current db + collection context */}
      <div className="flex items-center gap-3 border-b border-border bg-card px-6 py-3">
        <Link
          href="/connector"
          className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </Link>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <Database className="h-3.5 w-3.5 text-primary" />
          <span className="font-mono text-xs text-muted-foreground">{db}</span>
        </div>
        <span className="text-muted-foreground/40">/</span>
        <div className="flex items-center gap-2">
          <Table2 className="h-3.5 w-3.5 text-primary" />
          <span className="font-mono text-xs text-foreground">{collection}</span>
        </div>

        {/* Quick link to Mongo Edit */}
        <Link
          href={`/edit/${db}/${collection}`}
          className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <Pencil className="h-3 w-3" />
          Mongo Edit &rarr;
        </Link>
      </div>

      {/* Main content: Sidebar + Chat */}
      <div className="flex flex-1 overflow-hidden">
        <ChatHistoryPanel db={db} collection={collection} />
        <div className="flex-1 overflow-hidden">
          <ChatInterface db={db} collection={collection} />
        </div>
      </div>
    </div>
  )
}
