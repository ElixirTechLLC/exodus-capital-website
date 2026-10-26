/* Exodus Capital — site behaviour (no dependencies) */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  /* ---- header: solid after scrolling past the hero ---- */
  var header = $('.header');
  function onScroll() {
    if (!header) return;
    header.classList.toggle('is-solid', window.scrollY > 40);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---- side drawer ---- */
  var drawer = $('.drawer');
  function openDrawer() { drawer.classList.add('is-open'); document.body.classList.add('no-scroll'); }
  function closeDrawer() { drawer.classList.remove('is-open'); document.body.classList.remove('no-scroll'); }
  $$('[data-open-drawer]').forEach(function (b) { b.addEventListener('click', openDrawer); });
  $$('[data-close-drawer]').forEach(function (b) { b.addEventListener('click', closeDrawer); });

  /* ---- modals (contact / register / video) ---- */
  function openModal(id) {
    var m = document.getElementById('modal-' + id);
    if (!m) return;
    closeDrawer();
    m.classList.add('is-open');
    document.body.classList.add('no-scroll');
    var f = m.querySelector('input, select, textarea');
    if (f) setTimeout(function () { f.focus(); }, 50);
  }
  function closeModal(m) {
    m.classList.remove('is-open');
    document.body.classList.remove('no-scroll');
    var fr = m.querySelector('iframe[data-src]');
    if (fr) fr.removeAttribute('src');
  }
  $$('[data-modal]').forEach(function (b) {
    b.addEventListener('click', function (e) { e.preventDefault(); openModal(b.getAttribute('data-modal')); });
  });
  $$('.modal').forEach(function (m) {
    $$('[data-close-modal]', m).forEach(function (b) { b.addEventListener('click', function () { closeModal(m); }); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { $$('.modal.is-open').forEach(closeModal); closeDrawer(); }
  });
  $$('[data-video]').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = document.getElementById('modal-video');
      var fr = m && m.querySelector('iframe');
      if (fr) fr.src = b.getAttribute('data-video');
      openModal('video');
    });
  });

  /* ---- forms: post without leaving the page ---- */
  $$('form[data-ajax]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var status = form.querySelector('.form__status');
      var btn = form.querySelector('[type=submit]');
      if (form.querySelector('.honeypot input') && form.querySelector('.honeypot input').value) return;
      var data = new FormData(form);
      var provider = form.getAttribute('data-provider');
      var action = form.getAttribute('action') || '/';
      var opts = { method: 'POST' };
      if (provider === 'netlify') {
        opts.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
        opts.body = new URLSearchParams(data).toString();
      } else {
        opts.body = data;
        opts.headers = { 'Accept': 'application/json' };
      }
      if (btn) { btn.disabled = true; btn.textContent = 'Submitting'; }
      if (status) { status.textContent = ''; status.className = 'form__status'; }
      fetch(action, opts).then(function (r) {
        if (!r.ok) throw new Error('bad status ' + r.status);
        form.reset();
        if (status) { status.textContent = form.getAttribute('data-success') || 'Message sent successfully!'; status.classList.add('is-ok'); }
        if (btn) btn.textContent = 'Submitted';
      }).catch(function () {
        if (status) { status.textContent = 'Something went wrong. Please call or email us instead.'; status.classList.add('is-error'); }
        if (btn) { btn.disabled = false; btn.textContent = 'Submit'; }
      });
    });
  });

  /* ---- counters ---- */
  function animateCounter(el) {
    var raw = el.getAttribute('data-count');
    var m = raw.match(/^([^0-9]*)([0-9][0-9,.]*)(.*)$/);
    if (!m) { el.textContent = raw; return; }
    var prefix = m[1], suffix = m[3];
    var hasComma = m[2].indexOf(',') >= 0;
    var target = parseFloat(m[2].replace(/,/g, ''));
    var decimals = (m[2].split('.')[1] || '').length;
    var start = null, dur = 1600;
    function fmt(v) {
      var s = v.toFixed(decimals);
      if (hasComma) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      return prefix + s + suffix;
    }
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step); else el.textContent = raw;
    }
    requestAnimationFrame(step);
  }
  var counters = $$('[data-count]');
  if ('IntersectionObserver' in window && counters.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { animateCounter(en.target); io.unobserve(en.target); }
      });
    }, { threshold: 0.4 });
    counters.forEach(function (c) { io.observe(c); });
  } else { counters.forEach(function (c) { c.textContent = c.getAttribute('data-count'); }); }

  /* ---- reveal on scroll ---- */
  var reveals = $$('.reveal');
  if ('IntersectionObserver' in window && reveals.length) {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-visible'); ro.unobserve(en.target); } });
    }, { threshold: 0.12 });
    reveals.forEach(function (r) { ro.observe(r); });
  } else { reveals.forEach(function (r) { r.classList.add('is-visible'); }); }

  /* ---- scroll-snap carousels with prev/next ---- */
  $$('[data-carousel]').forEach(function (c) {
    var track = c.querySelector('[data-track]');
    if (!track) return;
    function stepBy(dir) {
      var item = track.firstElementChild;
      var w = item ? item.getBoundingClientRect().width + parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap || 0) : 300;
      var max = track.scrollWidth - track.clientWidth;
      var next = track.scrollLeft + dir * w;
      if (dir > 0 && track.scrollLeft >= max - 2) next = 0;
      if (dir < 0 && track.scrollLeft <= 2) next = max;
      track.scrollTo({ left: next, behavior: 'smooth' });
    }
    $$('[data-prev]', c).forEach(function (b) { b.addEventListener('click', function () { stepBy(-1); }); });
    $$('[data-next]', c).forEach(function (b) { b.addEventListener('click', function () { stepBy(1); }); });
    var auto = parseInt(c.getAttribute('data-autoplay') || '0', 10);
    if (auto > 0 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      var timer = setInterval(function () { stepBy(1); }, auto);
      c.addEventListener('mouseenter', function () { clearInterval(timer); });
    }
  });

  /* ---- simple fading slideshows (hero slides, property photos, quotes) ---- */
  $$('[data-slides]').forEach(function (box) {
    var slides = $$('[data-slide]', box);
    if (slides.length < 2) return;
    var i = 0, interval = parseInt(box.getAttribute('data-slides') || '6000', 10);
    var dots = $$('[data-dot]', box);
    function show(n) {
      i = (n + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle('is-active', k === i); });
      dots.forEach(function (d, k) { d.classList.toggle('is-active', k === i); });
    }
    dots.forEach(function (d, k) { d.addEventListener('click', function () { show(k); }); });
    $$('[data-prev]', box).forEach(function (b) { b.addEventListener('click', function () { show(i - 1); }); });
    $$('[data-next]', box).forEach(function (b) { b.addEventListener('click', function () { show(i + 1); }); });
    show(0);
    if (interval > 0 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) setInterval(function () { show(i + 1); }, interval);
  });

  /* ---- accordion ---- */
  $$('.accordion__item').forEach(function (item) {
    var btn = item.querySelector('.accordion__btn');
    btn && btn.addEventListener('click', function () { item.classList.toggle('is-open'); });
  });

  /* ---- "read more" on testimonials ---- */
  $$('[data-readmore]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.getElementById(b.getAttribute('data-readmore'));
      if (!t) return;
      var clamped = t.classList.toggle('is-clamped');
      b.textContent = clamped ? 'Read More' : 'Read Less';
    });
  });

  /* ---- lazy videos: only download once near the viewport ---- */
  $$('video[data-src]').forEach(function (v) {
    function load() {
      if (v.getAttribute('src')) return;
      v.src = v.getAttribute('data-src');
      v.load(); v.play().catch(function () {});
    }
    if ('IntersectionObserver' in window) {
      var vo = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { load(); vo.disconnect(); } }, { rootMargin: '300px' });
      vo.observe(v);
    } else load();
  });

  /* ---- footer year ---- */
  $$('[data-year]').forEach(function (y) { y.textContent = new Date().getFullYear(); });
})();
