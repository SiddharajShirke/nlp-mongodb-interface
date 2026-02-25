import {
  Activity,
  Database,
  MessageSquare,
  ShieldCheck,
  Stethoscope,
  WandSparkles,
} from "lucide-react"

const features = [
  {
    icon: Database,
    title: "Authenticated Cluster Connector",
    description:
      "Sign in with Google, connect with your MongoDB URI, and browse databases and collections before jumping into query or edit mode.",
  },
  {
    icon: MessageSquare,
    title: "Session-Based Query Chat",
    description:
      "Run natural-language queries with multi-chat history per collection, searchable sessions, tabular result rendering, pagination metadata, and value hints.",
  },
  {
    icon: Stethoscope,
    title: "Deep Pipeline Diagnostics",
    description:
      "Inspect every diagnosis stage: raw sample, schema detection, NL parse, field resolution, validation, MongoDB compilation, execution preview, and index analysis.",
  },
  {
    icon: WandSparkles,
    title: "Mongo Edit with Approval Workflow",
    description:
      "Use Manual Change or Query Dynamic Change, preview mutations, estimate affected documents, then explicitly Add and Commit changes to MongoDB.",
  },
  {
    icon: ShieldCheck,
    title: "Safety + Performance Signals",
    description:
      "Get non-blocking warnings for unindexed queried fields, zero-result value hints, schema cache controls, and parser fallback support.",
  },
  {
    icon: Activity,
    title: "Operational Analytics Dashboard",
    description:
      "Track query, diagnose, and commit activity with time filters, commit timeline, diagnosis severity trends, health scores, and top collections.",
  },
]

/**
 * FeaturesSection: Grid of product features with icons and descriptions.
 */
export function FeaturesSection() {
  return (
    <section className="border-t border-border px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            Built for day-to-day MongoDB operations
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            From connection and investigation to controlled writes and analytics.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-border bg-card p-6"
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <feature.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="mb-2 text-sm font-semibold text-card-foreground">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
