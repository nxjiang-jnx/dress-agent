// Baseline comparisons: one turntable per method, all turning in sync.
(function () {
  'use strict';
  var DRIFT = 0.09;       // seconds of drift tolerated before a resync

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
        self.grid.appendChild(cell);
        self.videos.push(v);
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
      if (self.playing && self.visible) { if (v.paused) v.play().catch(function () {}); }
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
      if (self.playing) {
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
      self.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  };

  Group.prototype.bind = function () {
    var self = this;
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
