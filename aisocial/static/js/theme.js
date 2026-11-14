// Light/dark theme. Loaded in <head> (classic script) so the page never flashes the wrong theme.
(function () {
  var KEY = "aisocial-theme";
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ }
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    button.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      if (!current) current = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* storage blocked */ }
    });
  });
})();
