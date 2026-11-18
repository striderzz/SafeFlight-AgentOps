// SAMPLE DATA. Fictional airlines and invented figures, used only to build and demo the
// interface before the agents and the scoring model exist. Never present these numbers
// as real safety data. The shapes match the API contract the backend will return.

export type Band = "strong" | "typical" | "limited";

export interface Carrier {
  code: string;
  name: string;
  departuresM: number; // departures flown in the window, millions
  accidents: { fatal: number; serious: number; minor: number };
  ratePerM: number; // shrunk, severity-weighted accidents per million departures
  interval: [number, number]; // 90% credible interval
  band: Band;
}

export interface Leg {
  from: string;
  to: string;
  flight: string;
  operator: string; // operating carrier code
  aircraft: string;
}

export interface Itinerary {
  id: string;
  marketedBy: string;
  legs: Leg[];
  durationMin: number;
  priceInr: number;
  band: Band; // weakest operating carrier on the itinerary
  rankedFor: string; // carrier code that sets the band
}

export interface AccidentRecord {
  id: string;
  carrier: string;
  date: string;
  aircraft: string;
  severity: "fatal" | "serious" | "minor";
  summary: string;
}

export interface TraceStep {
  agent: string;
  action: string;
  detail: string;
  seconds: number;
  status: "done" | "checked" | "waiting";
}

export const run = {
  id: "run_7f3c9a",
  from: { code: "BOM", city: "Mumbai" },
  to: { code: "LHR", city: "London Heathrow" },
  date: "2026-12-04",
  window: "2016 to 2025",
  industryRatePerM: 0.21,
  finishedIn: 38,
  judgeScore: 4.5,
};

export const carriers: Record<string, Carrier> = {
  MD: {
    code: "MD",
    name: "Meridian Air",
    departuresM: 2.41,
    accidents: { fatal: 0, serious: 1, minor: 3 },
    ratePerM: 0.11,
    interval: [0.05, 0.2],
    band: "strong",
  },
  NW: {
    code: "NW",
    name: "Northwind Airways",
    departuresM: 4.06,
    accidents: { fatal: 0, serious: 2, minor: 6 },
    ratePerM: 0.15,
    interval: [0.09, 0.24],
    band: "strong",
  },
  CL: {
    code: "CL",
    name: "Coralline",
    departuresM: 1.62,
    accidents: { fatal: 0, serious: 2, minor: 4 },
    ratePerM: 0.23,
    interval: [0.13, 0.37],
    band: "typical",
  },
  SR: {
    code: "SR",
    name: "Saffron Regional",
    departuresM: 0.88,
    accidents: { fatal: 0, serious: 2, minor: 3 },
    ratePerM: 0.29,
    interval: [0.15, 0.52],
    band: "typical",
  },
  KA: {
    code: "KA",
    name: "Kestrel Atlantic",
    departuresM: 0.27,
    accidents: { fatal: 0, serious: 0, minor: 1 },
    ratePerM: 0.19,
    interval: [0.06, 0.55],
    band: "limited",
  },
};

export const itineraries: Itinerary[] = [
  {
    id: "it_1",
    marketedBy: "MD",
    legs: [{ from: "BOM", to: "LHR", flight: "MD 104", operator: "MD", aircraft: "A350-900" }],
    durationMin: 595,
    priceInr: 68400,
    band: "strong",
    rankedFor: "MD",
  },
  {
    id: "it_2",
    marketedBy: "NW",
    legs: [{ from: "BOM", to: "LHR", flight: "NW 2", operator: "NW", aircraft: "787-9" }],
    durationMin: 580,
    priceInr: 72150,
    band: "strong",
    rankedFor: "NW",
  },
  {
    id: "it_3",
    marketedBy: "CL",
    legs: [
      { from: "BOM", to: "DXB", flight: "CL 88", operator: "CL", aircraft: "A321neo" },
      { from: "DXB", to: "LHR", flight: "CL 31", operator: "CL", aircraft: "777-300ER" },
    ],
    durationMin: 755,
    priceInr: 51900,
    band: "typical",
    rankedFor: "CL",
  },
  {
    id: "it_4",
    marketedBy: "NW",
    legs: [
      { from: "BOM", to: "AMD", flight: "NW 4410", operator: "SR", aircraft: "ATR 72-600" },
      { from: "AMD", to: "LHR", flight: "NW 18", operator: "NW", aircraft: "787-9" },
    ],
    durationMin: 790,
    priceInr: 49300,
    band: "typical",
    rankedFor: "SR",
  },
  {
    id: "it_5",
    marketedBy: "KA",
    legs: [{ from: "BOM", to: "LHR", flight: "KA 7", operator: "KA", aircraft: "777-300ER" }],
    durationMin: 605,
    priceInr: 64800,
    band: "limited",
    rankedFor: "KA",
  },
];

export interface TicketLeg extends Leg {
  depart: string;
  arrive: string;
  priceInr: number;
}

export interface SelfTransfer {
  id: string;
  hub: { code: string; city: string };
  legs: [TicketLeg, TicketLeg];
  layoverMin: number;
  durationMin: number;
  band: Band;
}

