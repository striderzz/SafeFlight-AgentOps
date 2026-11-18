import type { Band } from "@/lib/sample";
import { bandLabel } from "@/lib/format";

const dot: Record<Band, string> = {
  strong: "bg-good",
  typical: "bg-fg-3",
  limited: "border border-dashed border-fg-3 bg-transparent",
};

export function BandTag({ band }: { band: Band }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-cap text-fg-2">
      <span className={`h-2 w-2 rounded-full ${dot[band]}`} aria-hidden />
      {bandLabel[band]}
    </span>
  );
}
