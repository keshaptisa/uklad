/* Лендинг «Типы локальных экономик России». Данные: window.DATA (site.json), window.GEO (границы МО). */
(() => {
  const D = window.DATA, G = window.GEO, M = D.mo, N = M.id.length, T = D.types, K = D.K;
  const MONTHS = D.months;
  const MN = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const mlabel = (m) => { const [y, mm] = MONTHS[m].split("-"); return `${MN[+mm - 1]} ${y}`; };
  const fmt = (v, d = 0) => v == null || Number.isNaN(v) ? "-" : v.toLocaleString("ru-RU", { maximumFractionDigits: d, minimumFractionDigits: d });
  const fmtP = (v, d = 0) => v == null || v < 0 ? "-" : fmt(v, d);  // показатели, где −1 означает «нет данных»
  const idx = new Map(M.id.map((id, i) => [id, i]));
  const typeAt = (i, m) => +M.tm[i][m];
  const tip = document.getElementById("tip");
  const showTip = (ev, html) => {
    tip.innerHTML = html; tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
    if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  };
  const hideTip = () => { tip.hidden = true; };
  const avg = (a, from = 12) => { const s = a.slice(from); return s.reduce((x, y) => x + y, 0) / s.length; };
  const median = (arr) => { const s = arr.filter((v) => v >= 0).sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };

  // число типов словами - из данных, чтобы текст не расходился с конфигурацией
  const KW = { 4: "четыре", 5: "пять", 6: "шесть", 7: "семь", 8: "восемь", 9: "девять" }[K] || String(K);
  document.querySelectorAll(".kword").forEach((e) => { e.textContent = KW[0].toUpperCase() + KW.slice(1); });
  document.querySelectorAll(".kword-l").forEach((e) => { e.textContent = KW; });
  document.querySelectorAll(".knum").forEach((e) => { e.textContent = K; });

  // ---------- тема ----------
  const root = document.documentElement;
  const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const syncTheme = () => { root.dataset.dark = isDark() ? "1" : "0"; };
  try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch (e) { /* хранилище недоступно */ }
  syncTheme();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncTheme);
  document.getElementById("theme").onclick = () => {
    root.dataset.theme = isDark() ? "light" : "dark"; syncTheme();
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* хранилище недоступно */ }
  };

  // ---------- прокрутка: прогресс, шапка, активный пункт меню, «наверх», появление секций ----------
  const prog = document.getElementById("progress"), top = document.getElementById("top"), toTop = document.getElementById("to-top");
  const navLinks = [...document.querySelectorAll("nav a")];
  const onScroll = () => {
    const h = document.documentElement.scrollHeight - innerHeight;
    prog.style.width = (h > 0 ? scrollY / h * 100 : 0) + "%";
    top.classList.toggle("scrolled", scrollY > 10);
    toTop.classList.toggle("show", scrollY > 700);
  };
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  toTop.onclick = () => scrollTo({ top: 0, behavior: "smooth" });
  if ("IntersectionObserver" in window) {
    const rv = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); rv.unobserve(e.target); } }), { threshold: 0.06 });
    document.querySelectorAll(".reveal").forEach((el) => rv.observe(el));
    const act = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) navLinks.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id));
    }), { rootMargin: "-45% 0px -50% 0px" });
    document.querySelectorAll("section[id]").forEach((el) => act.observe(el));
  } else document.querySelectorAll(".reveal").forEach((el) => el.classList.add("in"));

  // ---------- шапка ----------
  const nRhythm = M.rt.filter((r) => r >= 0).length;
  document.getElementById("hero-stats").innerHTML = [
    [fmt(N), "муниципальных образований с полной историей"], ["24", "месяца безналичных трат, 2023–2024"],
    [String(K), K >= 2 && K <= 4 ? "устойчивых типа экономики" : "устойчивых типов экономики"], [fmt(nRhythm), "МО со своим сезонным ритмом"],
  ].map(([v, l]) => `<div class="stat"><div class="v" data-to="${v.replace(/\s/g, "")}">${v}</div><div class="l">${l}</div></div>`).join("");
  // счётчики в шапке плавно набегают от нуля
  document.querySelectorAll(".stat .v[data-to]").forEach((el) => {
    const to = +el.dataset.to; if (!to || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = performance.now(), dur = 1400;
    const step = (t) => { const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = fmt(Math.round(to * e)); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
    const done = () => { el.textContent = fmt(to); };
    setTimeout(done, dur + 100); addEventListener("beforeprint", done);   // печать и фоновые вкладки не ждут кадров
  });

  // ---------- атлас ----------
  const state = { mode: "type", selT: -1, selR: 2, month: 23, sel: null };
  const svg = d3.select("#map");
  const W = 900, H = 520;
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  // d3 считает внешним кольцом обход по часовой стрелке на сфере; полигон с обратным обходом «закрашивает весь шар».
  // Разворачиваем такие части (площадь больше полушария), чтобы и карта, и подгонка масштаба были верными.
  for (const f of G.features) {
    const g = f.geometry, polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    for (const p of polys) if (d3.geoArea({ type: "Polygon", coordinates: p }) > 2 * Math.PI) p.forEach((ring) => ring.reverse());
  }
  const proj = d3.geoConicEqualArea().parallels([52, 64]).rotate([-100, 0]).fitExtent([[6, 6], [W - 6, H - 6]], G);
  const path = d3.geoPath(proj);
  const feats = G.features.filter((f) => idx.has(f.id));

  // ---------- заставка «Уклад»: зацикленный фон - карта МО из светящихся точек, по связям бегут огоньки ----------
  (() => {
    const intro = document.getElementById("intro");
    if (!intro) return;
    const close = () => {
      intro.classList.add("gone"); document.body.classList.remove("intro-on");
      setTimeout(() => { cancelAnimationFrame(raf); intro.remove(); }, 1200);
    };
    // прямая ссылка на МО или печать - сразу к содержимому
    if (/mo=/.test(location.hash) || matchMedia("print").matches || navigator.webdriver) { intro.remove(); document.body.classList.remove("intro-on"); return; }
    document.getElementById("intro-go").addEventListener("click", close);
    addEventListener("keydown", function k(e) { if (e.key === "Enter" || e.key === "Escape") { removeEventListener("keydown", k); close(); } });
    const cv = document.getElementById("intro-cv"), ctx = cv.getContext("2d");
    const geo = feats.map((f) => [idx.get(f.id), d3.geoCentroid(f)]).filter(([, c]) => Number.isFinite(c[0]));
    const E = D.net ? D.net.e : [];
    const n = geo.length, X = new Float32Array(N), Y = new Float32Array(N), ok = new Uint8Array(N);
    const ph = Float32Array.from({ length: N }, () => Math.random() * 6.283), om = Float32Array.from({ length: N }, () => 0.6 + Math.random() * 1.4);
    let w = 0, h = 0, dpr = 1, raf = 0;
    const fit = () => {
      dpr = Math.min(2, devicePixelRatio || 1); w = innerWidth; h = innerHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      const m = Math.min(w, h) * 0.06;
      const pr = d3.geoConicEqualArea().parallels([52, 64]).rotate([-100, 0])
        .fitExtent([[m, m + h * 0.04], [w - m, h - m]], { type: "MultiPoint", coordinates: geo.map((g) => g[1]) });
      for (const [i, c] of geo) { const p = pr(c); X[i] = p[0]; Y[i] = p[1]; ok[i] = 1; }
    };
    fit(); addEventListener("resize", fit);
    const pulses = [];
    const spawn = (t) => {
      if (!E.length) return;
      const [a, b] = E[(Math.random() * E.length) | 0];
      if (ok[a] && ok[b]) pulses.push({ a, b, t0: t, d: 1200 + Math.random() * 1400 });
    };
    const frame = (ms) => {
      const t = ms / 1000;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      // медленное «дыхание» и дрейф всей карты
      const s = 1 + 0.015 * Math.sin(t * 0.35), cx = w / 2 + 10 * Math.sin(t * 0.13), cy = h / 2 + 6 * Math.cos(t * 0.11);
      ctx.translate(cx, cy); ctx.scale(s, s); ctx.translate(-w / 2, -h / 2);
      while (pulses.length < 26) spawn(ms - Math.random() * 1500);
      ctx.lineWidth = 0.8;
      for (let k = pulses.length - 1; k >= 0; k--) {
        const p = pulses[k], u = (ms - p.t0) / p.d;
        if (u >= 1) { pulses.splice(k, 1); continue; }
        if (u < 0) continue;
        const ax = X[p.a], ay = Y[p.a], bx = X[p.b], by = Y[p.b], fade = Math.sin(Math.PI * u);
        ctx.strokeStyle = `rgba(66, 198, 97, ${0.28 * fade})`; ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
        const qx = ax + (bx - ax) * u, qy = ay + (by - ay) * u;
        const g = ctx.createRadialGradient(qx, qy, 0, qx, qy, 7);
        g.addColorStop(0, `rgba(195, 240, 204, ${0.95 * fade})`); g.addColorStop(1, "rgba(46, 194, 76, 0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(qx, qy, 7, 0, 6.283); ctx.fill();
      }
      const r = Math.max(1, Math.min(2.2, w / 900));
      for (let i = 0; i < N; i++) {
        if (!ok[i]) continue;
        const a = 0.35 + 0.45 * (0.5 + 0.5 * Math.sin(t * om[i] + ph[i]));
        ctx.fillStyle = `rgba(${M.t[i] === 0 ? "195, 240, 204" : "120, 220, 140"}, ${a})`;
        ctx.fillRect(X[i] - r / 2, Y[i] - r / 2, r, r);
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
  })();
  const gMap = svg.append("g");
  const paths = gMap.selectAll("path").data(feats).join("path").attr("class", "mo").attr("d", path);
  // волна: при первом показе карта «прокрашивается» с запада на восток (задержка — по долготе центра МО)
  (() => {
    const svgEl = svg.node();
    if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches || matchMedia("print").matches) return;
    const xs = feats.map((f) => path.centroid(f)[0]), x0 = d3.min(xs), x1 = d3.max(xs);
    paths.each(function (f, i) { this.style.setProperty("--d", `${(((xs[i] - x0) / (x1 - x0 || 1)) * 1.6 + Math.random() * 0.25).toFixed(2)}s`); });
    svgEl.classList.add("wave-wait");
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { io.disconnect(); svgEl.classList.replace("wave-wait", "wave-go"); setTimeout(() => svgEl.classList.remove("wave-go"), 2600); } }, { threshold: 0.25 });
    io.observe(svgEl);
  })();
  svg.call(d3.zoom().scaleExtent([1, 12]).translateExtent([[0, 0], [W, H]]).on("zoom", (e) => gMap.attr("transform", e.transform)));

  const insets = [["#inset-msk", "Москва"], ["#inset-spb", "Санкт-Петербург"]].map(([sel, reg]) => {
    const fs = feats.filter((f) => M.region[idx.get(f.id)] === reg);
    const s = d3.select(sel).attr("viewBox", "0 0 300 150");
    const pr = d3.geoMercator().fitExtent([[4, 4], [296, 146]], { type: "FeatureCollection", features: fs });
    return s.selectAll("path").data(fs).join("path").attr("class", "mo").attr("d", d3.geoPath(pr));
  });
  const allPaths = () => [paths, ...insets];

  // траты: квантильные границы по месяцу
  const spendBins = MONTHS.map((_, m) => d3.quantile(M.spend.map((s) => s[m]).sort(d3.ascending), 0) !== undefined
    ? [0.2, 0.4, 0.6, 0.8, 0.95].map((q) => d3.quantile(M.spend.map((s) => s[m]).sort(d3.ascending), q)) : []);
  const fillOf = (i) => {
    const m = state.month;
    if (state.mode === "type") return state.selT < 0 ? `var(--t${typeAt(i, m)})` : typeAt(i, m) === state.selT ? "var(--accent)" : "var(--base)";
    if (state.mode === "rhythm") return M.rt[i] === state.selR ? "var(--accent)" : M.rt[i] >= 0 ? "var(--seq-1)" : "var(--base)";
    const b = spendBins[m], v = M.spend[i][m];
    const k = b.findIndex((x) => v <= x);
    return `var(--seq-${k < 0 ? 5 : k})`;
  };
  const paint = () => {
    for (const p of allPaths()) p.style("fill", (f) => fillOf(idx.get(f.id))).classed("sel", (f) => idx.get(f.id) === state.sel);
    document.getElementById("month-label").textContent = mlabel(state.month);
    legend();
  };
  const legend = () => {
    const el = document.getElementById("map-legend");
    if (state.mode === "spend") {
      const b = spendBins[state.month].map((v) => fmt(v * 10));
      const labs = [`≤ ${b[0]}`, `≤ ${b[1]}`, `≤ ${b[2]}`, `≤ ${b[3]}`, `≤ ${b[4]}`, `> ${b[4]}`];
      el.innerHTML = "Траты на жителя, ₽/мес, " + mlabel(state.month) + ": " +
        labs.map((l, k) => `<span><i class="sw" style="background:var(--seq-${k})"></i>${l}</span>`).join("");
    } else if (state.mode === "type" && state.selT < 0) {
      el.innerHTML = T.map((t) => `<span><i class="sw" style="background:var(--t${t.k})"></i>${t.name} - ${fmt(M.tm.filter((s) => +s[state.month] === t.k).length)}</span>`).join("") +
        `<span class="muted">- число МО в выбранном месяце (${mlabel(state.month)}); в кнопках над картой - по типологии за два года в целом. Нажмите тип, чтобы выделить его</span>`;
    } else if (state.mode === "type") {
      const n = M.tm.filter((s) => +s[state.month] === state.selT).length;
      el.innerHTML = `<span><i class="sw" style="background:var(--accent)"></i>${T[state.selT].name} - ${fmt(n)} МО в ${mlabel(state.month)}</span>` +
        `<span><i class="sw" style="background:var(--base)"></i>остальные типы</span><span class="muted">белым - нет полной истории трат или региона нет в данных СберИндекса</span>`;
    } else {
      el.innerHTML = `<span><i class="sw" style="background:var(--accent)"></i>${D.rhythm.names[state.selR]}</span>` +
        `<span><i class="sw" style="background:var(--seq-1)"></i>другой собственный ритм</span><span><i class="sw" style="background:var(--base)"></i>общероссийский ритм</span>`;
    }
  };
  const chips = () => {
    const el = document.getElementById("chips");
    if (state.mode === "type") {
      el.innerHTML = `<button class="chip ${state.selT < 0 ? "on" : ""}" data-k="-1">Все типы</button>` +
        T.map((t) => `<button class="chip ${t.k === state.selT ? "on" : ""}" data-k="${t.k}"><i class="dot" style="background:var(--t${t.k})"></i>${t.name}<span class="n">${t.n}</span></button>`).join("");
      el.querySelectorAll("button").forEach((b) => b.onclick = () => { state.selT = +b.dataset.k; chips(); paint(); });
    } else if (state.mode === "rhythm") {
      el.innerHTML = Object.entries(D.rhythm.names).map(([k, n]) => `<button class="chip ${+k === state.selR ? "on" : ""}" data-k="${k}">${n}<span class="n">${D.rhythm.n[k]}</span></button>`).join("");
      el.querySelectorAll("button").forEach((b) => b.onclick = () => { state.selR = +b.dataset.k; chips(); paint(); });
    } else el.innerHTML = "";
  };
  document.querySelectorAll("#mode button").forEach((b) => b.onclick = () => {
    document.querySelectorAll("#mode button").forEach((x) => x.classList.toggle("on", x === b));
    state.mode = b.dataset.m; chips(); paint();
  });
  const hover = (ev, f) => {
    const i = idx.get(f.id), m = state.month;
    showTip(ev, `<div class="t">${M.name[i]}</div><div class="s">${M.region[i]}</div>` +
      `<div>${T[typeAt(i, m)].name}</div><div class="s">траты ${fmt(M.spend[i][m] * 10)} ₽ на жителя, ${mlabel(m)}</div>` +
      (M.rt[i] >= 0 ? `<div class="s">ритм: ${D.rhythm.names[M.rt[i]]}</div>` : ""));
  };
  for (const p of allPaths()) p.on("mousemove", hover).on("mouseleave", hideTip).on("click", (ev, f) => select(idx.get(f.id)));

  const monthIn = document.getElementById("month");
  monthIn.oninput = () => { state.month = +monthIn.value; paint(); };
  let timer = null;
  document.getElementById("play").onclick = (e) => {
    if (timer) { clearInterval(timer); timer = null; e.target.textContent = "▶"; return; }
    e.target.textContent = "❚❚";
    if (state.month === 23) state.month = -1;
    timer = setInterval(() => {
      state.month += 1; monthIn.value = state.month; paint();
      if (state.month >= 23) { clearInterval(timer); timer = null; e.target.textContent = "▶"; }
    }, 450);
  };

  // поиск
  document.getElementById("mo-list").innerHTML = M.name.map((n, i) => `<option value="${n} - ${M.region[i]}">`).join("");
  document.getElementById("search").onchange = (e) => {
    const [n, r] = e.target.value.split(" - ");
    const i = M.name.findIndex((x, j) => x === n && (!r || M.region[j] === r));
    if (i >= 0) select(i);
  };

  // паспорт МО
  const nat = {
    food: median(M.food.map((a) => avg(a))), cafe: median(M.cafe.map((a) => avg(a))), market: median(M.market.map((a) => avg(a))),
    spend: median(M.spend.map((a) => avg(a))), wage: median(M.wage), pop: median(M.pop), urban: median(M.urban), access: median(M.access),
    emp: [0, 1, 2, 3, 4, 5].map((k) => median(M.emp.map((e) => e[k]))),
  };
  const EMP = ["сельское хозяйство", "добыча", "промышленность", "транспорт", "рыночные услуги", "бюджетный сектор"];
  function select(i) {
    state.sel = i; paint();
    const t = T[M.t[i]];
    const rows = [
      ["Траты на жителя, ₽/мес (2024)", fmt(avg(M.spend[i]) * 10), fmt(nat.spend * 10)],
      ["Доля продовольствия, %", fmt(avg(M.food[i]) / 10, 1), fmt(nat.food / 10, 1)],
      ["Доля общепита, %", fmt(avg(M.cafe[i]) / 10, 1), fmt(nat.cafe / 10, 1)],
      ["Доля маркетплейсов, %", fmt(avg(M.market[i]) / 10, 1), fmt(nat.market / 10, 1)],
      ["Зарплата, ₽", fmtP(M.wage[i]), fmt(nat.wage)],
      ["Население", fmtP(M.pop[i]), fmt(nat.pop)],
      ["Доля горожан, %", fmtP(M.urban[i]), fmt(nat.urban)],
      ["Доступность рынков", fmtP(M.access[i]), fmt(nat.access)],
    ];
    const strip = M.tm[i].split("").map((c, m) => `<i class="${+c === M.t[i] ? "cur" : "alt"}" title="${mlabel(m)}: ${T[+c].name}"></i>`).join("");
    const changed = new Set(M.tm[i].split("")).size > 1;
    const emp = M.emp[i].map((v, k) => `<div class="bar-row"><span>${EMP[k]}</span><div class="track"><div class="fill" style="width:${Math.max(0, v)}%"></div>` +
      `<div class="nat" style="left:${nat.emp[k]}%"></div></div><span>${v < 0 ? "-" : v + "%"}</span></div>`).join("");
    const el = document.getElementById("passport");
    el.innerHTML = `<h3>${M.name[i]}</h3><div class="muted">${M.region[i]} · ${M.kind[i]}</div>
      <div class="badge">${t.name}</div>${M.rt[i] >= 0 ? ` <span class="muted">· ритм: ${D.rhythm.names[M.rt[i]]}</span>` : ""}
      <div class="kv"><span></span><span class="muted" style="text-align:right">МО</span><span class="muted" style="text-align:right">Россия</span>
      ${rows.map(([k, v, n]) => `<span class="k">${k}</span><span class="v">${v}</span><span class="d">${n}</span>`).join("")}</div>
      <h3 style="font-size:14px;margin-top:10px">Траты на жителя по месяцам</h3><svg id="spark" viewBox="0 0 320 120"></svg>
      <h3 style="font-size:14px;margin-top:10px">Тип по месяцам ${changed ? `- ${M.kind[i] === "направленный" ? "сменил тип насовсем" : "сезонные качели, вернулся"}` : "- не менялся"}</h3><div class="strip">${strip}</div>
      <div class="muted" style="font-size:12px">${mlabel(0)} → ${mlabel(23)}${changed ? "; красным - месяцы в другом типе (наведите)" : ""}</div>
      <h3 style="font-size:14px;margin-top:10px">Структура занятости <span class="muted" style="font-weight:400">(черта - медиана по России)</span></h3>${emp}
      ${M.citywide[i] ? `<p class="muted" style="font-size:12px">Занятость и зарплата - по городу целиком (Росстат считает работников по месту работы).</p>` : ""}
      <h3 style="font-size:14px;margin-top:10px">Экономические двойники из других регионов</h3>
      ${M.twins[i].map((j) => `<button class="twin" data-j="${j}">${M.name[j]} - ${M.region[j]}</button>`).join("")}`;
    el.querySelectorAll(".twin").forEach((b) => b.onclick = () => select(+b.dataset.j));
    spark(i);
  }
  function spark(i) {
    const s = d3.select("#spark"), w = 320, h = 120, m = { l: 52, r: 14, t: 8, b: 20 };
    const ys = M.spend[i].map((v) => v * 10), ns = D.natSpend;
    const y = d3.scaleLinear().domain([0, d3.max([...ys, ...ns]) * 1.08]).range([h - m.b, m.t]);
    const x = d3.scaleLinear().domain([0, 23]).range([m.l, w - m.r]);
    s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickFormat((v) => fmt(v / 1000) + " тыс."));
    s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).tickValues([0, 12, 23]).tickFormat(mlabel));
    const line = d3.line().x((_, k) => x(k)).y((v) => y(v));
    s.append("path").attr("d", line(ns)).attr("fill", "none").style("stroke", "var(--muted)").attr("stroke-width", 2).attr("stroke-dasharray", "4 3");
    s.append("path").attr("d", line(ys)).attr("fill", "none").style("stroke", "var(--accent)").attr("stroke-width", 2);
    s.append("text").attr("class", "lbl").attr("x", w - m.r).attr("y", y(ns[23]) + 14).attr("text-anchor", "end").text("медиана России");
  }

  // ---------- карточки типов ----------
  const LAB = { spend: "траты", share_food: "доля продовольствия", share_cafe: "доля общепита", share_market: "доля маркетплейсов",
    wage: "зарплата", population: "население", urban_share: "доля горожан", market_access: "доступность рынков",
    emp_agro: "занятость в сельском хозяйстве", emp_mining: "занятость в добыче", emp_industry: "занятость в промышленности",
    emp_transport: "занятость в транспорте", emp_market_services: "занятость в рыночных услугах", emp_public: "занятость в бюджетном секторе" };
  const ruFormula = (s) => s.split(" И ").map((p) => { const [k, v] = p.split(": "); return v ? `${LAB[k] || k} - ${v}` : (LAB[k] || k); }).join(" и ");
  document.getElementById("cards").classList.add("stagger"); document.getElementById("cards").innerHTML = T.map((t) => `
    <div class="card" data-k="${t.k}"><h3>${t.name}</h3><div class="muted">${fmt(t.n)} МО</div><p>${t.short}</p>
      <div class="nums"><div><b>${fmt(t.med.spend)} ₽</b><span>траты на жителя</span></div>
        <div><b>${fmt(t.med.wage)} ₽</b><span>зарплата</span></div><div><b>${fmt(t.med.share_cafe, 1)}%</b><span>доля общепита</span></div></div>
      ${t.fca[0] ? `<div class="formula"><b>Формула типа:</b> ${ruFormula(t.fca[0].d)}<br>точность ${fmt(t.fca[0].p * 100)}%, покрытие ${fmt(t.fca[0].c * 100)}%, устойчивость ${fmt(t.fca[0].s, 2)}</div>` : ""}
      <p class="muted" style="font-size:12px">Крупнейшие: ${t.largest}</p></div>`).join("");
  document.querySelectorAll(".card").forEach((c) => c.onclick = () => {
    state.mode = "type"; state.selT = +c.dataset.k;
    document.querySelectorAll("#mode button").forEach((x) => x.classList.toggle("on", x.dataset.m === "type"));
    chips(); paint(); document.getElementById("atlas").scrollIntoView();
  });

  // ---------- ландшафт Энгеля ----------
  (() => {
    const s = d3.select("#engel-svg"), w = 900, h = 440, m = { l: 54, r: 16, t: 14, b: 40 };
    s.attr("viewBox", `0 0 ${w} ${h}`);
    const allS = M.spend.flat().map((v) => v * 10), allF = M.food.flat().map((v) => v / 10);
    const x = d3.scaleLog().domain([d3.quantile(allS.slice().sort(d3.ascending), 0.002), d3.max(allS)]).range([m.l, w - m.r]).clamp(true);
    const y = d3.scaleLinear().domain([d3.min(allF) - 1, d3.max(allF) + 1]).range([h - m.b, m.t]);
    s.append("g").attr("class", "gridl").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickSize(-(w - m.l - m.r)).tickFormat(""));
    s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickFormat((v) => v + "%"));
    s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).ticks(6, "~s").tickFormat((v) => fmt(v / 1000) + " тыс."));
    s.append("text").attr("class", "lbl").attr("x", w - m.r).attr("y", h - 6).attr("text-anchor", "end").text("траты на жителя в месяц, ₽ (лог. шкала) →");
    s.append("text").attr("class", "lbl").attr("x", m.l + 6).attr("y", m.t + 10).text("↑ доля продовольствия в тратах");
    const monthTxt = s.append("text").attr("x", w - m.r - 4).attr("y", m.t + 34).attr("text-anchor", "end").style("fill", "var(--axis)").style("font-size", "40px").style("font-weight", "700");
    const st = { m: 0, k: -1 };
    const dots = s.append("g").selectAll("circle").data(d3.range(N)).join("circle").attr("r", 2.6);
    const traj = s.append("path").attr("fill", "none").style("stroke", "var(--ink)").attr("stroke-width", 2);
    const trajDot = s.append("circle").attr("r", 5).style("fill", "var(--ink)").style("stroke", "var(--surface)").attr("stroke-width", 2);
    const draw = (dur) => {
      const mm = st.m;
      dots.style("fill", (i) => st.k < 0 ? "var(--accent)" : M.t[i] === st.k ? "var(--accent)" : "var(--base)")
        .style("opacity", (i) => st.k < 0 ? 0.45 : M.t[i] === st.k ? 0.85 : 0.5)
        .sort((a, b) => (M.t[a] === st.k) - (M.t[b] === st.k))
        .transition().duration(dur).attr("cx", (i) => x(M.spend[i][mm] * 10)).attr("cy", (i) => y(M.food[i][mm] / 10));
      if (st.k >= 0) {
        const ids = d3.range(N).filter((i) => M.t[i] === st.k);
        const pts = d3.range(mm + 1).map((t) => [x(d3.median(ids, (i) => M.spend[i][t] * 10)), y(d3.median(ids, (i) => M.food[i][t] / 10))]);
        traj.attr("d", d3.line()(pts)).style("display", null);
        trajDot.attr("cx", pts[mm][0]).attr("cy", pts[mm][1]).style("display", null);
      } else { traj.style("display", "none"); trajDot.style("display", "none"); }
      monthTxt.text(mlabel(mm));
      document.getElementById("engel-label").textContent = mlabel(mm);
    };
    dots.on("mousemove", (ev, i) => showTip(ev, `<div class="t">${M.name[i]}</div><div class="s">${M.region[i]}</div><div>${T[M.t[i]].name}</div>` +
      `<div class="s">${fmt(M.spend[i][st.m] * 10)} ₽ · еда ${fmt(M.food[i][st.m] / 10, 1)}%</div>`)).on("mouseleave", hideTip)
      .on("click", (ev, i) => { select(i); document.getElementById("atlas").scrollIntoView(); });
    const ch = document.getElementById("engel-chips");
    ch.innerHTML = `<button class="chip on" data-k="-1">Все МО</button>` + T.map((t) => `<button class="chip" data-k="${t.k}">${t.name}</button>`).join("");
    ch.querySelectorAll("button").forEach((b) => b.onclick = () => {
      st.k = +b.dataset.k; ch.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); draw(0);
    });
    const inp = document.getElementById("engel-month");
    inp.oninput = () => { st.m = +inp.value; draw(250); };
    let tm = null;
    document.getElementById("engel-play").onclick = (e) => {
      if (tm) { clearInterval(tm); tm = null; e.target.textContent = "▶"; return; }
      e.target.textContent = "❚❚"; if (st.m === 23) st.m = -1;
      tm = setInterval(() => { st.m += 1; inp.value = st.m; draw(380); if (st.m >= 23) { clearInterval(tm); tm = null; e.target.textContent = "▶"; } }, 420);
    };
    draw(0);
  })();

  // ---------- часы ритма ----------
  (() => {
    const el = document.getElementById("clocks");
    const ML = ["Я", "Ф", "М", "А", "М", "И", "И", "А", "С", "О", "Н", "Д"];
    for (const [k, name] of Object.entries(D.rhythm.names)) {
      const div = document.createElement("div"); div.className = "clock";
      div.innerHTML = `<h3>${name} <span class="muted" style="font-weight:400">· ${D.rhythm.n[k]} МО</span></h3><svg viewBox="-130 -130 260 260"></svg><p>${D.rhythm.short[k]}</p>
        <p class="muted" style="font-size:12px"><span class="sw" style="background:var(--accent)"></span>все траты <span class="sw" style="background:var(--muted);margin-left:8px"></span>общепит</p>`;
      el.appendChild(div);
      const s = d3.select(div.querySelector("svg"));
      const r = d3.scaleLinear().domain([-35, 45]).range([22, 118]).clamp(true);
      const ang = (mm) => (mm / 12) * 2 * Math.PI;
      for (const v of [-20, 0, 20, 40]) s.append("circle").attr("r", r(v)).attr("fill", "none").style("stroke", v === 0 ? "var(--axis)" : "var(--grid)").attr("stroke-width", v === 0 ? 1.5 : 1);
      for (const v of [-20, 20, 40]) s.append("text").attr("class", "lbl").attr("x", 3).attr("y", -r(v) + 10).style("font-size", "9px").text((v > 0 ? "+" : "") + v + "%");
      ML.forEach((l, mm) => s.append("text").attr("class", "lbl").attr("x", Math.sin(ang(mm)) * 124).attr("y", -Math.cos(ang(mm)) * 124 + 4).attr("text-anchor", "middle").style("font-size", "10px").text(l));
      const line = d3.lineRadial().angle((_, mm) => ang(mm)).radius((v) => r(v)).curve(d3.curveCardinalClosed.tension(0.3));
      const P = D.rhythm.profiles[k];
      s.append("path").attr("d", line(P.cafe)).attr("fill", "none").style("stroke", "var(--muted)").attr("stroke-width", 1.5);
      s.append("path").attr("d", line(P.total)).attr("fill", "none").style("stroke", "var(--accent)").attr("stroke-width", 2.5);
    }
  })();

  // ---------- динамика ----------
  (() => {
    const sw = d3.range(1, 24).map((m) => M.tm.filter((s) => s[m] !== s[m - 1]).length);
    const s = d3.select("#switch-svg"), w = 520, h = 240, m = { l: 40, r: 8, t: 10, b: 40 };
    s.attr("viewBox", `0 0 ${w} ${h}`);
    const x = d3.scaleBand().domain(d3.range(1, 24)).range([m.l, w - m.r]).padding(0.25);
    const y = d3.scaleLinear().domain([0, Math.max(5, d3.max(sw))]).nice().range([h - m.b, m.t]);
    s.append("g").attr("class", "gridl").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickSize(-(w - m.l - m.r)).tickFormat(""));
    s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4));
    s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).tickValues([1, 6, 12, 18, 23]).tickFormat(mlabel));
    s.selectAll("rect").data(sw).join("rect").attr("x", (_, k) => x(k + 1)).attr("width", x.bandwidth())
      .attr("y", (v) => y(v)).attr("height", (v) => y(0) - y(v)).attr("rx", 2).style("fill", "var(--accent)")
      .on("mousemove", (ev, v) => showTip(ev, `${mlabel(sw.indexOf(v) + 1)}: ${v} МО сменили тип`)).on("mouseleave", hideTip);

    // потоки: январь 2023 → декабрь 2024
    const C = d3.range(K).map(() => d3.range(K).fill(0));
    for (let i = 0; i < N; i++) C[+M.tm[i][0]][+M.tm[i][23]] += 1;
    const f = d3.select("#flow-svg"), fw = 700, fh = 360, pad = 4, colW = 14, xL = 245, xR = fw - 245;
    f.attr("viewBox", `0 0 ${fw} ${fh}`);
    const tot = N, scale = (fh - pad * (K - 1) - 10) / tot;
    const left = [], right = []; let yl = 5, yr = 5;
    for (let k = 0; k < K; k++) {
      const a = d3.sum(C[k]), b = d3.sum(C, (row) => row[k]);
      left.push({ y: yl, h: a * scale, off: 0 }); right.push({ y: yr, h: b * scale, off: 0 });
      yl += a * scale + pad; yr += b * scale + pad;
    }
    const links = [];
    for (let a = 0; a < K; a++) for (let b = 0; b < K; b++) if (C[a][b] > 0) {
      const hh = C[a][b] * scale, y0 = left[a].y + left[a].off, y1 = right[b].y + right[b].off;
      left[a].off += hh; right[b].off += hh; links.push({ a, b, n: C[a][b], y0, y1, hh });
    }
    const mid = (xL + colW + xR) / 2;
    f.append("g").selectAll("path").data(links).join("path")
      .attr("d", (l) => `M${xL + colW},${l.y0}C${mid},${l.y0} ${mid},${l.y1} ${xR},${l.y1}L${xR},${l.y1 + l.hh}C${mid},${l.y1 + l.hh} ${mid},${l.y0 + l.hh} ${xL + colW},${l.y0 + l.hh}Z`)
      .style("fill", (l) => l.a === l.b ? "var(--base)" : "var(--warm)").style("opacity", (l) => l.a === l.b ? 0.55 : 0.85)
      .on("mousemove", (ev, l) => showTip(ev, l.a === l.b ? `${T[l.a].name}: остались ${l.n} МО` : `${T[l.a].name} → ${T[l.b].name}: ${l.n} МО`)).on("mouseleave", hideTip);
    for (const [arr, xx, anchor, dx] of [[left, xL, "end", -6], [right, xR, "start", colW + 6]]) {
      arr.forEach((n, k) => {
        f.append("rect").attr("x", xx).attr("y", n.y).attr("width", colW).attr("height", Math.max(1, n.h)).attr("rx", 2).style("fill", "var(--accent)");
        f.append("text").attr("class", "lbl").attr("x", xx + dx).attr("y", n.y + n.h / 2 + 4).attr("text-anchor", anchor).style("font-size", "11px").text(T[k].name);
      });
    }
    const moved = N - d3.sum(d3.range(K), (k) => C[k][k]);
    f.append("text").attr("class", "lbl").attr("x", fw / 2).attr("y", fh - 2).attr("text-anchor", "middle")
      .text(`красным - ${moved} МО (${fmt(moved / N * 100, 1)}%) в другом типе через два года`);

    if (D.directed) {
      const S = D.trSummary;
      document.getElementById("dir-lead").innerHTML = `Из ${S.mo_with_switches} МО, менявших тип, <b>${S.directed} сменили его насовсем</b>,
        ${S.returning} вернулись в свой тип. У направленных переходов медианное изменение относительного уровня трат - ${fmt(S.directed_level_change_median_pct, 1)}%
        (у всех МО - ${fmt(S.all_level_change_median_pct, 1)}%): вверх по лестнице типов идут те, чьи траты растут быстрее страны.
        В таблице - все направленные переходы с примерами; нажмите на МО на карте, чтобы увидеть его траекторию.`;
      const rows = D.directed.map((r) => `<tr><td>${r.type_start} → ${r.type_end}</td><td>${r.n}</td><td>${(r.level_change_pct > 0 ? "+" : "") + fmt(r.level_change_pct, 1)}%</td><td style="text-align:left;white-space:normal">${r.examples}</td></tr>`).join("");
      document.getElementById("dir-table").innerHTML = `<div class="tbl"><table><thead><tr><th>Переход</th><th>МО</th><th>изменение уровня трат</th><th style="text-align:left">примеры</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }
    if (D.synthetic) {
      const cal = D.synthetic.filter((r) => r["сценарий"] === "калиброванный");
      const rows = cal.map((r) => `<tr class="${r["вариант"].includes("0.5") ? "hl" : ""}"><td>${r["вариант"]}</td><td>${fmt(r["ложные смены (не мигранты)"], 2)}</td>
        <td>${fmt(r["мигранты найдены через 0 мес."] * 100)}%</td><td>${fmt(r["мигранты найдены через 2 мес."] * 100)}%</td><td>${fmt(r["мигранты найдены через 4 мес."] * 100)}%</td></tr>`).join("");
      document.getElementById("dyn-table").insertAdjacentHTML("beforebegin", `<h3 style="margin-top:18px">Проверка на синтетике с известной истиной</h3>
        <p class="sub">Типы и шум откалиброваны по реальным данным; в 12-м месяце 5% МО по-настоящему меняют тип. Без памяти метод не отличает переход от шума;
        память α = 0,5 находит 84% настоящих переходов за два месяца и почти не даёт ложных.</p>
        <div class="tbl"><table><thead><tr><th>Способ</th><th>ложных смен на МО за 24 мес.</th><th>переходы найдены сразу</th><th>через 2 мес.</th><th>через 4 мес.</th></tr></thead><tbody>${rows}</tbody></table></div>
        <h3 style="margin-top:18px">Способы отслеживания на реальных данных</h3>`);
    }
    if (D.dynVariants) {
      const V = D.dynVariants, col = (c) => V.columns.indexOf(c);
      const rows = V.data.map((r, j) => `<tr class="${V.index[j].startsWith("эволюционный") && V.index[j].includes("0.5") ? "hl" : ""}"><td>${V.index[j]}</td>
        <td>${fmt(r[col("AMI_adjacent")], 3)}</td><td>${fmt(r[col("switch_rate_month")] * 100, 2)}%</td><td>${fmt(r[col("never_switch")] * 100, 1)}%</td>
        <td>${fmt(r[col("persistent_switches")])}</td><td>${fmt(r[col("SW_median")], 3)}</td><td>${fmt(r[col("MQ_median")], 3)}</td><td>${fmt(r[col("K")])}</td></tr>`).join("");
      document.getElementById("dyn-table").innerHTML = `<div class="tbl"><table><thead><tr><th>Способ отслеживания типов</th><th>AMI соседних месяцев</th>
        <th>смен в месяц</th><th>МО без смен</th><th>устойчивых переходов</th><th>SW (медиана)</th><th>MQ (медиана)</th><th>типов</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }
  })();

  // ---------- качество ----------
  (() => {
    if (D.methods && D.methodsRaw) {
      const R = D.methods, raw = D.methodsRaw, ci = (t, c) => t.columns.indexOf(c);
      const crit = [["SW", 1], ["CH", 1], ["S_Dbw", -1], ["AVI", 1], ["AVU", -1], ["MQ", 1], ["bootstrap_ARI", 1]];
      const val = (name, c) => raw.data[raw.index.indexOf(name)][ci(raw, c)];
      const best = Object.fromEntries(crit.map(([c, s]) => [c, R.index.map((n) => val(n, c)).reduce((a, b) => (s > 0 ? Math.max(a, b) : Math.min(a, b)))]));
      const rows = R.index.map((n, j) => `<tr class="${n === D.mainMethod ? "hl" : ""}"><td>${n}</td><td>${R.data[j][ci(R, "rank_threshold")]}</td><td>${R.data[j][ci(R, "rank_borda")]}</td>
        ${crit.map(([c]) => `<td class="${val(n, c) === best[c] ? "best" : ""}">${fmt(val(n, c), c === "CH" ? 0 : 3)}</td>`).join("")}</tr>`).join("");
      document.getElementById("methods-table").innerHTML = `<div class="tbl"><table><thead><tr><th>Метод (K = ${K})</th><th>место, Алескеров</th><th>место, Борда</th>
        <th>SW ↑</th><th>CH ↑</th><th>S_Dbw ↓</th><th>AVI ↑</th><th>AVU ↓</th><th>MQ ↑</th><th>бутстрап ↑</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }
    if (D.methodsZ && D.methodsRaw) {
      const Z = D.methodsZ, raw = D.methodsRaw, zc = (c) => Z.columns.indexOf(c);
      const fam = (n) => (n.includes("GNN") ? ["графовая нейросеть", "var(--t2)"] : n.includes("признаки+сеть") ? ["признаки + сеть", "var(--accent)"]
        : n.includes("(сеть)") ? ["только сеть", "var(--t3)"] : ["только признаки", "var(--t1)"]);
      // каждый индекс нормируем на максимум |z| по методам, иначе CH (z ~ 10³) заглушает остальные
      const zmax = Object.fromEntries(Z.columns.map((c) => [c, d3.max(Z.data, (r) => Math.abs(r[zc(c)])) || 1]));
      const mean = (r, cs) => cs.reduce((a, c) => a + r[zc(c)] / zmax[c], 0) / cs.length;
      const pts = Z.index.map((n, j) => ({ n, x: mean(Z.data[j], ["SW", "CH", "S_Dbw"]), y: mean(Z.data[j], ["AVI", "AVU", "MQ"]),
        b: raw.data[raw.index.indexOf(n)][raw.columns.indexOf("bootstrap_ARI")], f: fam(n) }));
      const s = d3.select("#pareto-svg"), w = 760, h = 360, m = { l: 52, r: 20, t: 14, b: 42 };
      s.attr("viewBox", `0 0 ${w} ${h}`);
      const pad = (e) => [e[0] - (e[1] - e[0]) * 0.12, e[1] + (e[1] - e[0]) * 0.12];
      const x = d3.scaleLinear().domain(pad(d3.extent(pts, (p) => p.x))).range([m.l, w - m.r]);
      const y = d3.scaleLinear().domain(pad(d3.extent(pts, (p) => p.y))).range([h - m.b, m.t]);
      s.append("g").attr("class", "gridl").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - m.l - m.r)).tickFormat(""));
      s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5));
      s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).ticks(6));
      s.append("text").attr("class", "lbl").attr("x", w - m.r).attr("y", h - 8).attr("text-anchor", "end").text("качество в признаках (средняя z, доля от лучшего) →");
      s.append("text").attr("class", "lbl").attr("x", m.l + 6).attr("y", m.t + 10).text("↑ качество в сети");
      const r = d3.scaleLinear().domain([0.5, 1]).range([4, 15]).clamp(true);
      const g = s.selectAll(null).data(pts).join("g").attr("transform", (p) => `translate(${x(p.x)},${y(p.y)})`);
      g.append("circle").style("fill", (p) => p.f[1]).style("fill-opacity", 0.75)
        .style("stroke", (p) => (p.n === D.mainMethod ? "var(--ink)" : "none")).attr("stroke-width", 2.5)
        .on("mousemove", (ev, p) => showTip(ev, `<b>${p.n}</b><br>признаки ${fmt(p.x, 2)} · сеть ${fmt(p.y, 2)} (доля от лучшего)<br>бутстрап ARI ${fmt(p.b, 2)}`))
        .on("mouseleave", hideTip).attr("r", (p) => r(p.b));
      // подписи: соседние по экрану точки разводим по вертикали
      const lab = pts.map((p) => ({ p, y: y(p.y) })).sort((a, b) => x(a.p.x) - x(b.p.x));
      lab.forEach((a, i) => lab.slice(0, i).forEach((b) => {
        if (Math.abs(x(a.p.x) - x(b.p.x)) < 110 && Math.abs(a.y - b.y) < 15) a.y = b.y + (a.y >= b.y ? 15 : -15);
      }));
      const dy = new Map(lab.map((a) => [a.p.n, a.y - y(a.p.y)]));
      g.append("text").attr("class", "lbl").attr("x", (p) => r(p.b) + 4).attr("y", (p) => 4 + dy.get(p.n)).text((p) => p.n.replace(/ \(.*\)$/, ""))
        .style("font-weight", (p) => (p.n === D.mainMethod ? 700 : 400));
      const fams = [...new Map(pts.map((p) => [p.f[0], p.f[1]])).entries()];
      d3.select(s.node().parentNode).append("div").attr("class", "legend")
        .html(fams.map(([l, c]) => `<span><i class="sw" style="background:${c}"></i>${l}</span>`).join("") +
          `<span class="muted">обводка - основной метод; крупнее - устойчивее</span>`);
    }
    if (D.chooseK) {
      const C = D.chooseK, ci = (c) => C.columns.indexOf(c), rows = C.data;
      const s = d3.select("#k-svg"), w = 520, h = 260, m = { l: 40, r: 12, t: 12, b: 36 };
      s.attr("viewBox", `0 0 ${w} ${h}`);
      const x = d3.scaleLinear().domain(d3.extent(rows, (r) => r[ci("K")])).range([m.l, w - m.r]);
      const y = d3.scaleLinear().domain([0.45, 1]).range([h - m.b, m.t]);
      s.append("g").attr("class", "gridl").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(w - m.l - m.r)).tickFormat(""));
      s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5));
      s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).ticks(8).tickFormat((v) => "K=" + v));
      s.append("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0.75)).attr("y2", y(0.75)).style("stroke", "var(--muted)").attr("stroke-dasharray", "4 3");
      for (const [c, color, lab] of [["boot_ARI", "var(--accent)", "всё разбиение (бутстрап ARI)"], ["hennig_min", "var(--ink-2)", "худший тип (Жаккар Хеннига)"]]) {
        const pts = rows.map((r) => [x(r[ci("K")]), y(r[ci(c)])]);
        s.append("path").attr("d", d3.line()(pts)).attr("fill", "none").style("stroke", color).attr("stroke-width", 2);
        s.selectAll(null).data(rows).join("circle").attr("cx", (r) => x(r[ci("K")])).attr("cy", (r) => y(r[ci(c)])).attr("r", 4).style("fill", color)
          .on("mousemove", (ev, r) => showTip(ev, `K=${r[ci("K")]}: ${lab} ${fmt(r[ci(c)], 3)}`)).on("mouseleave", hideTip);
      }
      d3.select(s.node().parentNode).append("div").attr("class", "legend")
        .html(`<span><i class="sw" style="background:var(--accent)"></i>всё разбиение (бутстрап ARI)</span>` +
          `<span><i class="sw" style="background:var(--ink-2)"></i>худший тип (Жаккар Хеннига)</span><span class="muted">вертикаль - выбранное K</span>`);
      s.append("text").attr("class", "lbl").attr("x", m.l + 4).attr("y", y(0.75) + 14).text("порог устойчивости 0,75");
      s.append("line").attr("x1", x(K)).attr("x2", x(K)).attr("y1", m.t).attr("y2", h - m.b).style("stroke", "var(--accent)").attr("stroke-width", 1);
    }
    if (D.edges) {
      const E = D.edges, ci = (c) => E.columns.indexOf(c);
      const RU = { cosine: "косинус профиля трат", rbf: "гауссово ядро", corr: "корреляция рядов", lagcorr: "лаговая корреляция (±2 мес.)",
        dtw: "DTW траекторий (основное)", road: "близость по дорогам", context: "сходство экономической базы", snf: "слияние SNF: траты + база + дороги" };
      const rows = E.index.map((r, j) => `<tr class="${r === "dtw" ? "hl" : ""}"><td>${RU[r] || r}</td><td>${fmt(E.data[j][ci("within_region")] * 100)}%</td>
        <td>${fmt(E.data[j][ci("homoph_log_wage")], 2)}</td><td>${fmt(E.data[j][ci("homoph_level")], 2)}</td><td>${fmt(E.data[j][ci("leiden_Q")], 2)}</td></tr>`).join("");
      document.getElementById("edges-table").innerHTML = `<div class="tbl" style="margin-top:0"><table><thead><tr><th>Правило</th><th>внутри региона</th>
        <th title="корреляция зарплаты на концах рёбер">соседи ≈ по зарплате</th><th title="корреляция уровня трат на концах рёбер">≈ по тратам</th><th title="модулярность Leiden">Q</th></tr></thead><tbody>${rows}</tbody></table></div>
        <p class="muted" style="font-size:12px">Зарплата не участвует в рёбрах - и всё же соседи по тратам похожи по зарплате. Дороги дают «типы = регионы».</p>`;
    }
  })();

  // ---------- скачать CSV ----------
  document.getElementById("dl-csv").onclick = () => {
    if (!D.csvTypes) return;
    const url = URL.createObjectURL(new Blob(["﻿" + D.csvTypes], { type: "text/csv;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "mo_types.csv" });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  // ---------- отпечатки типов ----------
  if (D.fingerprint) {
    const F = D.fingerprint, nc = F.columns.length;
    const cell = (v) => {
      const a = Math.min(1, Math.abs(v) / 2) * 75;
      const col = v >= 0 ? "var(--accent)" : "var(--warm)";
      return `<div class="c" style="background:color-mix(in srgb, ${col} ${a.toFixed(0)}%, var(--surface-2))">${Math.abs(v) >= 0.5 ? fmt(v, 1) : ""}</div>`;
    };
    let html = `<div class="fp" style="grid-template-columns: minmax(180px,1.4fr) repeat(${nc}, minmax(40px,1fr))"><div></div>` +
      F.columns.map((c) => `<div class="h">${c}</div>`).join("");
    F.index.forEach((t, j) => { html += `<div class="r">${t}</div>` + F.data[j].map(cell).join(""); });
    const el = document.getElementById("fingerprint");
    const sc = [-2, -1, 0, 1, 2].map((v) => `<span><i class="sw" style="background:${cell(v).match(/background:([^"]+)/)[1]}"></i>${v > 0 ? "+" : ""}${v} σ</span>`).join("");
    el.innerHTML = html + `</div><div class="legend">Медиана типа относительно медианы России: ${sc}<span class="muted">числа показаны, если отличие больше 0,5 σ</span></div>`;
    el.querySelectorAll(".c").forEach((c, i) => {
      const j = Math.floor(i / nc), k = i % nc, v = F.data[j][k];
      c.onmousemove = (ev) => showTip(ev, `<div class="t">${F.index[j]}</div><div class="s">${F.columns[k]}: ${v > 0 ? "+" : ""}${fmt(v, 2)} σ к медиане России</div>`);
      c.onmouseleave = hideTip;
    });
  }

  // ---------- кто уходит в отрыв ----------
  if (D.divergence && D.divSummary) {
    const V = D.divergence, S = D.divSummary, months = V.index;
    const types = V.columns.filter((c) => !c.startsWith("σ") && !c.startsWith("η"));
    const sgn2 = (v) => (v > 0 ? "+" : "") + fmt(v, 1);
    const sp = (a, b) => `${a > 0 ? "+" : ""}${fmt(a, 0)}% → ${b > 0 ? "+" : ""}${fmt(b, 0)}%`;
    const top = S.top_type, bot = S.bottom_type;
    document.getElementById("gap-lead").innerHTML = `Экономический тип - это ещё и уровень жизни. Тип «${top}» тратит на жителя
      ${sp(S.gap_pct_2023[top], S.gap_pct_2024[top])} к медиане страны (2023 → 2024), а тип «${bot}» - ${sp(S.gap_pct_2023[bot], S.gap_pct_2024[bot])}.
      Разрыв между полюсами за год ${S.spread_2024 > S.spread_2023 ? "вырос" : "сократился"} с ${fmt(S.spread_2023, 0)} до ${fmt(S.spread_2024, 0)} п. п.:
      ${S.spread_2024 > S.spread_2023 ? "<b>богатые типы уходят в отрыв</b>, а бедные их не догоняют" : "<b>типы сближаются</b>"}${S.spread_change_ci95 ? ` (95% бутстрап-интервал изменения: от ${sgn2(S.spread_change_ci95[0])} до ${sgn2(S.spread_change_ci95[1])} п. п. - рост небольшой, но значимый)` : ""}.`;
    const narrow = document.getElementById("gap-svg").getBoundingClientRect().width < 480;
    const s = d3.select("#gap-svg"), w = narrow ? 360 : 560, h = narrow ? 260 : 300, m = { l: 44, r: narrow ? 10 : 160, t: 12, b: 28 };
    s.attr("viewBox", `0 0 ${w} ${h}`);
    const x = d3.scaleLinear().domain([0, months.length - 1]).range([m.l, w - m.r]);
    const all = V.data.flatMap((r) => types.map((t) => r[V.columns.indexOf(t)]));
    const y = d3.scaleLinear().domain(d3.extent(all)).nice().range([h - m.b, m.t]);
    s.append("g").attr("class", "gridl").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickSize(-(w - m.l - m.r)).tickFormat(""));
    s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickFormat((v) => (v > 0 ? "+" : "") + v + "%"));
    s.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).tickValues([0, 6, 12, 18, 23]).tickFormat((i) => mlabel(i)));
    s.append("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0)).attr("y2", y(0)).style("stroke", "var(--axis)").attr("stroke-width", 1.5);
    const order = types.slice().sort((a, b) => S.gap_pct_2024[b] - S.gap_pct_2024[a]);
    const shade = (t) => `var(--seq-${Math.max(1, 5 - order.indexOf(t))})`;
    const lines = types.map((t) => {
      const ci = V.columns.indexOf(t), pts = V.data.map((r, i) => [x(i), y(r[ci])]);
      const p = s.append("path").attr("d", d3.line().curve(d3.curveMonotoneX)(pts)).attr("fill", "none").style("stroke", shade(t)).attr("stroke-width", 2.5);
      const L = p.node().getTotalLength();
      p.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L);
      const lab = s.append("text").attr("class", "lbl").style("display", narrow ? "none" : null).attr("x", w - m.r + 6).attr("y", pts[pts.length - 1][1] + 4).text(t.length > 24 ? t.slice(0, 23) + "…" : t);
      return { t, p, lab, pts };
    });
    lines.forEach((o) => s.append("path").attr("d", d3.line()(o.pts)).attr("fill", "none").style("stroke", "transparent").attr("stroke-width", 14)
      .on("mousemove", (ev) => { lines.forEach((q) => q.p.style("opacity", q.t === o.t ? 1 : 0.2)); showTip(ev, `<div class="t">${o.t}</div><div class="s">2023: ${fmt(S.gap_pct_2023[o.t], 1)}% · 2024: ${fmt(S.gap_pct_2024[o.t], 1)}% к медиане России</div>`); })
      .on("mouseleave", () => { lines.forEach((q) => q.p.style("opacity", 1)); hideTip(); }));
    // подписи справа не налезают друг на друга
    const labs = lines.map((o) => ({ o, y: +o.lab.attr("y") })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < labs.length; i++) if (labs[i].y - labs[i - 1].y < 13) labs[i].y = labs[i - 1].y + 13;
    labs.forEach((l) => l.o.lab.attr("y", l.y));
    if (narrow) d3.select(s.node().parentNode).append("div").attr("class", "legend")
      .html(order.map((t) => `<span><i class="sw" style="background:${shade(t)}"></i>${t}</span>`).join(""));
    const draw = () => lines.forEach((o, i) => o.p.transition().delay(i * 120).duration(1600).ease(d3.easeCubicOut).attr("stroke-dashoffset", 0));
    if ("IntersectionObserver" in window && !matchMedia("print").matches) {
      const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { draw(); io.disconnect(); } }, { threshold: 0.3 });
      io.observe(s.node());
    } else draw();
    addEventListener("beforeprint", () => lines.forEach((o) => o.p.interrupt().attr("stroke-dashoffset", 0)));
    const pct = (v) => fmt(v * 100, 1) + "%";
    document.getElementById("gap-stats").innerHTML = `
      <div class="g"><div class="v">${fmt(S.spread_2023, 0)}<span class="arrow">→</span>${fmt(S.spread_2024, 0)} п. п.</div><div class="l">разрыв между самым богатым и самым бедным типом, 2023 → 2024</div></div>
      <div class="g"><div class="v">${fmt(S.sigma_2023, 3)}<span class="arrow">→</span>${fmt(S.sigma_2024, 3)}</div><div class="l">разброс трат между МО (σ логарифма): ${S.sigma_2024 > S.sigma_2023 ? "растёт - неравенство между муниципалитетами усиливается" : "падает - муниципалитеты сближаются"}</div></div>
      <div class="g"><div class="v">${pct(S.eta2_2023)}<span class="arrow">→</span>${pct(S.eta2_2024)}</div><div class="l">доля разброса трат, которую объясняет тип (η²): почти три четверти неравенства - между типами, а не внутри них</div></div>`;
  }

  // ---------- варианты рейтинга ----------
  if (D.rankVariants) {
    const V = D.rankVariants, vc = V.columns.slice(0, 8);
    const tint = (r) => r === 1 ? "background:var(--accent);color:var(--on-accent)" : r <= 3 ? "background:var(--accent-soft);color:var(--accent-2)" : "color:var(--muted)";
    const rows = V.index.map((n, j) => `<tr class="${n === D.mainMethod ? "hl" : ""}"><td>${n}</td>` +
      vc.map((c, k) => `<td style="text-align:center"><span class="var-cell" style="${tint(V.data[j][k])}">${V.data[j][k]}</span></td>`).join("") +
      `<td>${V.data[j][V.columns.indexOf("первых мест")]} из 8</td></tr>`).join("");
    const head = vc.map((c) => `<th style="text-align:center;white-space:normal;min-width:84px">${c.replace(": ", "<br>")}</th>`).join("");
    document.getElementById("variants-table").innerHTML = `<div class="tbl"><table><thead><tr><th>Метод</th>${head}<th>первых мест</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // ---------- истории МО: все числа считаются из данных ----------
  const byName = (n) => M.name.indexOf(n);
  const goTo = (i) => {
    state.mode = "type"; state.selT = M.t[i];
    document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("on", b.dataset.m === "type"));
    chips(); select(i);
    document.getElementById("atlas").scrollIntoView({ behavior: "smooth" });
  };
  const EMPI = { agro: 0, mining: 1, industry: 2, transport: 3, market: 4, public: 5 };
  const switchAt = (i) => { const s = M.tm[i]; for (let m = 1; m < 24; m++) if (s[m] !== s[m - 1]) return m; return -1; };
  const yearAvg = (a, y) => avg(a.slice(y * 12, y * 12 + 12), 0);
  const rel = (i) => [0, 1].map((y) => (yearAvg(M.spend[i], y) * 10 / avg(D.natSpend.slice(y * 12, y * 12 + 12), 0) - 1) * 100);
  const times = (a, b) => { const r = a / b; return r >= 1.95 ? `в ${fmt(r, r < 10 ? 1 : 0)} раза` : `на ${fmt((r - 1) * 100, 0)}%`; };
  const sgn = (v, d = 0) => (v > 0 ? "+" : "") + fmt(v, d);
  const STORIES = [
    ["Красноярск", "Ступенька вверх", (i) => {
      const m = switchAt(i), r = rel(i);
      return `Миллионник с заводами (${M.emp[i][EMPI.industry]}% занятых в промышленности) в ${mlabel(m)} перешёл из «промышленных городов»
        в «центры услуг» и больше не возвращался. Траты на жителя - ${sgn(r[1])}% к медиане страны в 2024 году, и разрыв растёт
        (${sgn(r[0])}% годом раньше): город тратит всё больше, как центры услуг.`;
    }],
    ["Тайгинский", "Сеть находит своих", (i) => {
      const tw = M.twins[i], et = tw.map((j) => M.emp[j][EMPI.transport]);
      return `В транспорте занято ${M.emp[i][EMPI.transport]}% работников - ${times(M.emp[i][EMPI.transport], nat.emp[EMPI.transport])} больше медианы страны:
        станция Тайга на Транссибе. Сеть по тратам сама нашла ему «двойников» в других регионах - ${tw.map((j) => M.name[j]).join(", ")}:
        у них в транспорте ${d3.min(et)}–${d3.max(et)}% занятых. Пока транспорт был частью «услуг», такие МО терялись среди столиц.`;
    }],
    ["Анадырь", "Арктический июль", (i) => {
      const s = M.spend[i], c = M.cafe[i];
      const jul = ((s[6] + s[18]) / 2 / avg(s, 0) - 1) * 100, cj = ((c[6] + c[18]) / 2 / avg(c, 0) - 1) * 100;
      return `Зарплата ${fmt(M.wage[i])} ₽ - ${times(M.wage[i], nat.wage)} выше медианы страны. У самого Анадыря в июле траты на ${fmt(jul, 0)}% выше
        среднего месяца, а доля общепита в корзине - на ${fmt(cj, 0)}%. По всем ${D.rhythm.n[M.rt[i]]} МО арктического ритма продукты в июле почти не растут -
        это не северный завоз, а приток людей: навигация, вахты, возвращение из отпусков.`;
    }],
    ["Сургут", "Из ресурсного - в центр услуг", (i) => {
      const m = switchAt(i);
      return `Нефтяная столица: ${M.emp[i][EMPI.mining]}% занятых в добыче, зарплата ${fmt(M.wage[i])} ₽. По двум годам в целом - ресурсный тип,
        но с ${mlabel(m)} город держится в «центрах услуг»: рыночные услуги - уже ${M.emp[i][EMPI.market]}% занятых
        (медиана страны ${fmt(nat.emp[EMPI.market], 0)}%). Ближайшие двойники - ${M.twins[i].slice(0, 2).map((j) => M.name[j]).join(" и ")}.`;
    }],
    ["Чурапчинский", "Гипотеза, которую мы отвергли", (i) => `Улус Якутии с августовским пиком трат. Мы ждали, что это сезон добычи, - но в добыче
      здесь занято ${M.emp[i][EMPI.mining]}% работников, а в бюджетном секторе - ${M.emp[i][EMPI.public]}%. По всем ${D.rhythm.n[M.rt[i]]} МО этого ритма в августе
      растут общепит и здоровье, а продукты - нет: тот же след летнего притока людей, что у Арктики. Так мы проверяем каждую трактовку.`],
  ];
  document.getElementById("stories").innerHTML = STORIES.map(([n, title, f]) => {
    const i = byName(n); if (i < 0) return "";
    return `<article class="story"><div class="story-k">${title}</div><h3>${M.name[i]}</h3><div class="muted">${M.region[i]} · ${T[M.t[i]].name}</div>
      <p>${f(i)}</p><button class="link-btn" data-i="${i}">Показать на карте <span class="arr">→</span></button></article>`;
  }).join("");
  document.querySelectorAll("#stories .link-btn").forEach((b) => b.onclick = () => goTo(+b.dataset.i));

  // ---------- сравнение двух МО ----------
  const findMO = (v) => { const n = v.split(" - ")[0].trim(); const i = M.name.indexOf(n); return i; };
  const cmp = { a: byName("Красноярск"), b: byName("Новосибирск") };
  function compare() {
    const { a, b } = cmp; if (a < 0 || b < 0) return;
    const row = (lab, f, d = 0, unit = "") => {
      const va = f(a), vb = f(b), mx = Math.max(Math.abs(va), Math.abs(vb)) || 1;
      return `<div class="cmp-row"><div class="cmp-v l"><span>${fmt(va, d)}${unit}</span><i style="width:${(Math.abs(va) / mx * 60).toFixed(1)}%"></i></div>
        <div class="cmp-lab">${lab}</div><div class="cmp-v r"><i style="width:${(Math.abs(vb) / mx * 60).toFixed(1)}%"></i><span>${fmt(vb, d)}${unit}</span></div></div>`;
    };
    const head = (i) => `<div class="cmp-head"><h3>${M.name[i]}</h3><div class="muted">${M.region[i]}</div><div class="badge">${T[M.t[i]].name}</div></div>`;
    document.getElementById("cmp-out").innerHTML = `<div class="cmp-heads">${head(a)}<div></div>${head(b)}</div>` +
      row("траты на жителя, ₽", (i) => avg(M.spend[i]) * 10) + row("зарплата, ₽", (i) => Math.max(0, M.wage[i])) +
      row("население", (i) => Math.max(0, M.pop[i])) + row("доля продовольствия", (i) => avg(M.food[i]) / 10, 1, "%") +
      row("доля общепита", (i) => avg(M.cafe[i]) / 10, 1, "%") + row("доля маркетплейсов", (i) => avg(M.market[i]) / 10, 1, "%") +
      EMP.map((lab, k) => row("занятость: " + lab, (i) => Math.max(0, M.emp[i][k]), 0, "%")).join("") +
      `<p class="muted" style="text-align:center;font-size:13px;margin:12px 0 0">${M.t[a] === M.t[b] ? "Один тип" : "Разные типы"}${M.twins[a].includes(b) || M.twins[b].includes(a) ? " · экономические двойники" : ""}</p>`;
  }
  ["a", "b"].forEach((k) => {
    const inp = document.getElementById("cmp-" + k);
    inp.value = cmp[k] >= 0 ? `${M.name[cmp[k]]} - ${M.region[cmp[k]]}` : "";
    inp.onchange = () => { const i = findMO(inp.value); if (i >= 0) { cmp[k] = i; compare(); } };
  });
  document.getElementById("cmp-swap").onclick = () => {
    [cmp.a, cmp.b] = [cmp.b, cmp.a];
    ["a", "b"].forEach((k) => { document.getElementById("cmp-" + k).value = `${M.name[cmp[k]]} - ${M.region[cmp[k]]}`; });
    compare();
  };
  compare();

  // ---------- ссылка на МО: #mo=<id> ----------
  const selectRaw = select;
  select = (i) => {
    selectRaw(i);
    try { history.replaceState(null, "", "#mo=" + M.id[i]); } catch (e) { /* file:// в некоторых браузерах */ }
  };
  document.getElementById("share-mo").onclick = async () => {
    if (state.sel == null) return;
    const url = location.href.split("#")[0] + "#mo=" + M.id[state.sel], btn = document.getElementById("share-mo");
    try { await navigator.clipboard.writeText(url); btn.textContent = "Ссылка скопирована"; } catch (e) { btn.textContent = "#mo=" + M.id[state.sel]; }
    setTimeout(() => { btn.textContent = "Скопировать ссылку на МО"; }, 2000);
  };

  // ---------- словарь: подсказки к терминам ----------
  const GLOSS = {
    "KEFRiN": "Метод Шалилеха и Миркина: k-means, который одновременно приближает и признаки МО, и его связи в сети.",
    "DTW": "Динамическое выравнивание рядов: сравнивает форму двух рядов трат, допуская сдвиги во времени.",
    "ICVI": "Внутренние индексы качества кластеризации: считаются без «правильного ответа», по самим данным и сети.",
    "SW": "Силуэт: насколько МО ближе к своему типу, чем к соседнему (−1…1, больше - лучше).",
    "CH": "Индекс Калински–Харабаша: отношение разброса между типами к разбросу внутри типов.",
    "S_Dbw": "Индекс Халкиди: разброс внутри типов плюс плотность на границах между ними (меньше - лучше).",
    "AVI": "Изолированность: доля связей МО, ведущих внутрь своего типа.",
    "AVU": "Слитость: насколько пары типов связаны между собой (меньше - лучше).",
    "MQ": "Модулярность: насколько внутри типов связей больше, чем было бы случайно.",
    "бутстрап": "Повторяем кластеризацию на случайных 80% МО и смотрим, сохраняются ли типы.",
    "Хеннига": "Критерий Хеннига: тип устойчив, если на подвыборках находится похожий (Жаккар > 0,75).",
    "η²": "Доля разброса показателя, которую объясняет принадлежность к типу (0…100%).",
    "эволюционная кластеризация": "Каждый месяц кластеризация начинается с прошлого разбиения и учитывает историю, поэтому шум не выдаётся за смену типа.",
    "Алескерова": "Пороговое агрегирование: метод с провалом по одному индексу не может «купить» место успехами по другим.",
    "Борда": "Сумма мест по всем индексам - простое правило, рядом для сравнения.",
    "закон Энгеля": "Чем выше доход, тем меньшая доля трат уходит на еду.",
    "σ": "Стандартное отклонение логарифма трат между МО: мера неравенства.",
  };
  const done = new Set();
  const walker = document.createTreeWalker(document.querySelector("main") || document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => n.parentElement.closest("script,style,svg,button,.term,h1,h2,nav,.tip,table,#glossary,.fp") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(^|[^\\p{L}_])(${Object.keys(GLOSS).sort((a, b) => b.length - a.length).map(esc).join("|")})(?![\\p{L}_])`, "iu");
  const gkey = (w) => Object.keys(GLOSS).find((k) => k.toLowerCase() === w.toLowerCase());
  for (let q = 0; q < nodes.length; q++) {
    const n = nodes[q];
    let m = null, from = 0;
    for (;;) {                                    // первое ещё не размеченное вхождение термина в этом куске текста
      const mm = n.nodeValue.slice(from).match(re); if (!mm) break;
      if (!done.has(gkey(mm[2]))) { m = mm; m.index += from; break; }
      from += mm.index + mm[0].length;
    }
    if (!m) continue;
    done.add(gkey(m[2]));
    const at = m.index + m[1].length, after = n.splitText(at); after.nodeValue = after.nodeValue.slice(m[2].length);
    const span = document.createElement("span"); span.className = "term"; span.textContent = m[2]; span.tabIndex = 0;
    n.parentNode.insertBefore(span, after);
    nodes.push(after);                            // в остатке текста могут быть другие термины
    const show = (ev) => showTip(ev.clientX ? ev : { clientX: span.getBoundingClientRect().left, clientY: span.getBoundingClientRect().bottom },
      `<div class="t">${gkey(m[2])}</div><div class="s">${GLOSS[gkey(m[2])]}</div>`);
    span.onmousemove = show; span.onfocus = show; span.onmouseleave = hideTip; span.onblur = hideTip;
  }
  document.getElementById("glossary").innerHTML = Object.entries(GLOSS).map(([k, v]) => `<div class="gl"><b>${k}</b><span>${v}</span></div>`).join("");

  // ---------- сеть: карта ↔ граф ----------
  if (D.net) (() => {
    const box = document.getElementById("net-box"), cv = document.getElementById("net-cv"), ctx = cv.getContext("2d");
    const NS = D.net.summary, E = D.net.e;
    const geoXY = new Array(N).fill(null);
    for (const f of feats) { const c = path.centroid(f); if (Number.isFinite(c[0])) geoXY[idx.get(f.id)] = [c[0] / W, c[1] / H]; }
    const netXY = D.net.xy;
    const adj = Array.from({ length: N }, () => []);
    for (const [a, b] of E) { adj[a].push(b); adj[b].push(a); }
    let tMorph = 0, target = 0, hoverI = -1, w = 0, h = 0, dpr = 1, raf = 0;
    const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    let col = [];
    const readColors = () => { col = d3.range(K).map((k) => cssVar(`--t${k}`)); };
    const ease = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    const P = new Float32Array(N * 2);
    const place = () => {
      const e = ease(tMorph), pad = 18;
      const sx = (v) => pad + v * (w - 2 * pad), sy = (v) => pad + v * (h - 2 * pad);
      for (let i = 0; i < N; i++) {
        const g = geoXY[i] || netXY[i], n = netXY[i];
        P[2 * i] = sx(g[0] + (n[0] - g[0]) * e); P[2 * i + 1] = sy(g[1] + (n[1] - g[1]) * e);
      }
    };
    const draw = () => {
      place(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      const e = ease(tMorph);
      if (e > 0.02) {                                   // рёбра проявляются по мере перехода к сети
        ctx.globalAlpha = 0.10 * e; ctx.strokeStyle = cssVar("--ink"); ctx.lineWidth = 0.6; ctx.beginPath();
        for (const [a, b] of E) { ctx.moveTo(P[2 * a], P[2 * a + 1]); ctx.lineTo(P[2 * b], P[2 * b + 1]); }
        ctx.stroke();
      }
      ctx.globalAlpha = hoverI >= 0 ? 0.25 : 0.9;
      const r = Math.max(1.6, Math.min(3, w / 380));
      for (let k = 0; k < K; k++) {
        ctx.fillStyle = col[k]; ctx.beginPath();
        for (let i = 0; i < N; i++) if (M.t[i] === k) { ctx.moveTo(P[2 * i] + r, P[2 * i + 1]); ctx.arc(P[2 * i], P[2 * i + 1], r, 0, 6.2832); }
        ctx.fill();
      }
      if (hoverI >= 0) {
        ctx.globalAlpha = 0.9; ctx.strokeStyle = cssVar("--ink"); ctx.lineWidth = 1.2; ctx.beginPath();
        for (const j of adj[hoverI]) { ctx.moveTo(P[2 * hoverI], P[2 * hoverI + 1]); ctx.lineTo(P[2 * j], P[2 * j + 1]); }
        ctx.stroke(); ctx.globalAlpha = 1;
        for (const i of [hoverI, ...adj[hoverI]]) {
          ctx.fillStyle = col[M.t[i]]; ctx.beginPath(); ctx.arc(P[2 * i], P[2 * i + 1], i === hoverI ? r * 2.6 : r * 1.8, 0, 6.2832); ctx.fill();
          ctx.strokeStyle = cssVar("--surface"); ctx.lineWidth = 1.5; ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
    };
    const animate = () => {
      cancelAnimationFrame(raf);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) { tMorph = target; draw(); return; }
      const t0 = performance.now(), from = tMorph, dur = 1800;
      const step = (t) => { const p = Math.max(0, Math.min(1, (t - t0) / dur)); tMorph = from + (target - from) * p; draw(); if (p < 1) raf = requestAnimationFrame(step); };
      raf = requestAnimationFrame(step);
    };
    const resize = () => {
      w = box.clientWidth; h = Math.round(Math.min(620, Math.max(360, w * 0.62))); dpr = window.devicePixelRatio || 1;
      cv.width = w * dpr; cv.height = h * dpr; cv.style.width = w + "px"; cv.style.height = h + "px"; readColors(); draw();
    };
    new ResizeObserver(resize).observe(box);
    new MutationObserver(() => { readColors(); draw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const btns = document.querySelectorAll("#net-mode button");
    btns.forEach((b) => b.onclick = () => { btns.forEach((x) => x.classList.toggle("on", x === b)); target = +b.dataset.t; animate(); });
    const nearest = (mx, my) => {
      let best = -1, bd = 144;
      for (let i = 0; i < N; i++) { const dx = P[2 * i] - mx, dy = P[2 * i + 1] - my, dd = dx * dx + dy * dy; if (dd < bd) { bd = dd; best = i; } }
      return best;
    };
    cv.onmousemove = (ev) => {
      const r = cv.getBoundingClientRect(), i = nearest(ev.clientX - r.left, ev.clientY - r.top);
      if (i !== hoverI) { hoverI = i; draw(); }
      if (i >= 0) showTip(ev, `<div class="t">${M.name[i]}</div><div class="s">${M.region[i]} · ${T[M.t[i]].name}</div>` +
        `<div class="s" style="margin-top:4px">сильнейшие связи: ${adj[i].slice(0, 4).map((j) => M.name[j] + (M.region[j] !== M.region[i] ? ` (${M.region[j]})` : "")).join(", ")}</div>`);
      else hideTip();
    };
    cv.onmouseleave = () => { hoverI = -1; hideTip(); draw(); };
    cv.onclick = () => { if (hoverI >= 0) goTo(hoverI); };
    document.getElementById("net-legend").innerHTML = T.map((t) => `<span><i class="sw" style="background:var(--t${t.k})"></i>${t.name}</span>`).join("");
    const pc = (v) => fmt(v * 100, 0) + "%";
    document.getElementById("net-stats").innerHTML = [
      [fmt(NS.edges), "связей между МО (у каждого 15 ближайших по траекториям трат)"],
      [pc(NS.same_region), "связей внутри одного региона - остальные пересекают границы"],
      [fmt(NS.dist_median_km) + " км", "медианная длина связи; " + pc(NS.dist_over_1000_share) + " длиннее 1 000 км"],
      [pc(NS.same_type), "связей внутри одного типа - сеть и типы согласованы, но не совпадают"],
    ].map(([v, l]) => `<div class="g"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
    // автоматический переход в «сеть», когда блок впервые появился на экране
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { io.disconnect(); setTimeout(() => btns[1].click(), 700); } }, { threshold: 0.5 });
      io.observe(box);
    }
  })();

  // открыть МО из адреса страницы
  const hm = location.hash.match(/mo=(\d+)/);
  const fromHash = hm ? M.id.indexOf(+hm[1]) : -1;

  chips(); paint();
  if (fromHash >= 0) { state.selT = M.t[fromHash]; chips(); selectRaw(fromHash); setTimeout(() => document.getElementById("atlas").scrollIntoView(), 300); }
  else selectRaw(M.name.indexOf("Якутск") >= 0 ? M.name.indexOf("Якутск") : 0);
})();

// ---------- «дорогие» микровзаимодействия: заголовки по словам, наклон карточек, параллакс, блик ----------
(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches || matchMedia("print").matches;
  if (still) return;
  // заголовки разделов: слова выезжают из-под маски по очереди
  document.querySelectorAll("section h2").forEach((h) => {
    if (h.closest(".intro") || h.dataset.split || h.children.length) return;  // заголовки с разметкой внутри не трогаем
    h.dataset.split = 1;
    const words = h.textContent.trim().split(/\s+/);
    h.innerHTML = words.map((w, i) => `<span class="w"><span style="transition-delay:${(i * 0.06).toFixed(2)}s">${w}</span></span>`).join(" ");
    h.classList.add("split");
  });
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("on"); io.unobserve(e.target); } }), { threshold: 0.4 });
  document.querySelectorAll("h2.split").forEach((h) => io.observe(h));

  // карточки: лёгкий 3D-наклон за курсором и световое пятно
  const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (fine) {
    const sel = ".card, .stat, .chart-box, .author-card, .steps > li";
    document.addEventListener("pointermove", (e) => {
      const el = e.target.closest && e.target.closest(sel);
      if (!el) return;
      const r = el.getBoundingClientRect(), px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
      el.style.setProperty("--mx", `${(px * 100).toFixed(1)}%`); el.style.setProperty("--my", `${(py * 100).toFixed(1)}%`);
      if (!el.matches(".chart-box")) el.style.transform = `perspective(900px) rotateX(${((0.5 - py) * 5).toFixed(2)}deg) rotateY(${((px - 0.5) * 6).toFixed(2)}deg) translateY(-2px)`;
    }, { passive: true });
    document.addEventListener("pointerout", (e) => {
      const el = e.target.closest && e.target.closest(sel);
      if (el && !el.contains(e.relatedTarget)) el.style.transform = "";
    }, { passive: true });
  }

  // параллакс: свечение первого экрана и фоновые пятна уезжают медленнее страницы
  const hero = document.querySelector(".hero");
  let ticking = false;
  addEventListener("scroll", () => {
    if (ticking) return; ticking = true;
    requestAnimationFrame(() => { if (hero) hero.style.setProperty("--py", `${Math.min(scrollY, 900) * 0.35}px`); ticking = false; });
  }, { passive: true });
})();

