// app.js —— nanocode Web 前端：聊天 + 表情包 + 记忆状态面板
// 视觉与交互沿用 Edurag integrated_qa_system 的深色玻璃拟态风格

const chatEl = document.getElementById('chat');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const statusTextEl = document.getElementById('statusText');
const memListEl = document.getElementById('memList');
const appEl = document.getElementById('app');
const sidebarToggle = document.getElementById('sidebarToggle');
const newChatBtn = document.getElementById('newChat');
const memeSwitchEl = document.getElementById('memeSwitch');
const statAffinityEl = document.getElementById('statAffinity');
const statMoodEl = document.getElementById('statMood');
const statTimeEl = document.getElementById('statTime');
const affinityBarEl = document.getElementById('affinityBar');

let busy = false;
let memeOn = localStorage.getItem('nanocode_meme') !== 'off';

/* ---------------- 渲染工具 ---------------- */

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

/** 普通文本 -> HTML：转义 + 行内代码 + 换行 */
function textToHtml(str) {
  return escapeHtml(str)
    .replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\n/g, '<br>');
}

/** 渲染单个代码块（右上角带复制按钮） */
function buildCodeBlock(lang, code) {
  return `<div class="code-block">` +
    `<div class="code-head">` +
      `<span class="code-lang">${escapeHtml(lang)}</span>` +
      `<button type="button" class="copy-btn">复制</button>` +
    `</div>` +
    `<pre><code>${escapeHtml(code)}</code></pre>` +
    `</div>`;
}

/** 富文本渲染：``` 围栏代码块 -> 可复制代码块 */
function renderRich(text) {
  const src = String(text ?? '');
  const fence = /```([\w#+.\-]*)[ \t]*\n?([\s\S]*?)```/g;

  let html = '';
  let last = 0;
  let m;

  while ((m = fence.exec(src)) !== null) {
    const before = src.slice(last, m.index).replace(/\n+$/, '');
    if (before) html += textToHtml(before);

    const lang = (m[1] || 'code').trim() || 'code';
    const code = m[2].replace(/\n$/, '');
    html += buildCodeBlock(lang, code);

    last = m.index + m[0].length;
  }

  const tail = src.slice(last).replace(/^\n+/, '');
  if (tail) html += textToHtml(tail);

  return html;
}

/** 复制文本到剪贴板（http 环境下自动降级） */
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {
    /* 走降级方案 */
  }

  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;top:-1000px;left:-1000px;opacity:0;';
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}

function setStatus(type, text) {
  statusEl.classList.remove('busy', 'error');
  if (type === 'busy') statusEl.classList.add('busy');
  if (type === 'error') statusEl.classList.add('error');
  statusTextEl.textContent = text;
}

/* ---------------- 消息气泡 ---------------- */

function addMessage(role, html, opts = {}) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${role === 'user' ? 'user' : 'bot'}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? '我' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'bubble rich';
  bubble.innerHTML = html;

  wrap.append(avatar, bubble);
  chatEl.appendChild(wrap);

  // 表情包：附在 AI 气泡下方
  if (opts.meme) {
    const img = document.createElement('img');
    img.className = 'meme-img';
    img.src = opts.meme;
    img.alt = '表情包';
    img.loading = 'lazy';
    bubble.appendChild(img);
  }

  scrollToBottom();
  return wrap;
}

