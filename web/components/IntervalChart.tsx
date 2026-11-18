import type { Carrier } from "@/lib/sample";
import { rate } from "@/lib/format";

// The one rich moment on the page: each carrier's rate with its 90% interval, against the
// industry baseline. The recommended carrier carries the accent; everything else is neutral.

const W = 760;
const LEFT = 196;
const RIGHT = 64;
const ROW = 44;
const TOP = 28;
const MAX = 0.6;
const ticks = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6];

export function IntervalChart({
  carriers,
  industry,
  highlight,
  selected,
  onSelect,
}: {
  carriers: Carrier[];
  industry: number;
  highlight: string;
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  const H = TOP + carriers.length * ROW + 36;
  const x = (v: number) => LEFT + (v / MAX) * (W - LEFT - RIGHT);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label={`Accidents per million departures with 90 percent intervals. Industry rate ${industry}.`}
    >
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={TOP - 8} y2={H - 28} stroke="rgba(237,237,237,0.06)" />
          <text x={x(t)} y={H - 10} textAnchor="middle" className="fill-fg-3 font-mono" fontSize={11}>
            {t.toFixed(1)}
          </text>
        </g>
      ))}

      <line x1={x(industry)} x2={x(industry)} y1={TOP - 16} y2={H - 28} stroke="#a1a1a6" strokeDasharray="3 4" />
      <text x={x(industry) + 6} y={TOP - 10} className="fill-fg-2" fontSize={11}>
        Industry {rate(industry)}
      </text>

      {carriers.map((c, i) => {
        const y = TOP + i * ROW + ROW / 2;
        const lead = c.code === highlight;
        const sel = c.code === selected;
        const stroke = lead ? "#6cb4ee" : sel ? "#ededed" : "#85858b";
        return (
          <g
            key={c.code}
            onClick={() => onSelect(c.code)}
            className="cursor-pointer"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(c.code)}
            aria-label={`${c.name}, rate ${rate(c.ratePerM)}, interval ${rate(c.interval[0])} to ${rate(c.interval[1])}`}
          >
            <rect x={0} y={y - ROW / 2 + 2} width={W} height={ROW - 4} rx={8} fill={sel ? "#19191b" : "transparent"} />
            <text x={12} y={y + 4} className="fill-fg-3 font-mono" fontSize={11}>
              {c.code}
            </text>
            <text x={44} y={y + 4} className={lead || sel ? "fill-fg" : "fill-fg-2"} fontSize={13}>
              {c.name}
            </text>
            <line
              x1={x(c.interval[0])}
              x2={x(c.interval[1])}
              y1={y}
              y2={y}
              stroke={stroke}
              strokeWidth={2}
              strokeDasharray={c.band === "limited" ? "4 4" : undefined}
              strokeLinecap="round"
            />
            {[c.interval[0], c.interval[1]].map((v) => (
              <line key={v} x1={x(v)} x2={x(v)} y1={y - 5} y2={y + 5} stroke={stroke} strokeWidth={1.5} />
            ))}
            <circle cx={x(c.ratePerM)} cy={y} r={lead ? 6 : 5} fill={lead ? "#6cb4ee" : "#141415"} stroke={stroke} strokeWidth={2} />
            <text x={W - 8} y={y + 4} textAnchor="end" className={lead ? "fill-fg font-mono" : "fill-fg-3 font-mono"} fontSize={11}>
              {rate(c.ratePerM)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
