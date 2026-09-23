// Baseline comparisons: one synchronized turntable per method, scrubbed together.
(function () {
  'use strict';
  var DRIFT = 0.09;       // seconds of drift tolerated before a resync
  var TURN_PER_CELL = 0.5; // dragging one cell width turns the models half a revolution

  var probe = document.createElement('video');
  var EXT = probe.canPlayType('video/mp4; codecs="avc1.64001F"') ? '.mp4' : '.webm';

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function Group(root, cfg, scenes) {
    this.root = root;
    this.cfg = cfg;
    this.scenes = scenes;
    this.grid = root.querySelector('.cmp__grid');
    this.slider = root.querySelector('.cmp__angle');
    this.deg = root.querySelector('.cmp__deg');
    this.playBtn = root.querySelector('.cmp__play');
    this.videos = [];
    this.playing = true;
    this.t = 0;              // turntable time in seconds
    this.last = null;
    this.visible = false;
    this.scene = null;
    this.buildScenes();
    this.bind();
    var first = (cfg.default || {})[root.dataset.group];
    this.select(scenes.some(function (s) { return s.id === first; }) ? first : scenes[0].id);
  }

  Group.prototype.buildScenes = function () {
    var self = this, bar = this.root.querySelector('.cmp__scenes');
    this.scenes.forEach(function (s) {
      var b = el('button', 'scene', '<img loading="lazy" src="' + s.thumb + '" alt="">' + s.label);
      b.dataset.id = s.id;
      b.setAttribute('role', 'tab');
      b.addEventListener('click', function () { self.select(s.id); });
      bar.appendChild(b);
    });
  };

  Group.prototype.select = function (id) {
    if (this.scene === id) return;
    this.scene = id;
    var self = this, cfg = this.cfg, s = this.scenes.filter(function (x) { return x.id === id; })[0];
    this.root.querySelectorAll('.scene').forEach(function (b) {
      b.classList.toggle('is-active', b.dataset.id === id);
      b.setAttribute('aria-selected', b.dataset.id === id);
    });
    this.videos.forEach(function (v) { v.pause(); v.removeAttribute('src'); v.load(); });
    this.videos = [];
    this.grid.innerHTML = '';
    this.t = 0;
    cfg.rows.forEach(function (row, r) {
      self.grid.appendChild(el('div', 'cmp__rowlab', row.label));
      if (r === 0) {
        var inp = el('div', 'cmp__cell is-input');
        var img = el('img');
        img.src = s.input;
        img.alt = 'Input photo';
        inp.appendChild(img);
        self.grid.appendChild(inp);
      }
      cfg.methods.forEach(function (m) {
        var cell = el('div', 'cmp__cell' + (m.id === 'ours' ? ' is-ours' : ''));
        var src = cfg.dir + id + '/' + m.id + '_' + row.id;
        var v = document.createElement('video');
        v.muted = true; v.loop = true; v.playsInline = true; v.preload = 'auto';
        v.setAttribute('muted', ''); v.setAttribute('playsinline', '');
        v.poster = src + '.webp';
        v.src = src + EXT;
        v.addEventListener('loadeddata', function () { cell.classList.add('is-ready'); self.kick(); });
        cell.appendChild(v);
        cell.appendChild(el('div', 'spin'));
        self.grid.appendChild(cell);
        self.videos.push(v);
        self.dragTarget(cell);
      });
    });
    this.grid.appendChild(el('div'));
    this.grid.appendChild(el('div', 'cmp__method', '<i style="background:' + cfg.input_color + '"></i>Input'));
    cfg.methods.forEach(function (m) {
      self.grid.appendChild(el('div', 'cmp__method' + (m.id === 'ours' ? ' is-ours' : ''), '<i style="background:' + m.color + '"></i>' + m.label));
    });
    this.kick();
  };

  Group.prototype.duration = function () {
    var d = 0;
    this.videos.forEach(function (v) { if (isFinite(v.duration)) d = Math.max(d, v.duration); });
    return d || this.cfg.duration;
  };

  // keep every video on the shared clock
  Group.prototype.sync = function (force) {
    var dur = this.duration(), t = this.t, self = this;
    this.videos.forEach(function (v) {
      if (v.readyState < 2) return;
      var dt = Math.abs(v.currentTime - t);
      dt = Math.min(dt, dur - dt);
      if (force || dt > DRIFT) v.currentTime = t;
      if (self.playing && !self.dragging && self.visible) { if (v.paused) v.play().catch(function () {}); }
      else if (!v.paused) v.pause();
    });
  };

  Group.prototype.kick = function () {
    if (this.raf) return;
    var self = this;
    var loop = function (now) {
      self.raf = null;
      if (!self.visible) return;
      var dur = self.duration();
      if (self.playing && !self.dragging) {
        if (self.last != null) self.t = (self.t + (now - self.last) / 1000) % dur;
        // follow a playing video as the clock source so the picture never jumps
        var lead = self.videos.filter(function (v) { return !v.paused && v.readyState >= 3; })[0];
        if (lead) {
          var d = lead.currentTime - self.t;
          if (Math.abs(d) < 0.5) self.t += d * 0.5;
        }
      }
      self.last = now;
      if (!self.lastSync || now - self.lastSync > 250) { self.sync(false); self.lastSync = now; }
      var frac = dur ? self.t / dur : 0;
      if (!self.sliding) self.slider.value = Math.round(frac * 1000);
      self.deg.textContent = Math.round(frac * 360) + '°';
      self.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  };

  Group.prototype.seek = function (t) {
    var dur = this.duration();
    this.t = ((t % dur) + dur) % dur;
    var self = this;
    if (this.pendingSeek) return;
    this.pendingSeek = true;
    requestAnimationFrame(function () {
      self.pendingSeek = false;
      self.videos.forEach(function (v) { if (v.readyState >= 1) { if (!v.paused) v.pause(); v.currentTime = self.t; } });
    });
  };

  Group.prototype.dragTarget = function (cell) {
    var self = this, x0 = 0, t0 = 0, id = null;
    cell.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      id = e.pointerId;
      cell.setPointerCapture(id);
      x0 = e.clientX; t0 = self.t;
      self.dragging = true;
      self.root.classList.add('is-dragging');
    });
    cell.addEventListener('pointermove', function (e) {
      if (e.pointerId !== id) return;
      var dx = e.clientX - x0;
      self.seek(t0 - dx / cell.clientWidth * TURN_PER_CELL * self.duration());
    });
    var end = function (e) {
      if (e.pointerId !== id) return;
      id = null;
      self.dragging = false;
      self.last = null;
      self.root.classList.remove('is-dragging');
      self.sync(true);
    };
    cell.addEventListener('pointerup', end);
    cell.addEventListener('pointercancel', end);
  };

  Group.prototype.bind = function () {
    var self = this;
    this.slider.addEventListener('input', function () {
      self.sliding = true;
      self.dragging = true;
      self.seek(self.slider.value / 1000 * self.duration());
    });
    this.slider.addEventListener('change', function () {
      self.sliding = false;
      self.dragging = false;
      self.last = null;
      self.sync(true);
    });
    this.playBtn.addEventListener('click', function () {
      self.playing = !self.playing;
      self.playBtn.setAttribute('aria-pressed', String(self.playing));
      self.playBtn.setAttribute('aria-label', self.playing ? 'Pause' : 'Play');
      self.last = null;
      self.sync(true);
    });
    new IntersectionObserver(function (es) {
      self.visible = es[0].isIntersecting;
      self.last = null;
      if (self.visible) self.kick();
      self.sync(false);
    }, { threshold: 0.05 }).observe(this.root);
  };

  function start() {
    fetch('./static/data/compare.json').then(function (r) { return r.json(); }).then(function (cfg) {
      document.querySelectorAll('.cmp[data-group]').forEach(function (root) {
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
