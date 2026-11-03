// Baldwin Alexandria, the server side: a Cloudflare Worker (free plan) between the chat page and Google
// Gemini (free tier). It keeps the Gemini API key secret, loads the source library (knowledge.md) from
// the GitHub site, and makes Gemini answer only from it.
//
// Deploy: Cloudflare dashboard → Workers & Pages → Create → Worker → paste this file → Deploy, then
// Settings → Variables and Secrets → add a Secret named GEMINI_API_KEY with the key from
// https://aistudio.google.com/apikey.

const SITE = "https://artur20papp-source.github.io";
const KNOWLEDGE_URL = `${SITE}/baldwin-palantir/alexandria/knowledge.md`;
const MODEL = "gemini-2.5-flash";
const ALLOWED_ORIGINS = [SITE, "http://localhost:8765"];  // who may use it: the site, and local testing
const MAX_TURNS = 12, MAX_CHARS = 2000;                    // keep requests small on the free tier

const RULES = `You are Baldwin Alexandria, the source library of the Baldwin Palantir map and the Baldwin
Acre appraisal model, a Czech land-development project in Prague.

Answer ONLY from the library below. You explain which sources were used, what was taken from each,
and how each source or input affects the calculations (which model cells, formulas and results it
moves). Rules:
- If the library does not contain the answer, say so plainly and name the closest thing it does cover.
  Do not use outside knowledge, do not guess numbers, and do not give investment advice.
- Refuse politely anything unrelated to these sources and calculations.
- Be precise: give values with units, the model cell where it helps (e.g. Inputs C16), and say clearly
  when an input is an assumption or should be verified.
- Answer in the language of the question (Czech or English). Keep it short: a few sentences or a short
  list. You may use **bold**, bullet lists and links from the library.

=== LIBRARY ===
`;

let cached = { text: null, at: 0 };
async function knowledge() {
  if (cached.text && Date.now() - cached.at < 10 * 60 * 1000) return cached.text;  // refresh every 10 min
  // a fresh address every 10 minutes, and only good answers cached (a cached 404 once kept it offline)
  const res = await fetch(`${KNOWLEDGE_URL}?v=${Math.floor(Date.now() / 600000)}`,
                          { cf: { cacheTtlByStatus: { "200-299": 600, "400-599": 0 } } });
  if (!res.ok) throw new Error(`library not reachable (${res.status})`);
  cached = { text: await res.text(), at: Date.now() };
  return cached.text;
}

const json = (body, status, origin) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": origin,
             "access-control-allow-methods": "POST, OPTIONS", "access-control-allow-headers": "content-type" },
});

export default {
  async fetch(request, env) {
    const origin = request.headers.get("origin") || "";
    const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : SITE;
    if (request.method === "OPTIONS") return json({}, 204, allowed);
    if (request.method !== "POST") return json({ error: "POST a question to this address." }, 405, allowed);
    if (!ALLOWED_ORIGINS.includes(origin)) return json({ error: "Not allowed from this site." }, 403, allowed);
    if (!env.GEMINI_API_KEY) return json({ error: "The GEMINI_API_KEY secret is not set." }, 500, allowed);

    let messages;
    try {
      ({ messages } = await request.json());
    } catch {
      return json({ error: "Send JSON: {messages: [{role, text}]}" }, 400, allowed);
    }
    if (!Array.isArray(messages) || !messages.length) return json({ error: "No question." }, 400, allowed);
    const contents = messages.slice(-MAX_TURNS).map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: String(m.text || "").slice(0, MAX_CHARS) }],
    }));

    let library;
    try {
      library = await knowledge();
    } catch (err) {
      return json({ error: err.message }, 502, allowed);
    }
    const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: RULES + library }] },
        contents,
        generationConfig: { temperature: 0.2, maxOutputTokens: 900 },
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const busy = res.status === 429;
      return json({ error: busy ? "Alexandria is busy (free-tier limit). Try again in a minute."
                                : (data.error && data.error.message) || `Gemini error ${res.status}` }, busy ? 429 : 502, allowed);
    }
    const text = (data.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join("").trim();
    return json({ text: text || "I have no answer to that in the library." }, 200, allowed);
  },
};
