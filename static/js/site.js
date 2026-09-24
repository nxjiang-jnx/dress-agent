// Page chrome: scroll reveal, BibTeX copy.
(function () {
  'use strict';
  var rev = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); rev.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(function (n) { rev.observe(n); });

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
