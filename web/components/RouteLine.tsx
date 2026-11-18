import { Plane } from "lucide-react";

// Signature detail: the route as two departure-board codes joined by a dashed track.
export function RouteLine({ from, to, size = "md" }: { from: string; to: string; size?: "sm" | "md" }) {
  const width = size === "md" ? "w-24" : "w-10";
  return (
    <span className="inline-flex items-center gap-2" aria-label={`${from} to ${to}`}>
      <span className="code">{from}</span>
      <span className={`relative flex ${width} items-center`} aria-hidden>
        <span className="h-px w-full border-t border-dashed border-hair2" />
        {size === "md" && (
          <Plane size={14} strokeWidth={1.5} className="absolute left-1/2 -translate-x-1/2 rotate-45 bg-ink-900 text-fg-3" />
        )}
      </span>
      <span className="code">{to}</span>
    </span>
  );
}
