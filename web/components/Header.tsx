import { Github } from "lucide-react";

const links = [
  { label: "Search", href: "#", active: true },
  { label: "Runs", href: "#", active: false },
  { label: "Methodology", href: "#method", active: false },
];

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-hair bg-ink-950/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-8 px-6 lg:px-8">
        <a href="#" className="text-[16px] font-medium tracking-[-0.01em] text-fg">
          SafeFlight
        </a>
        <nav className="hidden items-center gap-1 sm:flex" aria-label="Main">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              aria-current={l.active ? "page" : undefined}
              className={`rounded-ctl px-3 py-1.5 transition-colors duration-150 ease-out ${
                l.active ? "bg-ink-800 text-fg" : "text-fg-2 hover:text-fg"
              }`}
            >
              {l.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <span className="hidden items-center gap-2 text-meta text-fg-3 md:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-caution" aria-hidden />
            Sample data, fictional airlines
          </span>
          <a
            href="https://github.com/striderzz/SafeFlight-AgentOps"
            className="text-fg-3 transition-colors duration-150 ease-out hover:text-fg"
            aria-label="Source on GitHub"
          >
            <Github size={18} strokeWidth={1.5} />
          </a>
        </div>
      </div>
    </header>
  );
}
