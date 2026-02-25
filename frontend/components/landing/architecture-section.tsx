import { ArrowRight } from "lucide-react"

const steps = [
  {
    label: "Access",
    tech: "NextAuth + Connector",
    description:
      "Login with Google, connect MongoDB URI, pick database and collection",
  },
  {
    label: "Query",
    tech: "Chat + Diagnose",
    description:
      "Ask in plain English, view tabular results, and inspect full pipeline trace",
  },
  {
    label: "Edit",
    tech: "Preview -> Add -> Commit",
    description:
      "Generate CRUD mutation plans (manual or NL), estimate impact, then commit",
  },
  {
    label: "Observe",
    tech: "Dashboard Analytics",
    description:
      "Monitor commits, activity breakdown, diagnosis severity, and health scores",
  },
]

/**
 * ArchitectureSection: Visual breakdown of the system architecture.
 * Shows the data flow from frontend to database.
 */
export function ArchitectureSection() {
  return (
    <section
      id="architecture"
      className="border-t border-border px-6 py-20"
    >
      <div className="mx-auto max-w-4xl">
        <div className="mb-12 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            Product workflow
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            The same path your team follows: connect, query, safely edit, then track.
          </p>
        </div>

        {/* Architecture flow */}
        <div className="flex flex-col items-center gap-3 md:flex-row md:justify-center">
          {steps.map((step, i) => (
            <div key={step.label} className="flex items-center gap-3">
              <div className="w-52 rounded-xl border border-border bg-card p-4 text-center">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-primary">
                  {step.label}
                </div>
                <div className="mb-2 font-mono text-[11px] text-muted-foreground">
                  {step.tech}
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground/80">
                  {step.description}
                </p>
              </div>
              {i < steps.length - 1 && (
                <ArrowRight className="hidden h-4 w-4 text-muted-foreground/40 md:block" />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
