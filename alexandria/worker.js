// Baldwin Alexandria, the server side: a Cloudflare Worker (free plan) between the chat page and Google
// Gemini (free tier). It keeps the Gemini API key secret, loads the source library (knowledge.md) from
// the GitHub site, and makes Gemini answer only from it.
//
// Deploy: Cloudflare dashboard → Workers & Pages → Create → Worker → paste this file → Deploy, then
// Settings → Variables and Secrets → add a Secret named GEMINI_API_KEY with the key from
// https://aistudio.google.com/apikey.

const SITE = "https://artur20papp-source.github.io";
const KNOWLEDGE_URL = `${SITE}/baldwin-palantir/alexandria/knowledge.md`;
// Google retires model names over time; this one is tried first, and if Google rejects it the worker
// picks the newest "flash" model from Google's own list (or set a GEMINI_MODEL variable to choose one).
const MODEL = "gemini-3.8-flash";
const API = "https://generativelanguage.googleapis.com/v1beta";
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

// the newest text "flash" model this key may use, from Google's model list
let picked = null;
async function newestFlash(key) {
  const res = await fetch(`${API}/models?pageSize=200`, { headers: { "x-goog-api-key": key } });
  const data = await res.json().catch(() => ({}));
  const version = (name) => (name.match(/gemini-(\d+(?:\.\d+)?)/) || [0, 0])[1] * 1;
  const usable = (data.models || []).map((m) => ({ id: m.name.replace("models/", ""), methods: m.supportedGenerationMethods || [] }))
    .filter((m) => m.methods.includes("generateContent") && /^gemini-[\d.]+-flash$|^gemini-[\d.]+-flash-latest$/.test(m.id))
    .sort((a, b) => version(b.id) - version(a.id));
  return usable.length ? usable[0].id : null;
}

async function generate(key, model, body) {
  const res = await fetch(`${API}/models/${model}:generateContent`, {
    method: "POST", headers: { "content-type": "application/json", "x-goog-api-key": key }, body: JSON.stringify(body),
  });
  return { res, data: await res.json().catch(() => ({})) };
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
    const body = {
      systemInstruction: { parts: [{ text: RULES + library }] },
      contents,
      generationConfig: { temperature: 0.2, maxOutputTokens: 900 },
    };
    let model = env.GEMINI_MODEL || picked || MODEL;
    let { res, data } = await generate(env.GEMINI_API_KEY, model, body);
    // the model was retired or is not offered to this key: take the newest flash model and try once more
    if (!res.ok && res.status !== 429 && !env.GEMINI_MODEL) {
      const fresh = await newestFlash(env.GEMINI_API_KEY);
      if (fresh && fresh !== model) {
        model = picked = fresh;
        ({ res, data } = await generate(env.GEMINI_API_KEY, model, body));
      }
    }
    if (!res.ok) {
      const busy = res.status === 429;
      return json({ error: busy ? "Alexandria is busy (free-tier limit). Try again in a minute."
                                : (data.error && data.error.message) || `Gemini error ${res.status}` }, busy ? 429 : 502, allowed);
    }
    const text = (data.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join("").trim();
    return json({ text: text || "I have no answer to that in the library." }, 200, allowed);
  },
};
