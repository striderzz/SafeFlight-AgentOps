"use client";

import { useCallback, useMemo, useState } from "react";
import { AdvisorCard } from "@/components/AdvisorCard";
import { AgentTrace } from "@/components/AgentTrace";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { Header } from "@/components/Header";
import { IntervalChart } from "@/components/IntervalChart";
import { ItineraryTable } from "@/components/ItineraryTable";
import { RouteLine } from "@/components/RouteLine";
import { SearchBar } from "@/components/SearchBar";
import { longDate } from "@/lib/format";
import { AirspaceCard } from "@/components/AirspaceCard";
import { Connections } from "@/components/Connections";
import { advice, airspace, carriers, itineraries, records, run, selfTransfers, trace } from "@/lib/sample";

export default function Page() {
  const [selectedItinerary, setSelectedItinerary] = useState<string | null>(null);
  const [drawerCarrier, setDrawerCarrier] = useState<string | null>(null);

  const chartCarriers = useMemo(() => {
    const order: string[] = [];
    for (const it of itineraries) for (const l of it.legs) if (!order.includes(l.operator)) order.push(l.operator);
    return order.map((c) => carriers[c]).sort((a, b) => a.ratePerM - b.ratePerM);
  }, []);

  const pickCarrier = itineraries.find((i) => i.id === advice.pick)!.rankedFor;
  const close = useCallback(() => setDrawerCarrier(null), []);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-[1440px] px-6 pb-16 pt-8 lg:px-8">
        <SearchBar from={run.from.code} to={run.to.code} date={run.date} />

        <div className="mt-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-4">
              <RouteLine from={run.from.code} to={run.to.code} />
            </div>
            <h1 className="mt-4 text-title font-medium tracking-[-0.01em] text-fg">
              {run.from.city} to {run.to.city}
            </h1>
            <p className="mt-1 text-cap text-fg-2">
              {longDate(run.date)} · {itineraries.length} itineraries · {chartCarriers.length} operating airlines
            </p>
          </div>
          <p className="num font-mono text-meta text-fg-3">
            Safety window {run.window} · finished in {run.finishedIn} s
          </p>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="enter min-w-0 space-y-6">
            <section className="card p-5" aria-labelledby="chart-title">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="chart-title" className="font-medium text-fg">
                  Accidents per million departures
                </h2>
                <p className="text-meta text-fg-3">Dot is the estimate, line is the 90% interval, dashed means limited data</p>
              </div>
              <div className="-mx-5 mt-4 overflow-x-auto px-5">
                <div className="min-w-[620px]">
                <IntervalChart
                  carriers={chartCarriers}
                  industry={run.industryRatePerM}
                  highlight={pickCarrier}
                  selected={drawerCarrier}
                  onSelect={setDrawerCarrier}
                />
                </div>
              </div>
            </section>

            <AirspaceCard advisories={airspace} itineraries={itineraries} />

            <section className="card" aria-labelledby="table-title">
              <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-5">
                <h2 id="table-title" className="font-medium text-fg">
                  Itineraries
                </h2>
                <p className="text-meta text-fg-3">Ranked by airspace status, safety record, then price · rated on the operating airline</p>
              </div>
              <div className="mt-3">
                <ItineraryTable
                  rows={itineraries}
                  carriers={carriers}
                  pick={advice.pick}
                  selected={selectedItinerary}
                  airspace={airspace}
                  onSelect={(it) => {
                    setSelectedItinerary(it.id);
                    setDrawerCarrier(it.rankedFor);
                  }}
                />
              </div>
            </section>

            <Connections options={selfTransfers} carriers={carriers} />

            <section id="method" className="grid gap-6 border-t border-hair pt-6 text-cap text-fg-2 md:grid-cols-3">
              <div>
                <h3 className="font-medium text-fg">Rated on the operator</h3>
                <p className="mt-1">
                  Codeshares are rated on the airline that flies the plane, and a connection takes the weaker record of
                  its legs.
                </p>
              </div>
              <div>
                <h3 className="font-medium text-fg">Numbers come from code</h3>
                <p className="mt-1">
                  Rates and intervals are computed by a deterministic scoring tool. A guardrail checks every figure the
                  advisor writes against it.
                </p>
              </div>
              <div>
                <h3 className="font-medium text-fg">Uncertainty is shown</h3>
                <p className="mt-1">
                  Airlines with few departures are pulled toward the industry rate and marked as limited data instead
                  of being ranked on a handful of flights.
                </p>
              </div>
            </section>
          </div>

          <aside className="enter space-y-6 [animation-delay:60ms]">
            <AdvisorCard
              headline={advice.headline}
              reasons={advice.reasons}
              caveats={advice.caveats}
              citations={advice.citations}
            />
            <AgentTrace steps={trace} runId={run.id} total={run.finishedIn} />
          </aside>
        </div>
      </main>

      {drawerCarrier && (
        <EvidenceDrawer
          carrier={carriers[drawerCarrier]}
          records={records.filter((r) => r.carrier === drawerCarrier)}
          industry={run.industryRatePerM}
          period={run.window}
          onClose={close}
        />
      )}
    </>
  );
}
