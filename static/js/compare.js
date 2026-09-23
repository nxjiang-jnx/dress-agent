// Baseline comparisons, laid out like the CHORD template: scene buttons, then the input photo,
// one row per view with its label, one pre-rendered turntable video per method, method names
// underneath. Nothing is rendered in the browser.
// Switching scenes never blanks the grid: the next scene is built off screen (already on hover),
// and only once its videos can play and its photo is decoded does it replace the old one.
// The videos of a scene start together and then just loop (one length, so they stay in step).
(function () {
  'use strict';
  var READY_TIMEOUT = 5000;   // swap anyway if a video is slow to buffer

  var probe = document.createElement('video');
  var EXT = probe.canPlayType('video/mp4; codecs="avc1.64001F"') ? '.mp4' : '.webm';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function unload(buf) {
    buf.videos.forEach(function (v) { v.pause(); v.removeAttribute('src'); v.load(); });
    if (buf.grid.parentNode) buf.grid.parentNode.removeChild(buf.grid);
  }

  function Group(root, cfg, scenes) {
    this.root = root;
    this.cfg = cfg;
    this.scenes = scenes;
    this.stack = el('div', 'comparison-stack');
    var wrap = root.querySelector('.comparison-grid-wrapper');
    wrap.innerHTML = '';
    wrap.appendChild(this.stack);
    this.buffers = {};        // scene id -> built grid (current, pending, prefetched)
    this.current = null;
    this.pending = null;
    this.visible = false;
    this.buildScenes();
    this.bind();
    var first = (cfg.default || {})[root.dataset.group];
    this.select(scenes.some(function (s) { return s.id === first; }) ? first : scenes[0].id);
  }

  Group.prototype.buildScenes = function () {
    var self = this, bar = this.root.querySelector('.comparison-scene-buttons');
    this.scenes.forEach(function (s) {
      var b = el('button', 'button is-light comparison-scene-button', s.label);
      b.dataset.scene = s.id;
      b.addEventListener('click', function () { self.select(s.id); });
      b.addEventListener('pointerenter', function () { self.buffer(s.id); });
      bar.appendChild(b);
    });
  };

  // build a scene's grid off screen and report when it can be shown without blanks
  Group.prototype.buffer = function (id) {
    if (this.buffers[id]) return this.buffers[id];
    var cfg = this.cfg, s = this.scenes.filter(function (x) { return x.id === id; })[0];
    var grid = el('div', 'comparison-grid');
    var nRows = cfg.rows.length;
    // input photo | view label | one column per method; the photo spans the view rows,
    // so each label sits right next to the row of results it names
    grid.style.gridTemplateColumns = '190px 84px repeat(' + cfg.methods.length + ', minmax(0, 1fr))';
    var place = function (node, row, col, span) {
      node.style.gridRow = span ? row + ' / span ' + span : String(row);
      node.style.gridColumn = String(col);
      grid.appendChild(node);
    };
    var waits = [];
    var inp = el('div', 'comparison-video-wrapper is-input');
    var img = el('img', 'comparison-video is-input');
    img.alt = 'Input photo';
    img.src = s.input;
    waits.push(img.decode ? img.decode().catch(function () {}) : Promise.resolve());
    inp.appendChild(img);
    place(inp, 1, 1, nRows);
    var videos = [];
    cfg.rows.forEach(function (row, r) {
      place(el('div', 'comparison-view-label', row.label), r + 1, 2);
      cfg.methods.forEach(function (m, j) {
        var wrap = el('div', 'comparison-video-wrapper');
        var src = cfg.dir + id + '/' + m.id + '_' + row.id;
        var v = el('video', 'comparison-video');
        v.muted = true; v.loop = true; v.playsInline = true; v.preload = 'auto';
        v.setAttribute('muted', ''); v.setAttribute('playsinline', '');
        v.poster = src + '.webp';
        waits.push(new Promise(function (res) {
          v.addEventListener('canplaythrough', res, { once: true });
          v.addEventListener('error', res, { once: true });
        }));
        v.src = src + EXT;
        wrap.appendChild(v);
        place(wrap, r + 1, j + 3);
        videos.push(v);
      });
    });
    place(el('div', 'comparison-method-label', 'Input'), nRows + 1, 1);
    cfg.methods.forEach(function (m, j) {
      place(el('div', 'comparison-method-label', m.label), nRows + 1, j + 3);
    });
    var buf = {
      id: id, grid: grid, videos: videos,
      ready: Promise.race([Promise.all(waits), new Promise(function (res) { setTimeout(res, READY_TIMEOUT); })]),
    };
    this.buffers[id] = buf;
    this.trim();
    return buf;
  };

  // keep the current scene, the one being switched to, and one prefetched scene
  Group.prototype.trim = function () {
    var self = this, keep = [this.current && this.current.id, this.pending];
    var extra = Object.keys(this.buffers).filter(function (k) { return keep.indexOf(k) < 0; });
    extra.slice(0, -1).forEach(function (k) { unload(self.buffers[k]); delete self.buffers[k]; });
  };

  Group.prototype.select = function (id) {
    this.root.querySelectorAll('.comparison-scene-button').forEach(function (b) {
      b.classList.toggle('is-primary', b.dataset.scene === id);
    });
    if (this.current && this.current.id === id) { this.pending = null; return; }
    if (this.pending === id) return;
    var self = this;
    this.pending = id;
    var buf = this.buffer(id);
    if (!this.current) {
      // first scene: show it right away on its poster frames, start once it can play
      this.swap(buf);
      buf.ready.then(function () {
        if (self.current !== buf) return;
        buf.started = true;
        self.play();
      });
      return;
    }
    buf.ready.then(function () {
      if (self.pending !== id) return;
      buf.started = true;
      self.swap(buf);
    });
  };

  // replace the grid in one step: the new scene is already buffered, so nothing blanks
  Group.prototype.swap = function (buf) {
    var old = this.current;
    this.pending = null;
    this.current = buf;
    buf.videos.forEach(function (v) { v.currentTime = 0; });
    this.stack.appendChild(buf.grid);
    if (old && old !== buf) { unload(old); delete this.buffers[old.id]; }
    this.play();
    this.trim();
  };

  Group.prototype.play = function () {
    if (!this.current) return;
    var on = this.visible && this.current.started;
    this.current.videos.forEach(function (v) {
      if (on) v.play().catch(function () {});
      else v.pause();
    });
  };

  Group.prototype.bind = function () {
    var self = this;
    // play only while on screen
    new IntersectionObserver(function (es) {
      self.visible = es[0].isIntersecting;
      self.play();
    }, { threshold: 0.05 }).observe(this.root);
  };

  function start() {
    fetch('./static/data/compare.json?v=' + (window.SITE_VERSION || '')).then(function (r) { return r.json(); }).then(function (cfg) {
      document.querySelectorAll('.comparison-category[data-group]').forEach(function (root) {
        var scenes = cfg.groups[root.dataset.group];
        if (scenes && scenes.length) new Group(root, cfg, scenes);
      });
    });
  }

  // build the section only when it approaches the viewport
  var sec = document.getElementById('comparisons');
  if (!('IntersectionObserver' in window)) return start();
  var io = new IntersectionObserver(function (es) {
    if (es[0].isIntersecting) { io.disconnect(); start(); }
  }, { rootMargin: '600px 0px' });
  io.observe(sec);
})();
