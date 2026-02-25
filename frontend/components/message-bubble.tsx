import { Bot, User } from "lucide-react"
import type { ChatMessage } from "@/context/app-context"
import { DiagnoseTrace } from "@/components/diagnose-trace"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * MessageBubble: Renders a single message in the chat.
 * User messages appear on the right, assistant messages on the left.
 * Query results from the assistant use monospace font.
 */
export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"
  const rows = message.queryResult?.data || []
  const columns = rows.length
    ? Array.from(new Set(rows.flatMap((row) => Object.keys(row))))
    : []

  const formatCellValue = (value: unknown) => {
    if (value === null || value === undefined) return "-"
    if (typeof value === "object") return JSON.stringify(value)
    return String(value)
  }

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${isUser ? "bg-secondary" : "bg-primary"
          }`}
      >
        {isUser ? (
          <User className="h-4 w-4 text-secondary-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary-foreground" />
        )}
      </div>

      {/* Message Content */}
      <div
        className={`${message.diagnoseResult ? "max-w-[90%]" : "max-w-[75%]"
          } rounded-xl px-4 py-3 ${isUser
            ? "bg-secondary text-secondary-foreground"
            : "border border-border bg-card text-card-foreground"
          }`}
      >
        {/* Detect if content looks like JSON / query result and use mono font */}
        <p
          className={`text-sm leading-relaxed ${!isUser && (message.content.startsWith("{") || message.content.startsWith("["))
              ? "font-mono text-xs"
              : ""
            } whitespace-pre-wrap break-words`}
        >
          {message.content}
        </p>
        {!isUser && message.diagnoseResult && (
          <DiagnoseTrace
            query={message.diagnoseResult.query}
            steps={message.diagnoseResult.steps}
          />
        )}
        {!isUser && message.queryResult && (
          <div className="mt-3 space-y-2">
            {typeof message.queryResult.total_results === "number" && (
              <p className="text-xs text-muted-foreground">
                {typeof message.queryResult.result_count === "number"
                  ? `Showing ${message.queryResult.result_count} of ${message.queryResult.total_results} rows`
                  : `${message.queryResult.total_results} rows matched`}
              </p>
            )}
            {message.queryResult.warning && (
              <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-300">
                {message.queryResult.warning}
              </p>
            )}
            {rows.length > 0 && columns.length > 0 && (
              <div className="rounded-lg border border-border bg-background/60 p-2">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {columns.map((column) => (
                        <TableHead key={column}>{column}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row, rowIndex) => (
                      <TableRow key={`${message.id}-${rowIndex}`}>
                        {columns.map((column) => (
                          <TableCell key={`${message.id}-${rowIndex}-${column}`}>
                            <span className="font-mono text-xs">
                              {formatCellValue(row[column])}
                            </span>
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
            {!rows.length && message.queryResult.value_hint && (
              <p className="text-xs text-muted-foreground">
                Hint: {message.queryResult.value_hint}
              </p>
            )}
          </div>
        )}
        <time className="mt-1.5 block text-[10px] text-muted-foreground">
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
      </div>
    </div>
  )
}
