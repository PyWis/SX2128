// Starfield
(function () {
  const sf = document.querySelector(".starfield");
  if (!sf) return;
  const count = 80;
  for (let i = 0; i < count; i++) {
    const s = document.createElement("span");
    s.style.top = Math.random() * 100 + "%";
    s.style.left = Math.random() * 100 + "%";
    s.style.animationDelay = Math.random() * 6 + "s";
    s.style.animationDuration = 4 + Math.random() * 6 + "s";
    if (Math.random() > 0.7) {
      s.style.background = "#ff3ec9";
      s.style.boxShadow = "0 0 6px #ff3ec9";
    } else if (Math.random() > 0.6) {
      s.style.background = "#7a5cff";
      s.style.boxShadow = "0 0 6px #7a5cff";
    }
    sf.appendChild(s);
  }
})();

// Mobile nav
(function () {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (!toggle || !links) return;
  toggle.addEventListener("click", () => {
    links.classList.toggle("open");
  });
})();

// Reveal on scroll
(function () {
  const els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || !els.length) {
    els.forEach((e) => e.classList.add("visible"));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  els.forEach((e) => io.observe(e));
})();

// Stat counter
(function () {
  const stats = document.querySelectorAll("[data-count]");
  if (!stats.length) return;
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const target = parseInt(el.dataset.count, 10);
        const suffix = el.dataset.suffix || "";
        const duration = 1500;
        const start = performance.now();
        const step = (now) => {
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          el.textContent = Math.floor(target * eased).toLocaleString("it-IT") + suffix;
          if (t < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
        io.unobserve(el);
      });
    },
    { threshold: 0.4 }
  );
  stats.forEach((s) => io.observe(s));
})();
