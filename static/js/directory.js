// Directory index: live search + category/pricing/tag filters.
//
// Search matches name, description, category AND tags (the card's text
// plus its data-tags). Tag chips toggle; multiple selected tags combine
// with AND (a project must have every selected tag). A tag link from a
// project page (?tag=<tag> or ?tags=a,b, or ?q=<text>) is honoured on load.
(function () {
  var search = document.getElementById("search");
  var category = document.getElementById("category-filter");
  var freeOnly = document.getElementById("free-only");
  var ossOnly = document.getElementById("oss-only");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".tag-chip[data-tag]"));
  var clearBtn = document.getElementById("clear-filters");
  var countEl = document.getElementById("result-count");
  var emptyEl = document.getElementById("empty-state");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".project-card"));
  var selectedTags = [];

  function selectedTagSet() { return selectedTags; }

  function apply() {
    var q = (search.value || "").toLowerCase().trim();
    var cat = category.value;
    var tags = selectedTagSet();
    var shown = 0;
    cards.forEach(function (card) {
      var text = (card.textContent || "").toLowerCase();
      var cardTags = (card.dataset.tags || "").toLowerCase().split(/\s+/).filter(Boolean);
      var okQ = !q || text.indexOf(q) !== -1 || cardTags.some(function (t) { return t.indexOf(q) !== -1; });
      var okCat = !cat || (card.dataset.categories || "").indexOf(cat) !== -1;
      var okTags = tags.every(function (t) { return cardTags.indexOf(t) !== -1; });
      var ok = okQ && okCat && okTags
        && (!freeOnly.checked || card.dataset.pricing === "free")
        && (!ossOnly.checked || card.dataset.openSource === "true");
      card.style.display = ok ? "" : "none";
      if (ok) shown += 1;
    });
    if (countEl) countEl.textContent = "Showing " + shown + " of " + cards.length + " projects";
    if (emptyEl) emptyEl.hidden = shown !== 0;
    chips.forEach(function (chip) {
      var active = selectedTags.indexOf(chip.dataset.tag) !== -1;
      chip.setAttribute("aria-pressed", active ? "true" : "false");
      chip.classList.toggle("active", active);
    });
  }

  function toggleTag(tag) {
    var i = selectedTags.indexOf(tag);
    if (i === -1) selectedTags.push(tag); else selectedTags.splice(i, 1);
    apply();
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () { toggleTag(chip.dataset.tag); });
  });

  function clearAll() {
    search.value = "";
    category.value = "";
    freeOnly.checked = false;
    ossOnly.checked = false;
    selectedTags = [];
    apply();
  }
  if (clearBtn) clearBtn.addEventListener("click", clearAll);

  [search, category, freeOnly, ossOnly].forEach(function (el) {
    if (!el) return;
    el.addEventListener("input", apply);
    el.addEventListener("change", apply);
  });

  // Honour deep links from project pages: ?tag=ai, ?tags=ai,api-gateway, ?q=text
  var params = new URLSearchParams(window.location.search);
  var initialTags = params.get("tags") || params.get("tag") || "";
  if (initialTags) {
    selectedTags = initialTags.split(",").map(function (t) { return t.trim().toLowerCase(); })
      .filter(function (t) { return chips.some(function (c) { return c.dataset.tag === t; }); });
  }
  var initialQ = params.get("q");
  if (initialQ && search) search.value = initialQ;
  var initialCat = params.get("category");
  if (initialCat && category) category.value = initialCat;
  apply();

  // Exposed for tests / debugging: pure-ish filter state, no DOM writes.
  window.OpenProjectDirectory = { apply: apply, toggleTag: toggleTag, clearAll: clearAll,
    selectedTags: function () { return selectedTags.slice(); } };
})();
