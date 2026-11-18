import type { TraceStep } from "@/lib/sample";

const dot: Record<TraceStep["status"], string> = {
  done: "bg-fg-3",
  checked: "bg-good",
  waiting: "border border-fg-3 bg-transparent",
};

export function AgentTrace({ steps, runId, total }: { steps: TraceStep[]; runId: string; total: number }) {
  return (
    <section className="card p-5" aria-labelledby="trace-title">
      <div className="flex items-baseline justify-between">
        <h2 id="trace-title" className="font-medium text-fg">
          Agent trace
        </h2>
        <span className="num font-mono text-meta text-fg-3">{total} s</span>
      </div>
      <ol className="mt-4">
        {steps.map((s, i) => (
          <li key={`${s.agent}-${s.action}`} className="relative flex gap-3 pb-4 last:pb-0">
            {i < steps.length - 1 && <span className="absolute left-[3px] top-4 h-full w-px bg-hair2" aria-hidden />}
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${s.agent === "You" ? "bg-sky" : dot[s.status]}`}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-cap font-medium text-fg">{s.agent}</span>
                {s.seconds > 0 && <span className="num font-mono text-meta text-fg-3">{s.seconds.toFixed(1)} s</span>}
              </div>
              <p className="font-mono text-meta text-fg-2">{s.action}</p>
              <p className="text-cap text-fg-3">{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 border-t border-hair pt-3 font-mono text-meta text-fg-3">{runId}</p>
    </section>
  );
}
