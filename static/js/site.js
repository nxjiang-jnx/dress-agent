// Page chrome: scroll reveal, BibTeX copy.
(function () {
  'use strict';
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
