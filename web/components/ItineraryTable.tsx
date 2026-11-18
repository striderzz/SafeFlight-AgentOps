import { ChevronRight } from "lucide-react";
import type { AirspaceAdvisory, Carrier, Itinerary } from "@/lib/sample";
import { duration, price, rate } from "@/lib/format";
import { BandTag } from "./BandTag";

export function ItineraryTable({
  rows,
  carriers,
  pick,
  selected,
  airspace,
  onSelect,
}: {
  rows: Itinerary[];
  carriers: Record<string, Carrier>;
  pick: string;
  selected: string | null;
  airspace: AirspaceAdvisory[];
  onSelect: (it: Itinerary) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead>
          <tr className="text-meta text-fg-3">
            <th className="w-10 px-4 py-3 font-normal">#</th>
            <th className="px-4 py-3 font-normal">Flights</th>
            <th className="px-4 py-3 font-normal">Aircraft</th>
            <th className="px-4 py-3 text-right font-normal">Duration</th>
            <th className="px-4 py-3 font-normal">Safety record</th>
            <th className="px-4 py-3 text-right font-normal">Rate, 90% interval</th>
            <th className="px-4 py-3 text-right font-normal">Price</th>
            <th className="w-10 px-2 py-3" />
          </tr>
        </thead>
        <tbody>
          {rows.map((it, i) => {
            const c = carriers[it.rankedFor];
            const isSel = selected === it.id;
            const isPick = pick === it.id;
            const advisory = airspace.find((a) => a.itineraryId === it.id && a.status !== "clear");
            const operatorNote = it.legs.find((l) => l.operator !== it.marketedBy);
            return (
              <tr
                key={it.id}
                onClick={() => onSelect(it)}
                tabIndex={0}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(it)}
                aria-selected={isSel}
                className={`cursor-pointer border-t border-hair align-top transition-colors duration-150 ease-out focus:outline-none focus-visible:bg-ink-800 ${
                  isSel ? "bg-ink-800 shadow-[inset_2px_0_0_#6cb4ee]" : "hover:bg-ink-800/60"
                }`}
              >
                <td className="num px-4 py-4 font-mono text-meta text-fg-3">{i + 1}</td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-fg">{it.legs.map((l) => l.flight).join(" + ")}</span>
                    {isPick && <span className="rounded-tag bg-sky/10 px-2 py-0.5 text-meta text-sky">Recommended</span>}
                  </div>
                  <div className="mt-1 text-cap text-fg-3">
                    {carriers[it.marketedBy].name}
                    {it.legs.length > 1 ? ` · via ${it.legs[0].to}` : " · nonstop"}
                    {operatorNote ? ` · ${operatorNote.flight} operated by ${carriers[operatorNote.operator].name}` : ""}
                  </div>
                </td>
                <td className="px-4 py-4 text-cap text-fg-2">{it.legs.map((l) => l.aircraft).join(", ")}</td>
                <td className="num whitespace-nowrap px-4 py-4 text-right text-fg-2">{duration(it.durationMin)}</td>
                <td className="px-4 py-4">
                  <BandTag band={it.band} />
                  {advisory && (
                    <p className="mt-1 whitespace-nowrap text-meta text-caution">
                      {advisory.status === "avoid" ? "Avoid" : "Caution"} · airspace advisory
                    </p>
                  )}
                </td>
                <td className="num whitespace-nowrap px-4 py-4 text-right font-mono text-cap">
                  <span className="text-fg">{rate(c.ratePerM)}</span>
                  <span className="text-fg-3">
                    {" "}
                    {rate(c.interval[0])} to {rate(c.interval[1])}
                  </span>
                </td>
                <td className="num px-4 py-4 text-right text-fg">{price(it.priceInr)}</td>
                <td className="px-2 py-4 text-fg-3">
                  <ChevronRight size={16} strokeWidth={1.5} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
