"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import {
    Plus,
    MessageSquare,
    Trash2,
    Pencil,
    Check,
    X,
    PanelLeftClose,
    PanelLeft,
    MoreHorizontal,
    Search,
} from "lucide-react"
import { useAppContext, type ChatSession } from "@/context/app-context"

/* ------------------------------------------------------------------ */
/*  Time-based grouping (Today / Yesterday / Previous 7 days / older) */
/* ------------------------------------------------------------------ */

type TimeGroup =
    | "Today"
    | "Yesterday"
    | "Previous 7 Days"
    | "Previous 30 Days"
    | "Older"

function getTimeGroup(date: Date): TimeGroup {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = diffMs / (1000 * 60 * 60 * 24)

    if (diffDays < 1 && now.getDate() === date.getDate()) return "Today"
    if (diffDays < 2) return "Yesterday"
    if (diffDays < 7) return "Previous 7 Days"
    if (diffDays < 30) return "Previous 30 Days"
    return "Older"
}

function groupSessions(sessions: ChatSession[]): Map<TimeGroup, ChatSession[]> {
    const order: TimeGroup[] = [
        "Today",
        "Yesterday",
        "Previous 7 Days",
        "Previous 30 Days",
        "Older",
    ]
    const groups = new Map<TimeGroup, ChatSession[]>()
    for (const g of order) groups.set(g, [])

    for (const s of sessions) {
        const group = getTimeGroup(s.updatedAt)
        groups.get(group)!.push(s)
    }
    // Remove empty groups
    for (const g of order) {
        if (groups.get(g)!.length === 0) groups.delete(g)
    }
    return groups
}

/* ------------------------------------------------------------------ */
/*  Single session row                                                 */
/* ------------------------------------------------------------------ */

function SessionRow({
    session,
    isActive,
    onSwitch,
    onDelete,
    onRename,
}: {
    session: ChatSession
    isActive: boolean
    onSwitch: () => void
    onDelete: () => void
    onRename: (title: string) => void
}) {
    const [isEditing, setIsEditing] = useState(false)
    const [editValue, setEditValue] = useState(session.title)
    const [showActions, setShowActions] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        if (isEditing) inputRef.current?.focus()
    }, [isEditing])

    const handleConfirmRename = () => {
        const trimmed = editValue.trim()
        if (trimmed && trimmed !== session.title) {
            onRename(trimmed)
        }
        setIsEditing(false)
    }

    const handleCancelRename = () => {
        setEditValue(session.title)
        setIsEditing(false)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") handleConfirmRename()
        if (e.key === "Escape") handleCancelRename()
    }

    return (
        <div
            className={`group relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer ${isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                }`}
            onClick={() => {
                if (!isEditing) onSwitch()
            }}
            onMouseEnter={() => setShowActions(true)}
            onMouseLeave={() => {
                if (!isEditing) setShowActions(false)
            }}
        >
            <MessageSquare className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />

            {isEditing ? (
                <div className="flex flex-1 items-center gap-1">
                    <input
                        ref={inputRef}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="flex-1 rounded border border-primary/40 bg-background px-1.5 py-0.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-primary/50"
                        onClick={(e) => e.stopPropagation()}
                    />
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            handleConfirmRename()
                        }}
                        className="rounded p-0.5 hover:bg-primary/20"
                        title="Confirm"
                    >
                        <Check className="h-3 w-3 text-green-400" />
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            handleCancelRename()
                        }}
                        className="rounded p-0.5 hover:bg-primary/20"
                        title="Cancel"
                    >
                        <X className="h-3 w-3 text-red-400" />
                    </button>
                </div>
            ) : (
                <>
                    <span className="flex-1 truncate text-xs">{session.title}</span>

                    {/* Hover actions — fade gradient + action icons, like ChatGPT */}
                    {showActions && (
                        <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                            {/* Gradient fade on the right edge */}
                            <div
                                className={`h-full w-6 ${isActive
                                        ? "bg-gradient-to-l from-sidebar-accent"
                                        : "bg-gradient-to-l from-sidebar"
                                    }`}
                            />
                            <button
                                onClick={(e) => {
                                    e.stopPropagation()
                                    setEditValue(session.title)
                                    setIsEditing(true)
                                }}
                                className={`rounded p-1 transition-colors ${isActive
                                        ? "hover:bg-sidebar-accent-foreground/10"
                                        : "hover:bg-sidebar-accent/70"
                                    }`}
                                title="Rename"
                            >
                                <Pencil className="h-3 w-3" />
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation()
                                    onDelete()
                                }}
                                className={`rounded p-1 transition-colors ${isActive
                                        ? "hover:bg-red-500/20 text-red-400"
                                        : "hover:bg-red-500/20 text-red-400"
                                    }`}
                                title="Delete"
                            >
                                <Trash2 className="h-3 w-3" />
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}

