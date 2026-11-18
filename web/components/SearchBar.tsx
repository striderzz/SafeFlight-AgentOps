"use client";

import { ArrowLeftRight, Search } from "lucide-react";
import { useState } from "react";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-meta text-fg-3">{label}</span>
      {children}
    </label>
  );
}

const input =
  "h-10 w-full rounded-ctl border border-hair bg-ink-800 px-3 text-body text-fg placeholder:text-fg-3 transition-colors duration-150 ease-out hover:border-hair2 focus:border-sky focus:outline-none";

export function SearchBar({ from, to, date }: { from: string; to: string; date: string }) {
  const [a, setA] = useState(from);
  const [b, setB] = useState(to);

  return (
    <form
      className="card flex flex-col gap-4 p-4 md:flex-row md:items-end"
      onSubmit={(e) => e.preventDefault()}
      aria-label="Search a route"
    >
      <Field label="From">
        <input className={`${input} font-mono uppercase`} value={a} maxLength={3} onChange={(e) => setA(e.target.value)} />
      </Field>
      <button
        type="button"
        onClick={() => {
          setA(b);
          setB(a);
        }}
        className="hidden h-10 w-10 shrink-0 items-center justify-center self-end rounded-ctl text-fg-3 transition-colors duration-150 ease-out hover:bg-ink-800 hover:text-fg md:flex"
        aria-label="Swap airports"
      >
        <ArrowLeftRight size={16} strokeWidth={1.5} />
      </button>
      <Field label="To">
        <input className={`${input} font-mono uppercase`} value={b} maxLength={3} onChange={(e) => setB(e.target.value)} />
      </Field>
      <Field label="Date">
        <input className={`${input} num`} type="date" defaultValue={date} />
      </Field>
      <button
        type="submit"
        className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-ctl bg-fg px-5 font-medium text-ink-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-[background-color,transform] duration-150 ease-out hover:bg-white active:scale-[0.98]"
      >
        <Search size={16} strokeWidth={1.5} />
        Compare airlines
      </button>
    </form>
  );
}
