"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import type { AccidentRecord, Carrier } from "@/lib/sample";
import { rate } from "@/lib/format";
import { BandTag } from "./BandTag";

const severity: Record<AccidentRecord["severity"], string> = {
  fatal: "Fatal",
  serious: "Serious",
  minor: "Minor",
};

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-ctl border border-hair bg-ink-850 p-3">
      <p className="text-meta text-fg-3">{label}</p>
      <p className="num mt-2 text-[20px] font-medium leading-6 text-fg">{value}</p>
      <p className="mt-1 text-meta text-fg-3">{sub}</p>
    </div>
  );
}

export function EvidenceDrawer({
  carrier,
  records,
  industry,
  period,
  onClose,
}: {
  carrier: Carrier;
  records: AccidentRecord[];
  industry: number;
  period: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [onClose]);

  const total = carrier.accidents.fatal + carrier.accidents.serious + carrier.accidents.minor;

  return (
    <div className="fixed inset-0 z-30" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <button className="absolute inset-0 bg-black/50" onClick={onClose} aria-label="Close evidence" />
      <aside className="enter absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col border-l border-hair bg-ink-950">
        <div className="flex h-14 items-center gap-3 border-b border-hair px-5">
          <span className="code">{carrier.code}</span>
          <h2 id="drawer-title" className="font-medium text-fg">
            {carrier.name}
          </h2>
          <button
            onClick={onClose}
            className="ml-auto rounded-ctl p-2 text-fg-3 transition-colors duration-150 ease-out hover:bg-ink-800 hover:text-fg"
            aria-label="Close"
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          <div className="flex items-center justify-between">
            <BandTag band={carrier.band} />
            <span className="text-meta text-fg-3">{period}</span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <Stat label="Rate per million" value={rate(carrier.ratePerM)} sub={`industry ${rate(industry)}`} />
            <Stat
              label="90% interval"
              value={`${rate(carrier.interval[0])}–${rate(carrier.interval[1])}`}
              sub="after shrinkage"
            />
            <Stat label="Departures" value={`${carrier.departuresM.toFixed(2)}M`} sub={`${total} accidents`} />
          </div>

          <div>
            <h3 className="text-cap font-medium text-fg">How the rate is built</h3>
            <p className="mt-2 text-cap text-fg-2">
              Accidents are weighted by severity ({carrier.accidents.fatal} fatal, {carrier.accidents.serious} serious,{" "}
              {carrier.accidents.minor} minor), recent years count more, and the result is pulled toward the industry
              rate in proportion to how few departures the airline has flown. The Risk Analyst calls this as a
              deterministic tool, so no number here is written by a model.
            </p>
          </div>

          <div>
            <h3 className="text-cap font-medium text-fg">Records</h3>
            {records.length === 0 ? (
              <p className="mt-2 text-cap text-fg-3">No records in the sample for this airline</p>
            ) : (
              <ul className="mt-2 divide-y divide-hair rounded-ctl border border-hair">
                {records.map((r) => (
                  <li key={r.id} className="p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="num font-mono text-meta text-fg-3">
                        {r.date} · {r.aircraft}
                      </span>
                      <span className="text-meta text-fg-2">{severity[r.severity]}</span>
                    </div>
                    <p className="mt-1 text-cap text-fg-2">{r.summary}</p>
                    <p className="mt-2 font-mono text-meta text-fg-3">{r.id}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <p className="border-t border-hair px-5 py-3 text-meta text-fg-3">Sample records for a fictional airline</p>
      </aside>
    </div>
  );
}
