// Full gallery (gallery.html): every turntable in a dense grid. A click opens the result in the
// project page's viewer; the choice travels in sessionStorage so the address stays clean.
(function () {
  'use strict';
  var V = '?v=' + (window.SITE_VERSION || '');
  var EXT = document.createElement('video').canPlayType('video/mp4; codecs="avc1.64001F"') ? '.mp4' : '.webm';
  var grid = document.getElementById('fg-grid');

  // back to the page we came from (keeps its scroll position), else to the project page
  function back(e) {
    var ref = document.referrer, here = location.href.replace(/[^/]*$/, '');
    if (ref && ref.indexOf(here) === 0 && history.length > 1) {
      if (e) e.preventDefault();
      history.back();
      return true;
    }
    return false;
  }
  document.getElementById('fg-back').addEventListener('click', back);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { if (!back()) location.href = './'; }
  });

  function open(id) {
    try { sessionStorage.setItem('dress-open', id); } catch (err) { /* storage off */ }
    location.href = './';
  }

  // play only what is on screen
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      var v = e.target;
      if (e.isIntersecting) {
        if (!v.src) { v.src = v.dataset.src; v.load(); }
        v.play().catch(function () {});
      } else v.pause();
    });
  }, { rootMargin: '200px 0px', threshold: 0.05 });

  fetch('./static/data/gallery.json' + V).then(function (r) { return r.json(); }).then(function (data) {
    data.items.forEach(function (it, i) {
      var card = document.createElement('article');
      card.className = 'card';
      card.tabIndex = 0;
      card.style.animationDelay = Math.min(i, 24) * 22 + 'ms';
      card.setAttribute('aria-label', it.title);
      card.innerHTML =
        '<div class="card__media">' +
        '<video muted loop playsinline preload="none" poster="' + it.poster + V + '" data-src="' + it.video.replace(/\.mp4$/, EXT) + V + '"></video>' +
        '<div class="card__photo"><img loading="lazy" src="' + it.thumb + V + '" alt=""></div>' +
        '<span class="card__cta">View in 3D</span></div>';
      card.addEventListener('click', function () { open(it.id); });
      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(it.id); }
      });
      grid.appendChild(card);
      io.observe(card.querySelector('video'));
    });
  });
})();
