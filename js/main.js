/* suthahar.msdevbuild.com — page behaviour. Loaded with `defer`. */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.remove('no-js');

  /* ── Hamburger menu ── */
  var hamburger = document.getElementById('hamburger');
  var drawer = document.getElementById('mobile-drawer');
  function setDrawer(open) {
    if (!drawer || !hamburger) return;
    drawer.classList.toggle('open', open);
    hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  window.closeDrawer = function () { setDrawer(false); };
  if (hamburger) hamburger.addEventListener('click', function () { setDrawer(!drawer.classList.contains('open')); });
  if (drawer) drawer.addEventListener('click', function (e) { if (e.target.closest('a')) setDrawer(false); });
  document.addEventListener('click', function (e) {
    if (drawer && drawer.classList.contains('open') && !drawer.contains(e.target) && !hamburger.contains(e.target)) setDrawer(false);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setDrawer(false); });

  /* ── Scroll reveal ── */
  if ('IntersectionObserver' in window) {
    var reveal = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); reveal.unobserve(e.target); } });
    }, { threshold: 0.06, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.fu').forEach(function (el) { reveal.observe(el); });
  } else {
    document.querySelectorAll('.fu').forEach(function (el) { el.classList.add('in'); });
  }

  /* ── Toast ── */
  function showToast(msg, ms) {
    var t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg; t.classList.add('show');
    setTimeout(function () { t.classList.remove('show'); }, ms || 2600);
  }

  /* ── Progress bar, active nav link, back-to-top ── */
  var progress = document.getElementById('progress-bar');
  var toTop = document.getElementById('back-to-top');
  var sections = Array.prototype.slice.call(document.querySelectorAll('main [id], .main > [id]'));
  var navLinks = document.querySelectorAll('.n-links a[href^="#"]');
  var ticking = false;
  function onScroll() {
    var y = window.scrollY;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) progress.style.width = (max > 0 ? (y / max) * 100 : 0) + '%';
    var cur = '';
    for (var i = 0; i < sections.length; i++) { if (y >= sections[i].offsetTop - 120) cur = sections[i].id; }
    navLinks.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + cur); });
    if (toTop) toTop.classList.toggle('show', y > 400);
    ticking = false;
  }
  window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  if (toTop) toTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });

  /* ── Theme: html[data-theme], same key as the blog ── */
  var themeBtn = document.getElementById('dark-toggle');
  function paintThemeBtn() {
    if (!themeBtn) return;
    var dark = root.getAttribute('data-theme') === 'dark';
    themeBtn.textContent = dark ? '☀️' : '🌙';
    themeBtn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  }
  paintThemeBtn();
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', next === 'dark' ? '#0b1424' : '#0078d4');
    paintThemeBtn();
  });

  /* ── Typewriter ── */
  var tw = document.getElementById('tw-text');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (tw && !reduce) {
    var phrases = [
      'Cloud, AI & Mobile Solutions Architect',
      'Technical Architect @ Continental Tire',
      'Microsoft Azure Content Hero · MCT',
      'Creator of MSDEVBUILD',
      'Azure · Azure AI · GitHub Copilot',
      'Flutter · .NET MAUI · C# · Python'
    ];
    var pi = 0, ci = phrases[0].length, deleting = true;
    var tick = function () {
      var p = phrases[pi];
      if (!deleting) {
        tw.textContent = p.slice(0, ++ci);
        if (ci === p.length) { deleting = true; return setTimeout(tick, 2200); }
        return setTimeout(tick, 55);
      }
      tw.textContent = p.slice(0, --ci);
      if (ci === 0) { deleting = false; pi = (pi + 1) % phrases.length; return setTimeout(tick, 350); }
      setTimeout(tick, 26);
    };
    setTimeout(tick, 2600);
  }

  /* ── Counters: animate the number, keep prefix/suffix ("5M+", "15,000+") ── */
  function animate(el) {
    var raw = el.getAttribute('data-final') || el.textContent.trim();
    var m = raw.match(/^([^\d]*)([\d,]+)(.*)$/);
    if (!m) return;
    var target = parseInt(m[2].replace(/,/g, ''), 10);
    var comma = m[2].indexOf(',') > -1;
    var start = null;
    function fmt(n) { return comma ? n.toLocaleString('en-US') : String(n); }
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / 1400, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = m[1] + fmt(Math.floor(e * target)) + m[3];
      if (p < 1) requestAnimationFrame(step); else el.textContent = raw;
    }
    requestAnimationFrame(step);
  }
  if ('IntersectionObserver' in window && !reduce) {
    var counters = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { animate(e.target); counters.unobserve(e.target); } });
    }, { threshold: 0.4 });
    document.querySelectorAll('.stat-n, .impact-n').forEach(function (el) {
      el.setAttribute('data-final', el.textContent.trim());
      counters.observe(el);
    });
  }

  /* ── Skills filter ── */
  document.querySelectorAll('.filter-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      document.querySelectorAll('.filter-tab').forEach(function (t) { t.classList.remove('active'); t.setAttribute('aria-pressed', 'false'); });
      tab.classList.add('active'); tab.setAttribute('aria-pressed', 'true');
      var f = tab.getAttribute('data-filter');
      document.querySelectorAll('#skill-pills .pill').forEach(function (p) {
        p.style.display = (f === 'all' || p.getAttribute('data-cat') === f) ? '' : 'none';
      });
    });
  });

  /* ── Share ── */
  window.copyLink = function () {
    var url = 'https://suthahar.msdevbuild.com/';
    if (navigator.share) {
      navigator.share({ title: 'Suthahar Jegatheesan — Cloud, AI & Mobile Solutions Architect', url: url }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(function () { showToast('🔗 Profile link copied'); });
    }
  };
})();
