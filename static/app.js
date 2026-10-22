(() => {
  const state = {
    topicId: null,       // null = home (12 root fields)
    topic: null,
    breadcrumb: [],
    children: [],
    siblings: [],
    activeTab: "beginner", // beginner | advanced | reading
    explain: null,
    readingList: null,
    models: [],
    defaultModel: "anthropic/claude-sonnet-4.5",
  };

  const el = (id) => document.getElementById(id);
  const homeBtn = el("home-btn");
  const searchInput = el("search-input");
  const searchResults = el("search-results");
  const browseView = el("browse-view");
  const detailView = el("detail-view");
  const browseBreadcrumb = el("breadcrumb");
  const browseTitle = el("browse-title");
  const browseCount = el("browse-count");
  const topicGrid = el("topic-grid");
  const detailBreadcrumb = el("detail-breadcrumb");
  const detailContent = el("detail-content");
  const metaLine = el("meta-line");
  const syncBtn = el("sync-btn");
  const syncMsg = el("sync-msg");
  const settingsBtn = el("settings-btn");
  const settingsOverlay = el("settings-overlay");
  const settingsClose = el("settings-close");
  const settingsSave = el("settings-save");
  const apiKeyInput = el("api-key-input");
  const modelSelect = el("model-select");

  function getApiKey() { return localStorage.getItem("mathAtlasApiKey") || ""; }
  function getModel() { return localStorage.getItem("mathAtlasModel") || state.defaultModel; }

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res.json();
  }

  function renderBreadcrumb(container, trail, onHome) {
    container.innerHTML = "";
    const homeCrumb = document.createElement("button");
    homeCrumb.textContent = "Fields";
    homeCrumb.onclick = onHome;
    container.appendChild(homeCrumb);
    trail.forEach((t, i) => {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "/";
      container.appendChild(sep);
      if (i === trail.length - 1) {
        const span = document.createElement("span");
        span.className = "crumb-current";
        span.textContent = t.title;
        container.appendChild(span);
      } else {
        const btn = document.createElement("button");
        btn.textContent = t.title;
        btn.onclick = () => navigateTo(t.id);
        container.appendChild(btn);
      }
    });
  }

  function topicCardHtml(t) {
    const isLeaf = !t.childIds || t.childIds.length === 0;
    return `
      <button class="topic-card ${isLeaf ? "is-leaf" : ""}" data-id="${escapeAttr(t.id)}">
        <span class="topic-card-title">${escapeHtml(t.title)}</span>
        <span class="topic-card-meta">
          <span>${t.count ?? "?"} problems</span>
          <span>${t.pct ?? "?"}% solved</span>
          ${isLeaf ? "" : `<span>${t.childIds.length} subtopics</span>`}
        </span>
        <span class="topic-card-arrow">&rarr;</span>
      </button>`;
  }

  function escapeHtml(s) {
    return (s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }

  async function showHome() {
    state.topicId = null;
    detailView.classList.add("hidden");
    browseView.classList.remove("hidden");
    renderBreadcrumb(browseBreadcrumb, [], showHome);
    browseTitle.textContent = "Fields";
    const roots = await api("/api/roots");
    browseCount.textContent = `${roots.length} top-level fields`;
    topicGrid.innerHTML = roots.map(topicCardHtml).join("");
    window.scrollTo(0, 0);
  }

  // Single delegated listener instead of rebinding onclick after every
  // render -- topic cards and related chips get re-created on every
  // navigation/tab switch, so per-element binding silently drops handlers
  // on freshly-inserted nodes (that was the "clicking past level 1 does
  // nothing" bug).
  document.addEventListener("click", (e) => {
    const card = e.target.closest(".topic-card, .chip");
    if (card && card.dataset.id) navigateTo(card.dataset.id);
  });

  async function navigateTo(topicId) {
    searchResults.classList.add("hidden");
    searchInput.value = "";
    const data = await api(`/api/topics/${encodeURI(topicId)}`);
    state.topicId = topicId;
    state.topic = data.topic;
    state.breadcrumb = data.breadcrumb;
    state.children = data.children;
    state.siblings = data.siblings;
    state.activeTab = "beginner";
    state.explain = null;
    state.readingList = null;

    browseView.classList.add("hidden");
    detailView.classList.remove("hidden");
    renderBreadcrumb(detailBreadcrumb, data.breadcrumb, showHome);
    renderDetail();
    window.scrollTo(0, 0);
  }

  function renderDetail() {
    const t = state.topic;
    const childrenHtml = state.children.length
      ? `<div class="panel-section">
           <h2>Subtopics (${state.children.length})</h2>
           <div class="topic-grid">${state.children.map(topicCardHtml).join("")}</div>
         </div>`
      : "";
    const relatedHtml = state.siblings.length
      ? `<div class="related-chips">
           ${state.siblings.slice(0, 10).map((s) =>
             `<button class="chip" data-id="${escapeAttr(s.id)}">${escapeHtml(s.title)}</button>`
           ).join("")}
         </div>`
      : "";

    detailContent.innerHTML = `
      <div class="detail-head">
        <h1 class="detail-title">${escapeHtml(t.title)}</h1>
        <div class="detail-meta">
          <span>${t.count ?? "?"} source problems</span>
          <span>${t.pct ?? "?"}% solved on mathprobvault</span>
          <span>depth ${t.depth}</span>
        </div>
        ${relatedHtml}
      </div>
      ${childrenHtml}
      <div class="panel-section">
        <h2>Explain this topic</h2>
        <div class="tabs">
          <button class="tab-btn" data-tab="beginner">Beginner</button>
          <button class="tab-btn" data-tab="advanced">Advanced</button>
          <button class="tab-btn" data-tab="reading">Reading list</button>
        </div>
        <div id="tab-content"></div>
      </div>
    `;

    detailContent.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === state.activeTab);
      btn.onclick = () => { state.activeTab = btn.dataset.tab; renderDetail(); };
    });

    renderTabContent();
  }

  function renderTabContent() {
    const host = document.getElementById("tab-content");
    if (!host) return;

    if (state.activeTab === "reading") {
      if (state.readingList) { renderReadingList(host); }
      else { renderGenCta(host, "Build a zero-to-mastery reading path for this topic.", loadReadingList); }
      return;
    }

    // beginner / advanced both come from the same `explain` payload
    if (state.explain) { renderExplain(host); }
    else { renderGenCta(host, "Generate a beginner-friendly explanation and a formal advanced treatment.", loadExplain); }
  }

  function renderGenCta(host, text, onGenerate) {
    if (!getApiKey()) {
      host.innerHTML = `
        <div class="gen-cta">
          <p>${text}</p>
          <p style="color:var(--amber)">Add your OpenRouter API key in Settings (&#9881; top right) first.</p>
          <button class="btn-primary" id="open-settings-cta">Open settings</button>
        </div>`;
      document.getElementById("open-settings-cta").onclick = openSettings;
      return;
    }
    host.innerHTML = `
      <div class="gen-cta">
        <p>${text}</p>
        <button class="btn-primary" id="gen-btn">Generate</button>
      </div>`;
    document.getElementById("gen-btn").onclick = () => onGenerate(false);
  }

  function renderLoading(host, label) {
    host.innerHTML = `<div class="loading-row"><span class="spinner"></span> ${label}</div>`;
  }

  function renderErrorBox(host, msg, retry) {
    host.innerHTML = `<div class="error-box">${escapeHtml(msg)}</div>
      <div style="margin-top:12px"><button class="btn-ghost" id="retry-btn">Try again</button></div>`;
    document.getElementById("retry-btn").onclick = retry;
  }

  async function loadExplain(force) {
    const host = document.getElementById("tab-content");
    renderLoading(host, "Generating explanation… (first time only, cached after)");
    try {
      const body = { apiKey: getApiKey(), model: getModel(), forceRegenerate: !!force };
      const data = await api(`/api/topics/${encodeURI(state.topicId)}/explain`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      state.explain = data;
      renderDetail();
    } catch (e) {
      renderErrorBox(host, e.message, () => loadExplain(force));
    }
  }

  async function loadReadingList(force) {
    const host = document.getElementById("tab-content");
    renderLoading(host, "Building reading list… (first time only, cached after)");
    try {
      const body = { apiKey: getApiKey(), model: getModel(), forceRegenerate: !!force };
      const data = await api(`/api/topics/${encodeURI(state.topicId)}/reading-list`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      state.readingList = data;
      renderDetail();
    } catch (e) {
      renderErrorBox(host, e.message, () => loadReadingList(force));
    }
  }

  function renderExplain(host) {
    const d = state.explain[state.activeTab];
    if (!d) { host.innerHTML = `<div class="error-box">No ${state.activeTab} content in the generated payload.</div>`; return; }

    const regenBtn = `<div style="margin-bottom:16px"><button class="btn-ghost" id="regen-btn">&#8635; Regenerate</button></div>`;

    if (state.activeTab === "advanced") {
      host.innerHTML = `
        ${regenBtn}
        <div class="formal-statement">${d.formalStatement || ""}</div>
        <div class="panel-section" style="margin-top:22px">
          <h2>Key idea / proof sketch</h2>
          <p style="white-space:pre-line">${escapeHtml(d.keyIdeaOrProofSketch)}</p>
        </div>
        <div class="panel-section">
          <h2>Worked example</h2>
          <p style="white-space:pre-line">${escapeHtml(d.workedExample)}</p>
        </div>
        <div class="panel-section">
          <h2>Further context</h2>
          <p style="white-space:pre-line">${escapeHtml(d.furtherContext)}</p>
        </div>
      `;
      document.getElementById("regen-btn").onclick = () => loadExplain(true);
      return;
    }

    const crossDomain = (d.crossDomainExamples || []).map((c) => `
      <div class="cross-domain-card">
        <span class="domain">${escapeHtml(c.domain)}</span>
        <p style="margin:0">${escapeHtml(c.example)}</p>
      </div>`).join("");

    const misconceptions = (d.commonMisconceptions || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("");
    const traps = (d.trapsToAvoid || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("");
    const glossary = (d.glossary || []).map((g) =>
      `<div><span class="glossary-term">${escapeHtml(g.term)}</span><p style="margin:4px 0 0">${escapeHtml(g.definition)}</p></div>`
    ).join("");

    const quiz = d.checkYourself;
    const quizHtml = quiz ? `
      <div class="quiz-box">
        <div class="quiz-question">${escapeHtml(quiz.question)}</div>
        ${(quiz.options || []).map((opt, i) =>
          `<button class="quiz-option" data-i="${i}">${escapeHtml(opt)}</button>`
        ).join("")}
        <div class="quiz-explain" id="quiz-explain">${escapeHtml(quiz.explanation || "")}</div>
      </div>` : "";

    host.innerHTML = `
      ${regenBtn}
      <div class="tldr">${escapeHtml(d.tldr)}</div>
      <div class="panel-section"><p style="white-space:pre-line">${escapeHtml(d.explanation)}</p></div>
      <div class="panel-section">
        <h2>Picture it like this</h2>
        <div class="analogy-box"><span class="tag">Analogy</span>${escapeHtml(d.analogy)}</div>
      </div>
      ${crossDomain ? `<div class="panel-section"><h2>The same idea, elsewhere</h2><div class="cross-domain-grid">${crossDomain}</div></div>` : ""}
      ${misconceptions ? `<div class="panel-section"><h2>Common misconceptions</h2><ul class="list-plain">${misconceptions}</ul></div>` : ""}
      ${traps ? `<div class="panel-section"><h2>Traps to avoid</h2><ul class="list-plain">${traps}</ul></div>` : ""}
      ${glossary ? `<div class="panel-section"><h2>Glossary</h2><div class="glossary-grid">${glossary}</div></div>` : ""}
      ${quizHtml ? `<div class="panel-section"><h2>Check yourself</h2>${quizHtml}</div>` : ""}
    `;

    document.getElementById("regen-btn").onclick = () => loadExplain(true);
    if (quiz) {
      const opts = host.querySelectorAll(".quiz-option");
      opts.forEach((btn) => {
        btn.onclick = () => {
          const i = parseInt(btn.dataset.i, 10);
          opts.forEach((o, j) => o.classList.toggle(j === quiz.correctIndex ? "correct" : "incorrect", j === i || j === quiz.correctIndex));
          document.getElementById("quiz-explain").classList.add("shown");
        };
      });
    }
  }

  function renderReadingList(host) {
    const d = state.readingList;
    const stages = ["Zero / Absolute beginner", "Foundations", "Core", "Advanced", "Research / primary sources"];
    const byStage = {};
    (d.readings || []).forEach((r) => {
      (byStage[r.stage] = byStage[r.stage] || []).push(r);
    });
    const regenBtn = `<div style="margin-bottom:16px"><button class="btn-ghost" id="regen-reading-btn">&#8635; Regenerate</button></div>`;
    const stagesHtml = stages
      .filter((s) => byStage[s] && byStage[s].length)
      .map((s) => `
        <div class="reading-stage">
          <h3>${escapeHtml(s)}</h3>
          ${byStage[s].map((r) => {
            const hasLink = typeof r.url === "string" && /^https?:\/\//.test(r.url);
            const titleHtml = hasLink
              ? `<a class="reading-item-title" href="${escapeAttr(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)} &#8599;</a>`
              : `<span class="reading-item-title">${escapeHtml(r.title)}</span>`;
            return `
            <div class="reading-item">
              ${titleHtml}
              <span class="reading-item-author">${escapeHtml(r.author)}</span>
              <div class="reading-item-about">${escapeHtml(r.about)}</div>
              <div class="reading-item-why">${escapeHtml(r.why)}</div>
            </div>
          `;
          }).join("")}
        </div>
      `).join("");

    host.innerHTML = `
      ${regenBtn}
      <p class="reading-overview">${escapeHtml(d.overview)}</p>
      ${stagesHtml}
    `;
    document.getElementById("regen-reading-btn").onclick = () => loadReadingList(true);
  }

  // Advanced-tab formal statements may include \( \) / \[ \] LaTeX markers;
  // rendered as plain styled text below (no MathJax bundled), still readable.

  // ---------- search ----------
  let searchDebounce = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    const q = searchInput.value.trim();
    if (!q) { searchResults.classList.add("hidden"); return; }
    searchDebounce = setTimeout(async () => {
      const results = await api(`/api/search?q=${encodeURIComponent(q)}`);
      renderSearchResults(results);
    }, 120);
  });
  searchInput.addEventListener("focus", () => {
    if (searchInput.value.trim()) searchResults.classList.remove("hidden");
  });
  document.addEventListener("click", (e) => {
    if (!searchResults.contains(e.target) && e.target !== searchInput) {
      searchResults.classList.add("hidden");
    }
  });

  function renderSearchResults(results) {
    if (!results.length) {
      searchResults.innerHTML = `<div class="search-empty">No topics found.</div>`;
    } else {
      searchResults.innerHTML = results.map((t) => `
        <button class="search-item" data-id="${escapeAttr(t.id)}">
          <div class="search-item-title">${escapeHtml(t.title)}</div>
          <div class="search-item-path">${escapeHtml(t.id.replace(/\//g, " › "))}</div>
        </button>`).join("");
      searchResults.querySelectorAll(".search-item").forEach((item) => {
        item.onclick = () => navigateTo(item.dataset.id);
      });
    }
    searchResults.classList.remove("hidden");
  }

  // ---------- settings ----------
  function openSettings() {
    apiKeyInput.value = getApiKey();
    populateModelSelect();
    modelSelect.value = getModel();
    settingsOverlay.classList.remove("hidden");
  }
  function closeSettings() { settingsOverlay.classList.add("hidden"); }
  function populateModelSelect() {
    modelSelect.innerHTML = state.models.map((m) =>
      `<option value="${m.id}">${m.label} — ${m.tier}</option>`
    ).join("");
  }
  settingsBtn.onclick = openSettings;
  settingsClose.onclick = closeSettings;
  settingsOverlay.onclick = (e) => { if (e.target === settingsOverlay) closeSettings(); };
  settingsSave.onclick = () => {
    localStorage.setItem("mathAtlasApiKey", apiKeyInput.value.trim());
    localStorage.setItem("mathAtlasModel", modelSelect.value);
    closeSettings();
  };

  // ---------- sync ----------
  syncBtn.onclick = async () => {
    syncBtn.disabled = true;
    syncMsg.textContent = "Crawling mathprobvault.com… this can take several minutes.";
    try {
      await api("/api/sync", { method: "POST" });
      pollSync();
    } catch (e) {
      syncMsg.textContent = `Error: ${e.message}`;
      syncBtn.disabled = false;
    }
  };
  async function pollSync() {
    const status = await api("/api/sync/status");
    if (status.status === "running") {
      syncMsg.textContent = `Fetching… ${status.fetched || 0} pages so far`;
      setTimeout(pollSync, 2000);
    } else if (status.status === "done") {
      syncBtn.disabled = false;
      const parts = [];
      if (status.added?.length) parts.push(`${status.added.length} added`);
      if (status.removed?.length) parts.push(`${status.removed.length} removed`);
      if (status.changed?.length) parts.push(`${status.changed.length} changed`);
      syncMsg.textContent = parts.length ? parts.join(", ") : "Already up to date.";
      loadMeta();
    } else if (status.status === "error") {
      syncBtn.disabled = false;
      syncMsg.textContent = `Error: ${status.error}`;
    }
  }

  async function loadMeta() {
    const meta = await api("/api/meta");
    const synced = meta.lastSyncedAt ? new Date(meta.lastSyncedAt).toLocaleString() : "initial build";
    metaLine.textContent = `${meta.topicCount.toLocaleString()} topics · last synced ${synced}`;
  }

  // ---------- init ----------
  homeBtn.onclick = showHome;
  (async () => {
    const modelsResp = await api("/api/models");
    state.models = modelsResp.models;
    state.defaultModel = modelsResp.default;
    await loadMeta();
    await showHome();
  })();
})();
