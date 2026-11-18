import type { Band } from "./sample";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export const price = (n: number) => inr.format(n);

export const duration = (min: number) => `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;

export const rate = (n: number) => n.toFixed(2);

export const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });

export const bandLabel: Record<Band, string> = {
  strong: "Strong record",
  typical: "Typical",
  limited: "Limited data",
};
