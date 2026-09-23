// Page chrome: floating nav, scroll reveal, BibTeX copy.
(function () {
  'use strict';
  var bar = document.getElementById('topbar');
  var hero = document.getElementById('top');
  var links = Array.prototype.slice.call(bar.querySelectorAll('.topbar__links a'));
  var secs = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });

  var onScroll = function () {
    bar.classList.toggle('is-on', hero.getBoundingClientRect().bottom < 80);
    var y = window.innerHeight * 0.35, cur = -1;
    secs.forEach(function (s, i) { if (s && s.getBoundingClientRect().top < y) cur = i; });
    links.forEach(function (a, i) { a.classList.toggle('is-active', i === cur); });
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  var rev = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); rev.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(function (n) { rev.observe(n); });

  var copy = document.getElementById('bib-copy');
  copy.addEventListener('click', function () {
    var txt = document.getElementById('bib-code').textContent;
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function () {
      copy.textContent = 'Copied';
      setTimeout(function () { copy.textContent = 'Copy'; }, 1600);
    }).catch(function () {});
  });
})();
