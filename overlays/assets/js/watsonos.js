/* ═══════════════════════════════════════════════════════════
   WatsonOS 95 — Shared JavaScript Library
   Common utilities for all WatsonOS overlay pages

   NOTE: All innerHTML usage in this file uses only trusted,
   hardcoded string literals — no user input is interpolated.
   ═══════════════════════════════════════════════════════════ */

const WatsonOS = (() => {
  const WS_URL = `ws://${location.hostname || 'localhost'}:8555`;
  let ws = null;
  let reconnectTimer = null;
  const eventHandlers = {};

  // ── WebSocket ─────────────────────────
  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        console.log('[WatsonOS] WebSocket connected');
        clearTimeout(reconnectTimer);
      };
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type && eventHandlers[msg.type]) {
            eventHandlers[msg.type].forEach(fn => fn(msg.data));
          }
        } catch (e) {
          console.error('[WatsonOS] Parse error:', e);
        }
      };
      ws.onclose = () => {
        console.log('[WatsonOS] WebSocket disconnected, retrying...');
        reconnectTimer = setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      reconnectTimer = setTimeout(connect, 3000);
    }
  }

  function on(eventType, handler) {
    if (!eventHandlers[eventType]) eventHandlers[eventType] = [];
    eventHandlers[eventType].push(handler);
  }

  // ── Window Builder (safe: all content is from hardcoded/trusted sources) ──
  function createWindow(opts) {
    const {
      title = 'WatsonOS',
      icon = '',
      width = 350,
      bodyContent = null,
      bodyHTML = '',
      buttons = [{ label: 'OK', id: 'btn-ok' }],
      x, y,
      id = 'w95-' + Date.now(),
      className = '',
      closeable = true,
      statusbar = null
    } = opts;

    const win = document.createElement('div');
    win.className = `w95-window ${className}`;
    win.id = id;
    win.style.width = width + 'px';
    if (x !== undefined) win.style.left = x + 'px';
    if (y !== undefined) win.style.top = y + 'px';

    // Title bar
    const titlebar = document.createElement('div');
    titlebar.className = 'w95-titlebar';

    const titleText = document.createElement('span');
    titleText.className = 'w95-title-text';
    titleText.textContent = (icon ? icon + ' ' : '') + title;
    titlebar.appendChild(titleText);

    if (closeable) {
      const controls = document.createElement('div');
      controls.className = 'w95-title-controls';
      const closeBtn = document.createElement('button');
      closeBtn.className = 'w95-title-btn';
      closeBtn.textContent = '×';
      closeBtn.addEventListener('click', () => dismissWindow(win));
      controls.appendChild(closeBtn);
      titlebar.appendChild(controls);
    }

    win.appendChild(titlebar);

    // Body
    const body = document.createElement('div');
    body.className = 'w95-body';

    if (bodyContent) {
      body.appendChild(bodyContent);
    } else if (bodyHTML) {
      // bodyHTML is only used with trusted hardcoded strings in this codebase
      const temp = document.createElement('div');
      temp.innerHTML = bodyHTML; // SAFE: only called with hardcoded alert content
      while (temp.firstChild) body.appendChild(temp.firstChild);
    }

    // Buttons
    if (buttons.length) {
      const btnRow = document.createElement('div');
      btnRow.style.cssText = 'display:flex;gap:6px;justify-content:center;margin-top:10px;';
      buttons.forEach((b, i) => {
        const btn = document.createElement('button');
        btn.className = 'w95-btn' + (i === 0 ? ' default' : '');
        if (b.id) btn.id = b.id;
        btn.textContent = b.label;
        btnRow.appendChild(btn);
      });
      body.appendChild(btnRow);
    }

    win.appendChild(body);

    // Status bar
    if (statusbar) {
      const bar = document.createElement('div');
      bar.className = 'w95-statusbar';
      statusbar.forEach(s => {
        const sp = document.createElement('span');
        sp.textContent = s;
        bar.appendChild(sp);
      });
      win.appendChild(bar);
    }

    return win;
  }

  // ── Window Animations ─────────────────
  function showWindow(win, container, soundOverride) {
    container = container || document.getElementById('overlay-container') || document.body;
    container.appendChild(win);
    win.style.animation = 'w95-open 0.3s cubic-bezier(.175,.885,.32,1.275) forwards';
    playSound(soundOverride || './assets/sounds/popup.mp3', 0.5);
    return win;
  }

  function dismissWindow(win, callback) {
    win.style.animation = 'w95-close 0.18s ease forwards';
    setTimeout(() => {
      if (win.parentNode) win.parentNode.removeChild(win);
      if (callback) callback();
    }, 180);
  }

  // ── Animated Cursor ───────────────────
  function createCursor() {
    const cursor = document.createElement('div');
    cursor.className = 'w95-cursor';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M3 3L10.07 19.97L12.58 12.58L19.97 10.07L3 3Z');
    path.setAttribute('fill', 'white');
    path.setAttribute('stroke', 'black');
    path.setAttribute('stroke-width', '1.5');
    svg.appendChild(path);
    cursor.appendChild(svg);
    cursor.style.left = '-30px';
    cursor.style.top = '-30px';
    return cursor;
  }

  function moveCursorTo(cursor, target, callback) {
    const rect = target.getBoundingClientRect();
    const x = rect.left + rect.width / 2 - 5;
    const y = rect.top + rect.height / 2 - 2;
    cursor.style.left = x + 'px';
    cursor.style.top = y + 'px';
    setTimeout(() => {
      if (callback) callback();
    }, 450);
  }

  function moveCursorNatural(cursorEl, targetX, targetY, duration, callback) {
    const startX = parseFloat(cursorEl.style.left) || 0;
    const startY = parseFloat(cursorEl.style.top) || 0;
    const dx = targetX - startX;
    const dy = targetY - startY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    // Bezier control point perpendicular to the line for a natural arc
    const perpScale = 0.15 + Math.random() * 0.15;
    const side = Math.random() > 0.5 ? 1 : -1;
    const normX = -dy / (dist || 1);
    const normY = dx / (dist || 1);
    const cpX = (startX + targetX) / 2 + normX * dist * perpScale * side + (Math.random() - 0.5) * 20;
    const cpY = (startY + targetY) / 2 + normY * dist * perpScale * side + (Math.random() - 0.5) * 20;

    const startTime = performance.now();
    cursorEl.style.transition = 'none';

    function animate(now) {
      let t = Math.min((now - startTime) / duration, 1);
      t = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

      const x = (1 - t) * (1 - t) * startX + 2 * (1 - t) * t * cpX + t * t * targetX;
      const y = (1 - t) * (1 - t) * startY + 2 * (1 - t) * t * cpY + t * t * targetY;
      cursorEl.style.left = x + 'px';
      cursorEl.style.top = y + 'px';

      if (t < 1) {
        requestAnimationFrame(animate);
      } else if (callback) {
        callback();
      }
    }
    requestAnimationFrame(animate);
  }

  function clickButton(btn) {
    playSound('./assets/sounds/click.mp3', 0.4);
    btn.style.boxShadow = 'inset -1px -1px 0 #fff, inset 1px 1px 0 #000, inset -2px -2px 0 #dfdfdf, inset 2px 2px 0 #808080';
    btn.style.padding = '5px 19px 3px 21px';
    setTimeout(() => {
      btn.style.boxShadow = '';
      btn.style.padding = '';
    }, 150);
  }

  // ── Sound Playback ────────────────────
  function playSound(src, volume) {
    try {
      const audio = new Audio(src);
      audio.volume = typeof volume === 'number' ? volume : 0.7;
      audio.play().catch(() => {});
      return audio;
    } catch (e) {
      console.error('[WatsonOS] Sound error:', e);
      return null;
    }
  }

  // ── Utility ───────────────────────────
  function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Auto-connect on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }

  // ── Send Event via WebSocket ────────
  function sendEvent(type, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: type, data: data }));
    }
  }

  return {
    connect, on, sendEvent,
    createWindow, showWindow, dismissWindow,
    createCursor, moveCursorTo, moveCursorNatural, clickButton,
    playSound, randomInt, delay, escapeHtml
  };
})();
