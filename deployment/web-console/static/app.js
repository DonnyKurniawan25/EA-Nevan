const KEYS = {Backspace:0xff08, Enter:0xff0d, Tab:0xff09, Escape:0xff1b};
export function textKeysyms(text) {
  return Array.from(text.replace(/\r\n?/g, '\n')).flatMap(char => {
    const cp = char.codePointAt(0);
    if (char === '\n') return [KEYS.Enter];
    if (char === '\t') return [KEYS.Tab];
    if (char === '\b') return [KEYS.Backspace];
    if (cp < 32 || cp === 127 || (cp >= 0xd800 && cp <= 0xdfff)) return [];
    return [cp <= 255 ? cp : 0x01000000 + cp];
  });
}
export function controlKeysyms(name) {
  if (name === 'selectAll') return [[0xffe3,true],[97,true],[97,false],[0xffe3,false]];
  return KEYS[name] ? [[KEYS[name],true],[KEYS[name],false]] : [];
}
export function bindPhoneInput(input, send) {
  let composing = false, committed = false;
  const flush = () => { const symbols = textKeysyms(input.value); input.value = ''; symbols.forEach(send); };
  input.addEventListener('compositionstart', () => { composing = true; committed = false; });
  input.addEventListener('compositionend', () => { composing = false; committed = true; flush(); });
  input.addEventListener('input', e => {
    if (composing || e.isComposing) return;
    if (committed && /Composition$/.test(e.inputType || '')) { input.value = ''; committed = false; return; }
    committed = false; flush();
  });
  input.addEventListener('keydown', e => {
    e.stopPropagation();
    if (!composing && !e.isComposing && KEYS[e.key]) { e.preventDefault(); input.value = ''; send(KEYS[e.key]); }
  });
  input.addEventListener('keyup', e => e.stopPropagation());
  input.addEventListener('beforeinput', e => {
    if (composing || e.isComposing) return;
    const key = {deleteContentBackward:KEYS.Backspace, deleteContentForward:0xffff, insertLineBreak:KEYS.Enter, insertParagraph:KEYS.Enter}[e.inputType];
    if (key) { e.preventDefault(); input.value = ''; send(key); }
  });
}
export function consumeTicket(location, history) {
  const fragment = location.hash;
  if (fragment) history.replaceState(null, '', location.pathname + location.search);
  return /^#ticket=([A-Za-z0-9_-]{43})$/.exec(fragment)?.[1] ?? null;
}
export function websocketURL(base) {
  const url = new URL('/ea-console/ws', base);
  if (url.protocol === 'https:') { url.protocol = 'wss:'; url.port = ''; }
  else url.protocol = 'ws:';
  return url.href;
}

