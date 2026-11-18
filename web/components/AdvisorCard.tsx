import { Check, Info } from "lucide-react";

export function AdvisorCard({
  headline,
  reasons,
  caveats,
  citations,
}: {
  headline: string;
  reasons: string[];
  caveats: string[];
  citations: string[];
}) {
  return (
    <section className="card p-5" aria-labelledby="advice-title">
      <p className="text-meta text-fg-3">Travel Advisor</p>
      <h2 id="advice-title" className="mt-2 text-[16px] font-medium leading-6 text-fg">
        {headline}
      </h2>
      <ul className="mt-4 space-y-3">
        {reasons.map((r) => (
          <li key={r} className="flex gap-2 text-cap text-fg-2">
            <Check size={16} strokeWidth={1.5} className="mt-0.5 shrink-0 text-fg-3" />
            <span>{r}</span>
          </li>
        ))}
      </ul>
      <div className="mt-5 border-t border-hair pt-4">
        <p className="text-meta text-fg-3">Keep in mind</p>
        <ul className="mt-2 space-y-3">
          {caveats.map((c) => (
            <li key={c} className="flex gap-2 text-cap text-fg-2">
              <Info size={16} strokeWidth={1.5} className="mt-0.5 shrink-0 text-fg-3" />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {citations.map((c) => (
          <span key={c} className="code">
            {c}
          </span>
        ))}
      </div>
      <p className="mt-5 text-meta text-fg-3">
        Commercial flying is very safe and the differences here are small. This is a summary of public records, not
        travel or safety advice.
      </p>
    </section>
  );
}