// Two separate one-way tickets through a hub, both legs on strong-record airlines.
export const selfTransfers: SelfTransfer[] = [
  {
    id: "st_1",
    hub: { code: "DXB", city: "Dubai" },
    legs: [
      { from: "BOM", to: "DXB", flight: "MD 210", operator: "MD", aircraft: "A321neo", depart: "02:10", arrive: "03:55", priceInr: 14200 },
      { from: "DXB", to: "LHR", flight: "NW 51", operator: "NW", aircraft: "787-9", depart: "08:20", arrive: "12:35", priceInr: 31800 },
    ],
    layoverMin: 265,
    durationMin: 775,
    band: "strong",
  },
  {
    id: "st_2",
    hub: { code: "DOH", city: "Doha" },
    legs: [
      { from: "BOM", to: "DOH", flight: "NW 302", operator: "NW", aircraft: "A321neo", depart: "04:40", arrive: "05:50", priceInr: 12900 },
      { from: "DOH", to: "LHR", flight: "MD 19", operator: "MD", aircraft: "A350-900", depart: "09:15", arrive: "14:05", priceInr: 33600 },
    ],
    layoverMin: 205,
    durationMin: 715,
    band: "strong",
  },
];

export type AirspaceStatus = "avoid" | "caution" | "clear";

export interface AirspaceAdvisory {
  itineraryId: string;
  status: AirspaceStatus;
  zone: string;
  source: string; // official bulletin id; news never sets the status
  validUntil: string;
  note: string;
  news: { title: string; outlet: string; date: string }[];
}

// Fictional zone and bulletin, for the interface only. Not a statement about real airspace.
export const airspace: AirspaceAdvisory[] = [
  {
    itineraryId: "it_5",
    status: "avoid",
    zone: "Sample zone ZX",
    source: "CZIB-SAMPLE-07",
    validUntil: "2027-01-31",
    note: "The direct track of KA 7 crosses an active prohibition zone; the airline may reroute, but the filed track was flagged",
    news: [
      { title: "Sample report: airspace over zone ZX closed to civil traffic", outlet: "Sample Wire", date: "2026-11-28" },
      { title: "Sample report: carriers add 40 minutes to avoid zone ZX", outlet: "Sample Aviation Daily", date: "2026-11-30" },
    ],
  },
];

export const records: AccidentRecord[] = [
  {
    id: "SAMPLE-23-014",
    carrier: "MD",
    date: "2023-08-11",
    aircraft: "A320neo",
    severity: "serious",
    summary: "Cabin crew member injured during severe turbulence in descent; seatbelt sign was on",
  },
  {
    id: "SAMPLE-21-206",
    carrier: "MD",
    date: "2021-02-03",
    aircraft: "A350-900",
    severity: "minor",
    summary: "Tail strike on rotation in gusting crosswind; aircraft returned and landed normally",
  },
  {
    id: "SAMPLE-19-077",
    carrier: "MD",
    date: "2019-06-22",
    aircraft: "A320neo",
    severity: "minor",
    summary: "Ground collision with a tug during pushback; no injuries",
  },
  {
    id: "SAMPLE-17-131",
    carrier: "MD",
    date: "2017-11-30",
    aircraft: "A321",
    severity: "minor",
    summary: "Bird strike on climb out damaged the radome; precautionary return",
  },
];

export const advice = {
  pick: "it_1",
  headline: "Meridian Air MD 104 has the strongest record on this route",
  reasons: [
    "0.11 accidents per million departures over 2.41 million departures, about half the industry rate of 0.21",
    "No fatal accidents in the window; the one serious event was turbulence with a crew injury",
    "Northwind NW 2 is close behind at 0.15 and its interval overlaps, so either is a sound choice",
  ],
  caveats: [
    "KA 7 is ranked last: its filed track crosses an active airspace prohibition (CZIB-SAMPLE-07)",
    "Kestrel Atlantic also has too few departures for a firm estimate; its wide interval is a data gap",
    "The NW 4410 connection is operated by Saffron Regional, so that itinerary is rated on Saffron's record",
  ],
  citations: ["SAMPLE-23-014", "SAMPLE-21-206", "carrier_exposure:MD", "carrier_exposure:NW"],
};

export const trace: TraceStep[] = [
  { agent: "Flight Scout", action: "search_flights", detail: "8 offers, 5 kept after de-duplicating codeshares", seconds: 3.1, status: "done" },
  { agent: "You", action: "Confirm itineraries", detail: "5 of 5 selected for research", seconds: 0, status: "done" },
  { agent: "Safety Researcher", action: "carrier_accidents, carrier_exposure", detail: "5 carriers via the safety-data MCP server", seconds: 6.4, status: "done" },
  { agent: "Safety Researcher", action: "search_accident_reports", detail: "11 passages after hybrid search and reranking", seconds: 4.2, status: "done" },
  { agent: "Airspace Watch", action: "conflict_bulletins, track_crosses", detail: "1 itinerary crosses an active prohibition zone", seconds: 2.7, status: "done" },
  { agent: "Airspace Watch", action: "search_news", detail: "2 recent reports summarized as context only", seconds: 5.3, status: "done" },
  { agent: "Risk Analyst", action: "score_carrier", detail: "Bayesian rates and 90% intervals for 5 carriers", seconds: 9.8, status: "done" },
  { agent: "Travel Advisor", action: "Recommendation", detail: "Structured output with 4 citations", seconds: 11.6, status: "done" },
  { agent: "Guardrail", action: "Numbers and citations", detail: "9 of 9 figures match, 4 of 4 citations exist", seconds: 0.4, status: "checked" },
  { agent: "Judge", action: "LLM-as-a-judge", detail: "Clarity and honest uncertainty, 4.5 of 5", seconds: 2.5, status: "checked" },
];
