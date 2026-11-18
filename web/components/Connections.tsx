import { ExternalLink, TriangleAlert } from "lucide-react";
import type { Carrier, SelfTransfer } from "@/lib/sample";
import { duration, price } from "@/lib/format";
import { BandTag } from "./BandTag";

export function Connections({ options, carriers }: { options: SelfTransfer[]; carriers: Record<string, Carrier> }) {
  return (
    <section className="card" aria-labelledby="connections-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-5">
        <h2 id="connections-title" className="font-medium text-fg">
          Safer connections on two tickets
        </h2>
        <p className="text-meta text-fg-3">Both legs on strong-record airlines · layover of 3 hours or more</p>
      </div>

      <ul className="mt-4 divide-y divide-hair border-t border-hair">
        {options.map((o) => {
          const total = o.legs[0].priceInr + o.legs[1].priceInr;
          return (
            <li key={o.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_200px]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="code">{o.legs[0].from}</span>
                  <span className="h-px w-6 border-t border-dashed border-hair2" aria-hidden />
                  <span className="code">{o.hub.code}</span>
                  <span className="h-px w-6 border-t border-dashed border-hair2" aria-hidden />
                  <span className="code">{o.legs[1].to}</span>
                  <span className="ml-2 text-cap text-fg-2">
                    {duration(o.layoverMin)} in {o.hub.city}
                  </span>
                </div>

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {o.legs.map((l, i) => (
                    <div key={l.flight} className="rounded-ctl border border-hair bg-ink-900 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-meta text-fg-3">Ticket {i + 1}</span>
                        <BandTag band={carriers[l.operator].band} />
                      </div>
                      <p className="mt-2 font-medium text-fg">
                        {l.flight} <span className="font-normal text-fg-3">· {carriers[l.operator].name}</span>
                      </p>
                      <p className="num mt-1 font-mono text-meta text-fg-2">
                        {l.from} {l.depart} → {l.to} {l.arrive} · {l.aircraft}
                      </p>
                      <div className="mt-3 flex items-center justify-between">
                        <span className="num text-fg">{price(l.priceInr)}</span>
                        <a
                          href="#"
                          className="inline-flex h-8 items-center gap-2 rounded-ctl border border-hair bg-ink-800 px-3 text-cap text-fg transition-colors duration-150 ease-out hover:border-hair2 hover:bg-ink-850"
                        >
                          Book {l.flight}
                          <ExternalLink size={14} strokeWidth={1.5} className="text-fg-3" />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col justify-between gap-3 lg:items-end lg:text-right">
                <div>
                  <p className="num text-figure font-medium text-fg">{price(total)}</p>
                  <p className="num mt-2 text-cap text-fg-3">
                    {duration(o.durationMin)} total · 2 tickets
                  </p>
                </div>
                <BandTag band={o.band} />
              </div>
            </li>
          );
        })}
      </ul>

      <div className="flex gap-2 border-t border-hair px-5 py-4 text-cap text-fg-2">
        <TriangleAlert size={16} strokeWidth={1.5} className="mt-0.5 shrink-0 text-caution" />
        <p>
          Separate tickets: if the first flight is late, the second airline does not have to rebook you. You also
          collect and re-check bags at the hub, and transit visa rules may apply. Booking opens each airline&apos;s own
          site; SafeFlight never takes payment.
        </p>
      </div>
    </section>
  );
}
