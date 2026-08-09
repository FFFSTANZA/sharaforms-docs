/* ============================================================
   SharaForms Docs — site scripts
   Theme, mobile nav, search, code copy, scrollspy.
   Vanilla JS, no dependencies.
   ============================================================ */
(function () {
  "use strict";

  /* ---------- theme ---------- */
  var root = document.documentElement;
  var THEME_KEY = "sf-docs-theme";

  var themeToggle = document.querySelector(".theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    });
  }

  /* ---------- mobile nav ---------- */
  var burger = document.querySelector(".nav-burger");
  var sidebar = document.querySelector(".sidebar");
  var scrim = document.querySelector(".scrim");
  function closeNav() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    if (scrim) scrim.classList.remove("open");
    if (burger) burger.setAttribute("aria-expanded", "false");
  }
  if (burger && sidebar) {
    burger.addEventListener("click", function () {
      var open = sidebar.classList.toggle("open");
      if (scrim) scrim.classList.toggle("open", open);
      burger.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  if (scrim) scrim.addEventListener("click", closeNav);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeNav();
  });

  /* ---------- sidebar search ---------- */
  var search = document.getElementById("nav-search");
  var nav = document.getElementById("nav");
  if (search && nav) {
    var links = Array.prototype.slice.call(nav.querySelectorAll(".nav a"));
    var groups = Array.prototype.slice.call(nav.querySelectorAll(".nav-group"));

    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      var any = false;
      links.forEach(function (a) {
        var hit = !q || (a.textContent || "").toLowerCase().indexOf(q) !== -1;
        a.style.display = hit ? "" : "none";
        if (hit) any = true;
      });
      groups.forEach(function (g) {
        var hits = Array.prototype.slice.call(g.querySelectorAll(".nav a"))
          .filter(function (a) { return a.style.display !== "none"; }).length;
        g.dataset.empty = hits === 0 ? "true" : "false";
      });
      nav.dataset.empty = any ? "false" : "true";
    });

    document.addEventListener("keydown", function (e) {
      var tag = (document.activeElement && document.activeElement.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        search.focus();
        search.select();
      }
    });
  }

  /* ---------- code copy ---------- */
  document.querySelectorAll(".codeblock").forEach(function (block) {
    var head = block.querySelector(".code-head");
    var pre = block.querySelector("pre");
    if (!head || !pre) return;

    var copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.type = "button";
    copyBtn.innerHTML =
      '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2"/></svg><span>Copy</span>';
    copyBtn.setAttribute("aria-label", "Copy code");
    head.appendChild(copyBtn);

    copyBtn.addEventListener("click", function () {
      var text = pre.innerText || pre.textContent || "";
      var done = function () {
        copyBtn.classList.add("copied");
        copyBtn.querySelector("span").textContent = "Copied!";
        setTimeout(function () {
          copyBtn.classList.remove("copied");
          copyBtn.querySelector("span").textContent = "Copy";
        }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
      } else { fallbackCopy(text); done(); }
    });
  });

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
  }

  /* ---------- scrollspy TOC ---------- */
  var tocCol = document.querySelector(".toc-col");
  if (tocCol) {
    var tocLinks = Array.prototype.slice.call(tocCol.querySelectorAll("a[href^='#']"));
    var headings = tocLinks
      .map(function (a) {
        var el = document.getElementById(a.getAttribute("href").slice(1));
        return el ? { link: a, el: el } : null;
      })
      .filter(Boolean);
    if (headings.length && "IntersectionObserver" in window) {
      var spy = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          headings.forEach(function (h) {
            var on = h.el === entry.target;
            h.link.classList.toggle("active", on);
          });
          var active = headings.find(function (h) { return h.link.classList.contains("active"); });
          if (active && active.link.scrollIntoView) {
            active.link.scrollIntoView({ block: "nearest" });
          }
        });
      }, { rootMargin: "-15% 0px -75% 0px" });
      headings.forEach(function (h) { spy.observe(h.el); });
    }
  }
})();