function addTyping() {
  const wrap = document.createElement('div');
  wrap.className = 'msg bot';
  wrap.innerHTML =
    '<div class="avatar">AI</div>' +
    '<div class="bubble"><span class="typing"><i></i><i></i><i></i></span>' +
    '<span class="typing-text">思考中…</span></div>';
  chatEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

/* ---------------- 记忆状态面板 ---------------- */

async function refreshState() {
  try {
    const state = await (await fetch('/api/state')).json();
    statAffinityEl.textContent = state.affinity ?? '--';
    statMoodEl.textContent = state.mood_label ?? '--';
    statTimeEl.textContent = state.updated_at
      ? state.updated_at.replace('T', ' ').slice(5, 16)
      : '--';
    affinityBarEl.style.width =
      Math.max(0, Math.min(100, Number(state.affinity) || 50)) + '%';

    const data = await (await fetch('/api/memories')).json();
    const items = data.items || [];
    memListEl.innerHTML = '';
    if (!items.length) {
      memListEl.innerHTML = '<div class="conv-empty">还没有记忆条目</div>';
      return;
    }
    items.forEach((item) => {
      const div = document.createElement('div');
      div.className = 'conv-item';
      div.innerHTML =
        `<div class="conv-info">` +
          `<div class="conv-title">${escapeHtml(item.title)}</div>` +
          `<div class="conv-sub">${escapeHtml(item.date.slice(5))} ${escapeHtml(item.time || '')}` +
          `${item.affinity != null ? ' · 好感度 ' + item.affinity : ''}</div>` +
        `</div>`;
      div.addEventListener('click', () => {
        addMessage(
          'bot',
          `<span class="badge faq">记忆</span> ${escapeHtml(item.date)} ${escapeHtml(item.time || '')}<br>` +
          textToHtml(item.text || '')
        );
      });
      memListEl.appendChild(div);
    });
  } catch (e) {
    /* 面板刷新失败不打扰聊天 */
  }
}

/* ---------------- 发送 ---------------- */

async function send() {
  const text = inputEl.value.trim();
  if (!text || busy) return;

  busy = true;
  sendBtn.disabled = true;
  sendBtn.classList.add('loading');
  setStatus('busy', '思考中');

  addMessage('user', textToHtml(text));
  inputEl.value = '';
  inputEl.style.height = 'auto';

  const typing = addTyping();
  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    const data = await resp.json();
    typing.remove();

    if (data.error) {
      addMessage('bot', `<span class="badge miss">错误</span> ${escapeHtml(data.error)}`);
      setStatus('error', '出错');
    } else {
      addMessage('bot', renderRich(data.reply || ''), {
        meme: memeOn ? data.meme : null,
      });
      setStatus('ok', '就绪');
      refreshState();
    }
  } catch (err) {
    typing.remove();
    addMessage('bot', `<span class="badge miss">错误</span> ${escapeHtml(String(err))}`);
    setStatus('error', '网络错误');
  } finally {
    busy = false;
    sendBtn.disabled = false;
    sendBtn.classList.remove('loading');
    inputEl.focus();
  }
}

/* ---------------- 事件绑定 ---------------- */

sendBtn.addEventListener('click', send);

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

// 输入框随内容增高
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
});

newChatBtn.addEventListener('click', async () => {
  await fetch('/api/reset', { method: 'POST' });
  chatEl.innerHTML = '';
  addMessage(
    'bot',
    '新对话开始了。<br>我仍记得你——侧边栏里是最近的记忆条目。'
  );
  setStatus('ok', '就绪');
  refreshState();
});

sidebarToggle.addEventListener('click', () => {
  appEl.classList.toggle('sidebar-open');
});

memeSwitchEl.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  memeOn = btn.dataset.meme === 'on';
  localStorage.setItem('nanocode_meme', memeOn ? 'on' : 'off');
  memeSwitchEl.querySelectorAll('button').forEach((b) => {
    b.classList.toggle('active', b === btn);
  });
});

// 代码块复制按钮（事件委托）
chatEl.addEventListener('click', async (e) => {
  const btn = e.target.closest('.copy-btn');
  if (!btn) return;
  const code = btn.closest('.code-block').querySelector('code').textContent;
  const ok = await copyText(code);
  btn.textContent = ok ? '已复制' : '复制失败';
  btn.classList.toggle('done', ok);
  setTimeout(() => {
    btn.textContent = '复制';
    btn.classList.remove('done');
  }, 1500);
});

// 初始化：同步表情包开关状态 + 拉记忆面板
memeSwitchEl.querySelectorAll('button').forEach((b) => {
  b.classList.toggle('active', (b.dataset.meme === 'on') === memeOn);
});
refreshState();
inputEl.focus();