/* ------------------------------------------------------------------ */
/*  Main Chat History Panel                                            */
/* ------------------------------------------------------------------ */

export function ChatHistoryPanel({
    db,
    collection,
}: {
    db: string
    collection: string
}) {
    const {
        chatSessions,
        activeChatSessionId,
        createNewChat,
        switchChat,
        deleteChat,
        renameChat,
    } = useAppContext()

    const [collapsed, setCollapsed] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")

    // Filter sessions to current db/collection
    const relevantSessions = chatSessions.filter(
        (s) => s.db === db && s.collection === collection,
    )

    // Apply search filter
    const filteredSessions = searchQuery.trim()
        ? relevantSessions.filter((s) =>
            s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.messages.some((m) =>
                m.content.toLowerCase().includes(searchQuery.toLowerCase()),
            ),
        )
        : relevantSessions

    const grouped = groupSessions(filteredSessions)

    const handleNewChat = () => {
        createNewChat(db, collection)
    }

    // Collapsed state: show a thin strip with toggle button
    if (collapsed) {
        return (
            <aside className="flex w-12 flex-shrink-0 flex-col items-center border-r border-border bg-sidebar py-3 gap-3">
                <button
                    onClick={() => setCollapsed(false)}
                    className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
                    title="Expand sidebar"
                >
                    <PanelLeft className="h-4 w-4" />
                </button>
                <button
                    onClick={handleNewChat}
                    className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
                    title="New chat"
                >
                    <Plus className="h-4 w-4" />
                </button>
            </aside>
        )
    }

    return (
        <aside className="flex w-64 flex-shrink-0 flex-col border-r border-border bg-sidebar">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-sidebar-border px-3 py-3">
                <button
                    onClick={handleNewChat}
                    className="inline-flex flex-1 items-center gap-2 rounded-lg border border-sidebar-border px-3 py-2 text-xs font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
                    title="New chat"
                >
                    <Plus className="h-3.5 w-3.5" />
                    New Chat
                </button>
                <button
                    onClick={() => setCollapsed(true)}
                    className="ml-2 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
                    title="Collapse sidebar"
                >
                    <PanelLeftClose className="h-4 w-4" />
                </button>
            </div>

            {/* Search */}
            <div className="px-3 py-2">
                <div className="flex items-center gap-2 rounded-md border border-sidebar-border bg-background/50 px-2 py-1.5">
                    <Search className="h-3 w-3 text-muted-foreground" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search chats…"
                        className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground outline-none"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="text-muted-foreground hover:text-foreground"
                        >
                            <X className="h-3 w-3" />
                        </button>
                    )}
                </div>
            </div>

            {/* Sessions List */}
            <nav
                className="flex-1 overflow-y-auto px-2 pb-3"
                aria-label="Chat history"
            >
                {filteredSessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                        <MessageSquare className="mb-2 h-8 w-8 text-muted-foreground/30" />
                        <p className="text-xs text-muted-foreground">
                            {searchQuery
                                ? "No chats match your search."
                                : "No conversations yet. Start a new chat!"}
                        </p>
                    </div>
                ) : (
                    Array.from(grouped.entries()).map(([group, sessions]) => (
                        <div key={group} className="mb-2">
                            <h3 className="mb-1 px-3 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                {group}
                            </h3>
                            {sessions.map((session) => (
                                <SessionRow
                                    key={session.id}
                                    session={session}
                                    isActive={session.id === activeChatSessionId}
                                    onSwitch={() => switchChat(session.id)}
                                    onDelete={() => deleteChat(session.id, db, collection)}
                                    onRename={(title) => renameChat(session.id, title)}
                                />
                            ))}
                        </div>
                    ))
                )}
            </nav>

            {/* Footer: session count */}
            <div className="border-t border-sidebar-border px-3 py-2">
                <p className="text-[10px] text-muted-foreground">
                    {relevantSessions.length} chat{relevantSessions.length !== 1 ? "s" : ""} •{" "}
                    <span className="font-mono">{collection}</span>
                </p>
            </div>
        </aside>
    )
}
