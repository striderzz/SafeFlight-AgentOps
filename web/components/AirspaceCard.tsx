import { Newspaper, ShieldAlert } from "lucide-react";
import type { AirspaceAdvisory, Itinerary } from "@/lib/sample";

const statusLabel = { avoid: "Avoid", caution: "Caution", clear: "No advisories" } as const;

export function AirspaceCard({ advisories, itineraries }: { advisories: AirspaceAdvisory[]; itineraries: Itinerary[] }) {
  const flagged = advisories.filter((a) => a.status !== "clear");
  return (
    <section className="card" aria-labelledby="airspace-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-5">
        <h2 id="airspace-title" className="font-medium text-fg">
          Airspace and world events
        </h2>
        <p className="text-meta text-fg-3">
          {flagged.length} of {itineraries.length} itineraries flagged · official bulletins decide, news adds context
        </p>
      </div>
      <ul className="mt-4 divide-y divide-hair border-t border-hair">
        {flagged.map((a) => {
          const it = itineraries.find((i) => i.id === a.itineraryId)!;
          return (
            <li key={a.itineraryId} className="grid gap-4 px-5 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="flex gap-3">
                <ShieldAlert size={18} strokeWidth={1.5} className="mt-0.5 shrink-0 text-caution" />
                <div className="min-w-0">
                  <p className="text-fg">
                    <span className="font-medium">{statusLabel[a.status]}</span>
                    <span className="text-fg-2"> · {it.legs.map((l) => l.flight).join(" + ")} · {a.zone}</span>
                  </p>
                  <p className="mt-1 text-cap text-fg-2">{a.note}</p>
                  <p className="num mt-2 font-mono text-meta text-fg-3">
                    {a.source} · valid until {a.validUntil}
                  </p>
                </div>
              </div>
              <div className="rounded-ctl border border-hair bg-ink-900 p-3">
                <p className="text-meta text-fg-3">Recent reports, context only</p>
                <ul className="mt-2 space-y-2">
                  {a.news.map((n) => (
                    <li key={n.title} className="flex gap-2 text-cap">
                      <Newspaper size={16} strokeWidth={1.5} className="mt-0.5 shrink-0 text-fg-3" />
                      <span className="min-w-0">
                        <span className="text-fg-2">{n.title}</span>
                        <span className="num block font-mono text-meta text-fg-3">
                          {n.outlet} · {n.date}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="border-t border-hair px-5 py-3 text-meta text-fg-3">
        A route is marked Avoid only when its track crosses a zone in an official bulletin. Sample zone, not real
        airspace; airlines and authorities make the actual routing decisions.
      </p>
    </section>
  );
}
