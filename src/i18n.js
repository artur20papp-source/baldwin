// Languages: Czech, English and Slovak. The choice from the switcher in the top bar is kept in this browser
// (the map and Baldwin Alexandria share it); a first visit is in English. Scripts call
// t(cs, en, sk) for their texts and tw(word) for the values that come in Czech with the IPR data; static
// HTML carries all three as <span class="l-cs|l-en|l-sk"> and the CSS shows the right one. Switching
// reloads the page, without the start screen. Inlined at the top of the page (map and Alexandria).
(function () {
  const LANGS = ["cs", "en", "sk"];
  let lang = null;
  try { lang = localStorage.getItem("baldwin-lang"); } catch (e) {}
  if (!LANGS.includes(lang)) lang = "en";  // English until a visitor picks another
  document.documentElement.lang = lang;
  window.baldwinLang = lang;
  window.t = (cs, en, sk) => (lang === "en" ? en : lang === "sk" ? sk : cs);

  // the IPR data's own Czech labels (stability, use, urban structure)
  const WORDS = {
    "rozvojová": ["development", "rozvojová"], "transformační": ["transformation", "transformačná"],
    "obytná": ["residential", "obytná"],
    "heterogenní struktura": ["heterogeneous structure", "heterogénna štruktúra"],
    "vesnická struktura": ["village structure", "vidiecka štruktúra"],
    "struktura zahradního města": ["garden-city structure", "štruktúra záhradného mesta"],
    "hybridní struktura": ["hybrid structure", "hybridná štruktúra"],
    "struktura areálů vybavenosti": ["amenity-campus structure", "štruktúra areálov vybavenosti"],
    "bloková struktura": ["block structure", "bloková štruktúra"],
    "modernistická struktura": ["modernist structure", "modernistická štruktúra"],
  };
  window.tw = (w) => (WORDS[w] && lang !== "cs" ? WORDS[w][lang === "en" ? 0 : 1] : w);

  window.baldwinSetLang = (next) => {
    if (!LANGS.includes(next) || next === lang) return;
    try {
      localStorage.setItem("baldwin-lang", next);
      sessionStorage.setItem("baldwin-skip-intro", "1");
    } catch (e) {}
    location.reload();
  };
  let skip = false;
  try { skip = sessionStorage.getItem("baldwin-skip-intro") === "1"; sessionStorage.removeItem("baldwin-skip-intro"); } catch (e) {}
  if (skip) document.documentElement.classList.add("skip-intro");
})();

// The buttons to the three parts (map, Acre, Alexandria) slide their name out to its own width, not to a
// fixed one: with a fixed width a short name ("ACRE") would finish early and a long one look slower
document.addEventListener("mouseover", (e) => {
  const link = e.target.closest && e.target.closest(".ds-lighthouse, .go, .orb-link");
  const text = link && link.querySelector(".lh-text, .tx");
  if (text) text.style.setProperty("--w", text.scrollWidth + 18 + "px");
});
