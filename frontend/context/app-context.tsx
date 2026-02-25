"use client"

import { createContext, useContext, useState, useCallback, type ReactNode } from "react"
import type { DiagnoseSteps } from "@/lib/api/gateway"

/** A single chat message between user and assistant */
export interface QueryResultSnapshot {
  data?: Record<string, unknown>[]
  result?: number
  result_count?: number
  total_results?: number
  page?: number
  page_size?: number
  warning?: string
  value_hint?: string
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  queryResult?: QueryResultSnapshot
  diagnoseResult?: {
    query: string
    steps: DiagnoseSteps
  }
}

/** A chat session — one conversation thread */
export interface ChatSession {
  id: string
  title: string
  db: string
  collection: string
  messages: ChatMessage[]
  createdAt: Date
  updatedAt: Date
}

interface AppContextType {
  connectionString: string
  setConnectionString: (s: string) => void
  selectedDB: string | null
  setSelectedDB: (db: string | null) => void
  selectedCollection: string | null
  setSelectedCollection: (col: string | null) => void
  databases: string[]
  setDatabases: (dbs: string[]) => void
  collections: string[]
  setCollections: (cols: string[]) => void
  isConnected: boolean
  setIsConnected: (v: boolean) => void

  // ---- Chat session management (ChatGPT-style) ----
  chatSessions: ChatSession[]
  activeChatSessionId: string | null
  /** Messages for the currently active session */
  chatMessages: ChatMessage[]
  /** Create a new session and make it active; returns the new session id */
  createNewChat: (db: string, collection: string) => string
  /** Switch to an existing session */
  switchChat: (sessionId: string) => void
  /** Delete a session (switches to another or creates a new one) */
  deleteChat: (sessionId: string, db: string, collection: string) => void
  /** Rename a session */
  renameChat: (sessionId: string, title: string) => void
  /** Add a message to the active session */
  addChatMessage: (msg: ChatMessage) => void
  /** Clear all messages in the active session */
  clearChat: () => void
}

const AppContext = createContext<AppContextType | undefined>(undefined)

function generateSessionId() {
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * AppProvider manages the core application state:
 * - MongoDB connection info
 * - Database & collection selection
 * - Multi-session chat history (ChatGPT-style)
 */
export function AppProvider({ children }: { children: ReactNode }) {
  const [connectionString, setConnectionString] = useState("")
  const [selectedDB, setSelectedDB] = useState<string | null>(null)
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null)
  const [databases, setDatabases] = useState<string[]>([])
  const [collections, setCollections] = useState<string[]>([])
  const [isConnected, setIsConnected] = useState(false)

  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(null)

  // Derive active session's messages
  const activeSession = chatSessions.find((s) => s.id === activeChatSessionId)
  const chatMessages = activeSession?.messages ?? []

  const createNewChat = useCallback(
    (db: string, collection: string) => {
      const id = generateSessionId()
      const now = new Date()
      const session: ChatSession = {
        id,
        title: "New Chat",
        db,
        collection,
        messages: [],
        createdAt: now,
        updatedAt: now,
      }
      setChatSessions((prev) => [session, ...prev])
      setActiveChatSessionId(id)
      return id
    },
    [],
  )

  const switchChat = useCallback((sessionId: string) => {
    setActiveChatSessionId(sessionId)
  }, [])

  const deleteChat = useCallback(
    (sessionId: string, db: string, collection: string) => {
      setChatSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== sessionId)
        if (filtered.length === 0) {
          // Create a fresh session when all are deleted
          const id = generateSessionId()
          const now = new Date()
          const fresh: ChatSession = {
            id,
            title: "New Chat",
            db,
            collection,
            messages: [],
            createdAt: now,
            updatedAt: now,
          }
          setActiveChatSessionId(id)
          return [fresh]
        }
        // If we deleted the active session, switch to the first remaining
        setActiveChatSessionId((currentId) =>
          currentId === sessionId ? filtered[0].id : currentId,
        )
        return filtered
      })
    },
    [],
  )

  const renameChat = useCallback((sessionId: string, title: string) => {
    setChatSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, title } : s)),
    )
  }, [])

  const addChatMessage = useCallback(
    (msg: ChatMessage) => {
      setChatSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeChatSessionId) return s
          const updated = {
            ...s,
            messages: [...s.messages, msg],
            updatedAt: new Date(),
          }
          // Auto-title from the first user message
          if (
            updated.title === "New Chat" &&
            msg.role === "user" &&
            s.messages.length === 0
          ) {
            updated.title =
              msg.content.length > 40
                ? msg.content.slice(0, 40) + "…"
                : msg.content
          }
          return updated
        }),
      )
    },
    [activeChatSessionId],
  )

  const clearChat = useCallback(() => {
    setChatSessions((prev) =>
      prev.map((s) =>
        s.id === activeChatSessionId
          ? { ...s, messages: [], updatedAt: new Date() }
          : s,
      ),
    )
  }, [activeChatSessionId])

  return (
    <AppContext.Provider
      value={{
        connectionString,
        setConnectionString,
        selectedDB,
        setSelectedDB,
        selectedCollection,
        setSelectedCollection,
        databases,
        setDatabases,
        collections,
        setCollections,
        isConnected,
        setIsConnected,
        chatSessions,
        activeChatSessionId,
        chatMessages,
        createNewChat,
        switchChat,
        deleteChat,
        renameChat,
        addChatMessage,
        clearChat,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useAppContext() {
  const context = useContext(AppContext)
  if (!context) throw new Error("useAppContext must be used within AppProvider")
  return context
}
