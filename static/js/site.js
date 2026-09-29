// Page chrome: scroll reveal, scroll-scaled films, BibTeX copy.
(function () {
  'use strict';
  var rev = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); rev.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(function (n) { rev.observe(n); });

  // CHORD's 4D gallery, as in its index.js: a lazy video keeps the bouncing-dots poster
  // (loading.svg) until it comes within 200px, then loads and plays.
  function initLazyVideos() {
    var lazyVideos = document.querySelectorAll('video[data-lazy="true"]');
    if (!lazyVideos.length) return;

    function loadVideo(video) {
      var source = video.querySelector('source');
      if (source) {
        var dataSrc = source.getAttribute('data-src');
        if (dataSrc && !source.getAttribute('src')) {
          source.setAttribute('src', dataSrc);
        }
      } else {
        var dataSrc = video.getAttribute('data-src');
        if (dataSrc && !video.getAttribute('src')) {
          video.setAttribute('src', dataSrc);
        }
      }
      video.load();
      if (video.autoplay) {
        var playPromise = video.play();
        if (playPromise && typeof playPromise.catch === 'function') {
          playPromise.catch(function () {});
        }
      }
    }

    if (!('IntersectionObserver' in window)) {
      lazyVideos.forEach(loadVideo);
      return;
    }

    var observer = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        loadVideo(entry.target);
        obs.unobserve(entry.target);
      });
    }, { rootMargin: '200px 0px', threshold: 0.01 });

    lazyVideos.forEach(function (video) { observer.observe(video); });
  }

  // ... and a scroll-scaled video grows from 50% to 100% of the page width as it scrolls in,
  // reaching full width when its centre meets the middle of the screen.
  function initScrollScaleVideos() {
    var videos = document.querySelectorAll('.scroll-scale-video');
    if (!videos.length) return;

    function updateVideoWidths() {
      videos.forEach(function (video) {
        var rect = video.getBoundingClientRect();
        var windowHeight = window.innerHeight;
        var scrollRange = windowHeight / 2;
        var distanceFromBottom = windowHeight - rect.top;
        var progress = Math.min(1, Math.max(0, distanceFromBottom / (scrollRange + rect.height / 2)));
        var width = 50 + (progress * 50);
        video.style.width = width + '%';
      });
    }

    window.addEventListener('scroll', updateVideoWidths, { passive: true });
    updateVideoWidths();
  }

  initScrollScaleVideos();
  initLazyVideos();

  // copy a tidy BibTeX: two-space fields, closing brace on its own line
  function tidy(text) {
    var lines = text.split('\n').map(function (l) { return l.trim(); }).filter(Boolean);
    return lines.map(function (l, i) {
      return i === 0 || i === lines.length - 1 ? l : '  ' + l;
    }).join('\n') + '\n';
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    // http pages: the old textarea route
    return new Promise(function (res, rej) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) res(); else rej(new Error('copy failed'));
    });
  }

  document.querySelectorAll('.bib').forEach(function (box) {
    var btn = box.querySelector('.bib__copy'), code = box.querySelector('pre code'), timer;
    if (!btn || !code) return;
    btn.addEventListener('click', function () {
      copy(tidy(code.textContent)).then(function () {
        btn.classList.add('is-done');
        btn.setAttribute('aria-label', 'Copied');
        clearTimeout(timer);
        timer = setTimeout(function () {
          btn.classList.remove('is-done');
          btn.setAttribute('aria-label', 'Copy BibTeX');
        }, 1800);
      });
    });
  });
})();
