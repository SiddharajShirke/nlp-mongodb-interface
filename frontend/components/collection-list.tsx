"use client"

import Link from "next/link"
import { Table2, ArrowRight, MessageSquare, Pencil } from "lucide-react"
import { useAppContext } from "@/context/app-context"

/**
 * CollectionList: Displays collections for the selected database.
 * Each collection shows two action links:
 *   - Query Chat  → /chat/:db/:col  (read-only NLP queries)
 *   - Mongo Edit  → /edit/:db/:col  (CRUD mutations with approval)
 */
export function CollectionList() {
  const { collections, selectedDB, selectedCollection, setSelectedCollection } =
    useAppContext()

  if (!selectedDB) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <Table2 className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            Select a database to view its collections.
          </p>
        </div>
      </div>
    )
  }

  if (collections.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <Table2 className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No collections found in{" "}
            <span className="font-mono text-foreground">{selectedDB}</span>.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">{selectedDB}</h2>
        <p className="text-sm text-muted-foreground">
          {collections.length} collection{collections.length !== 1 ? "s" : ""} found
        </p>
      </div>
      <div className="grid gap-2">
        {collections.map((col) => (
          <div
            key={col}
            className="group flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-card/80"
          >
            <div className="flex items-center gap-3">
              <Table2 className="h-4 w-4 text-primary" />
              <span className="font-mono text-sm text-card-foreground">{col}</span>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href={`/chat/${selectedDB}/${col}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Query
              </Link>
              <Link
                href={`/edit/${selectedDB}/${col}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-600 transition-colors hover:bg-amber-500/20 dark:text-amber-400"
              >
                <Pencil className="h-3.5 w-3.5" />
                Mongo Edit
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
