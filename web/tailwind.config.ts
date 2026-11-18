import type { Config } from "tailwindcss";

// Graphite ramp (dark), one sky accent from the cockpit-at-night world.
// Spacing stays on Tailwind's 4px scale; no arbitrary one-off values.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0f0f10", // deepest: header, drawer
          900: "#141415", // page
          850: "#19191b", // card
          800: "#232325", // raised: inputs, active row
        },
        fg: {
          DEFAULT: "#ededed",
          2: "#a1a1a6",
          3: "#85858b",
        },
        sky: {
          DEFAULT: "#6cb4ee", // accent; dark text on it passes 4.5:1
          ink: "#0b1a26",
        },
        good: "#4cc38a",
        caution: "#d9a441",
      },
      borderColor: {
        hair: "rgba(237,237,237,0.08)",
        hair2: "rgba(237,237,237,0.14)",
      },
      fontFamily: {
        sans: ["var(--font-geist)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        meta: ["12px", "16px"],
        cap: ["13px", "20px"],
        body: ["14px", "20px"],
        title: ["28px", "34px"],
        figure: ["28px", "28px"],
      },
      borderRadius: {
        tag: "6px",
        ctl: "8px",
        card: "14px",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