export async function boot(env = globalThis) {
  // Remove the one-use fragment before fetch or the protected module import.
  let ticket = consumeTicket(env.location, env.history);
  const doc = env.document;
  const el = id => doc.getElementById(id);
  const screen = el('screen'), input = el('phone-input');
  let rfb = null, expires = 0, busy = false, closed = false, generation = 0, zoomed = false;
  let timer;
  let cancelConnection = () => {};
  const connected = () => screen.dataset.status === 'true';
  const status = (title, message, live = false) => {
    el('status').textContent = title;
    el('message').textContent = message;
    screen.dataset.status = String(live);
    doc.body.dataset.connected = String(live);
    for (const button of doc.querySelectorAll('[data-key], #keyboard-toggle, #zoom')) button.disabled = !live;
  };
  const hideKeyboard = () => {
    input.value = ''; input.blur(); el('phone-keyboard').hidden = true;
    el('keyboard-toggle').setAttribute('aria-expanded', 'false');
    el('keyboard-toggle').textContent = 'Buka keyboard';
    if (rfb) rfb.focusOnClick = true;
  };
  const stop = () => {
    generation++; cancelConnection(); hideKeyboard();
    const current = rfb; rfb = null;
    if (current) current.disconnect();
    screen.dataset.status = 'false';
  };
  const expired = (message = 'Akses berakhir. Minta link privat baru; link lama tidak dapat dipakai ulang.') => {
    closed = true; stop(); env.clearInterval(timer);
    status('Akses berakhir', message); el('remaining').textContent = 'Sesi tidak aktif';
    el('reconnect').disabled = true;
  };
  const request = async (path, options = {}) => {
    const response = await env.fetch('./api/' + path, {
      credentials: 'same-origin', cache: 'no-store', ...options,
      headers: {'X-EA-Console': '1', ...(options.body ? {'Content-Type':'application/json'} : {})}
    });
    if (!response.ok) { const error = new Error('request'); error.status = response.status; throw error; }
    return response.status === 204 ? {} : response.json();
  };
  const setExpiry = value => {
    const parsed = typeof value === 'number' ? (value < 1e12 ? value * 1000 : value) : Date.parse(value);
    if (!Number.isFinite(parsed) || parsed <= Date.now()) throw Object.assign(new Error('expired'), {status:401});
    expires = expires ? Math.min(expires, parsed) : parsed;
  };
  const tick = () => {
    const seconds = Math.max(0, Math.ceil((expires - Date.now()) / 1000));
    if (!seconds) return expired();
    el('remaining').textContent = 'Sisa ' + Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  };
  const send = sym => { if (connected() && rfb) rfb.sendKey(sym); };
  bindPhoneInput(input, send);
  el('keyboard-toggle').addEventListener('click', () => {
    if (!connected()) return;
    if (!el('phone-keyboard').hidden) return hideKeyboard();
    rfb.focusOnClick = false; rfb.blur();
    el('phone-keyboard').hidden = false;
    el('keyboard-toggle').textContent = 'Tutup keyboard';
    el('keyboard-toggle').setAttribute('aria-expanded', 'true');
    input.focus({preventScroll:true});
  });
  for (const button of doc.querySelectorAll('[data-key]')) {
    button.addEventListener('pointerdown', e => { if (!el('phone-keyboard').hidden) e.preventDefault(); });
    button.addEventListener('click', () => {
      if (!connected() || !rfb) return;
      for (const [sym, down] of controlKeysyms(button.dataset.key)) rfb.sendKey(sym, null, down);
    });
  }
  const applyZoom = () => {
    if (!rfb) return;
    rfb.scaleViewport = !zoomed; rfb.clipViewport = zoomed; rfb.dragViewport = zoomed;
    el('zoom').setAttribute('aria-pressed', String(zoomed));
    el('zoom').textContent = zoomed ? 'Pas layar' : 'Perbesar & geser';
  };
  el('zoom').addEventListener('click', () => { zoomed = !zoomed; applyZoom(); });
  const connect = async () => {
    if (busy || closed) return;
    busy = true; stop(); const attempt = generation;
    el('reconnect').disabled = true;
    status('Menyambungkan', 'Memeriksa akses desktop privat…');
    let connection;
    const controller = new AbortController();
    const deadline = env.setTimeout(() => {
      if (closed || attempt !== generation || connected()) return;
      stop(); busy = false;
      status('Koneksi tertunda', 'Layar belum tersambung. Tekan Sambungkan ulang atau muat ulang halaman ini.');
      el('reconnect').disabled = false;
    }, 20000);
    cancelConnection = () => {
      env.clearTimeout(deadline); controller.abort();
      if (connection) connection.password = '';
      connection = null;
    };
    try {
      connection = await request('connection', {method:'POST', signal:controller.signal});
      if (closed || attempt !== generation) return;
      setExpiry(connection.expires_at);
      status('Memuat layar', 'Memuat komponen desktop privat…');
      const {default:RFB} = env.loadRFB ? await env.loadRFB() : await import('./vendor/core/rfb.js');
      if (closed || attempt !== generation) return;
      status('Menyambungkan', 'Membuka koneksi layar MT5…');
      rfb = new RFB(screen, websocketURL(env.location.href), {credentials:{password:connection.password}, shared:true});
      connection.password = ''; connection = null;
      rfb.resizeSession = false; rfb.focusOnClick = true; applyZoom();
      rfb.addEventListener('connect', () => {
        if (closed || attempt !== generation) return;
        cancelConnection();
        status('Terhubung', 'Login: klik File di kiri atas layar MT5 → Login to Trade Account.', true);
        el('reconnect').disabled = false;
      });
      rfb.addEventListener('disconnect', () => {
        if (closed || attempt !== generation) return;
        cancelConnection();
        hideKeyboard(); status('Terputus', 'Koneksi terputus. Sambungkan ulang selama sesi masih aktif.');
        el('reconnect').disabled = false;
      });
      rfb.addEventListener('securityfailure', () => {
        if (attempt === generation) expired('Koneksi privat ditolak. Minta link privat baru.');
      });
    } catch (error) {
      if (closed || attempt !== generation) return;
      cancelConnection();
      if (error.status === 401 || error.status === 403) expired();
      else { status('Belum terhubung', 'Server belum dapat dihubungi. Coba sambungkan ulang.'); el('reconnect').disabled = false; }
    } finally {
      if (connection) connection.password = '';
      connection = null;
      if (attempt === generation) busy = false;
    }
  };
  el('reconnect').addEventListener('click', connect);
  el('logout').addEventListener('click', async () => {
    el('logout').disabled = true;
    expired('Akses ditutup. MT5 tetap berjalan di server.');
    try { await request('logout', {method:'POST'}); }
    catch { el('message').textContent = 'Desktop terputus, tetapi penutupan sesi belum terkonfirmasi. Coba Tutup akses lagi.'; el('logout').disabled = false; }
  });
  env.addEventListener?.('pagehide', () => { stop(); env.clearInterval(timer); });
  try {
    let session;
    if (ticket) {
      const body = JSON.stringify({ticket}); ticket = null;
      session = await request('session', {method:'POST', body});
    } else { ticket = null; session = await request('session'); }
    setExpiry(session.expires_at); tick(); timer = env.setInterval(tick, 1000);
    if (!closed) await connect();
  } catch {
    ticket = null; expired('Link tidak valid atau sesi berakhir. Minta link privat baru, lalu buka di browser ini.');
  }
}
if (typeof document !== 'undefined') void boot();
