"use client"

import { use } from "react"
import { Navbar } from "@/components/navbar"
import { MongoEditInterface } from "@/components/mongo-edit-interface"
import { Database, Table2, ArrowLeft, Pencil } from "lucide-react"
import Link from "next/link"

/**
 * Mongo Edit Page: /edit/:db/:collection
 *
 * Natural-language CRUD interface for modifying MongoDB documents.
 * Users describe insert / update / delete operations in plain English,
 * preview the planned mutation, and explicitly approve before committing.
 */
export default function MongoEditPage({
    params,
}: {
    params: Promise<{ db: string; collection: string }>
}) {
    const { db, collection } = use(params)

    return (
        <div className="flex h-screen flex-col">
            <Navbar />

            {/* Header: shows current db + collection + "Mongo Edit" badge */}
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
                    <span className="font-mono text-xs text-foreground">
                        {collection}
                    </span>
                </div>
                <div className="h-4 w-px bg-border" />
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                    <Pencil className="h-3 w-3" />
                    Mongo Edit
                </span>

                {/* Quick link back to read-only chat */}
                <Link
                    href={`/chat/${db}/${collection}`}
                    className="ml-auto text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                    Switch to Query Chat &rarr;
                </Link>
            </div>

            {/* Main content */}
            <div className="flex-1 overflow-hidden">
                <MongoEditInterface db={db} collection={collection} />
            </div>
        </div>
    )
}
