/* ═══════════════════════════════════════════════════════════════
   Floating Chat Widget — shared across all dashboard pages
   Self-contained: injects its own styles + HTML + wires events.
   Depends on: data/ai_config.json, data/chatbot_context.json,
               data/chatbot_prices_index.json, POST /api/chat
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // Don't inject twice (e.g., if this file is included on chatbot.html
  // which already has the full-page chatbot).
  if (document.getElementById('chatWidget')) return;
  if (document.body && document.body.classList.contains('no-chat-widget')) return;

  // ── Styles ──────────────────────────────────────────────────
  const STYLE = `
@keyframes chatSlideUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes chatDot { 0%,80%,100%{opacity:0.2} 40%{opacity:1} }

#chatWidget {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.65rem;
  font-family: var(--font-sans, 'DM Sans', system-ui, sans-serif);
}

#chatToggle {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: var(--gold, #c9a84c);
  border: none;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 18px rgba(0,0,0,0.45);
  transition: background 0.15s, transform 0.15s;
}
#chatToggle:hover { background: #e0bb5a; transform: scale(1.05); }
#chatToggle svg { width: 22px; height: 22px; color: #0c0a08; }
[data-theme="light"] #chatToggle { box-shadow: 0 4px 18px rgba(73,53,20,0.22); }

#chatPanel {
  width: 360px;
  max-height: 520px;
  background: var(--bg-card, #131109);
  border: 1px solid var(--border, rgba(255,255,255,0.07));
  border-radius: 10px;
  box-shadow: 0 8px 36px rgba(0,0,0,0.55);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: chatSlideUp 0.22s ease;
}
[data-theme="light"] #chatPanel {
  box-shadow: 0 12px 40px rgba(73,53,20,0.22);
}

#chatPanelHeader {
  padding: 0.75rem 1rem;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
#chatPanelHeader .chat-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.45rem;
  letter-spacing: 0.02em;
}
#chatPanelHeader .chat-title::before {
  content: '';
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--gold);
}
#chatModelBadge {
  font-size: 0.58rem;
  color: var(--text-dim);
  font-family: var(--font-mono);
}

#chatMessages {
  flex: 1;
  overflow-y: auto;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.chat-msg {
  max-width: 88%;
  font-size: 0.77rem;
  line-height: 1.5;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  word-break: break-word;
}
.chat-msg.user {
  align-self: flex-end;
  background: var(--gold-subtle);
  color: var(--text-primary);
  border: 1px solid var(--gold-border);
}
.chat-msg.assistant {
  align-self: flex-start;
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.chat-msg.system-notice {
  align-self: center;
  background: transparent;
  color: var(--text-dim);
  font-size: 0.68rem;
  border: none;
  padding: 0.25rem 0;
  text-align: center;
}

.chat-typing {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0.55rem 0.75rem;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.chat-typing span {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--text-dim);
  animation: chatDot 1.2s infinite;
}
.chat-typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-typing span:nth-child(3) { animation-delay: 0.4s; }

#chatInputRow {
  padding: 0.65rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.45rem;
  flex-shrink: 0;
  background: var(--bg-surface);
}
#chatInput {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.75rem;
  padding: 0.45rem 0.65rem;
  outline: none;
  transition: border-color 0.15s;
}
#chatInput:focus { border-color: var(--gold); }
#chatInput::placeholder { color: var(--text-dim); }
#chatSend {
  background: var(--gold);
  color: #0c0a08;
  border: none;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}
#chatSend:hover { background: #e0bb5a; }
#chatSend:disabled { opacity: 0.45; cursor: not-allowed; }

@media (max-width: 640px) {
  #chatWidget { bottom: 1rem; right: 1rem; }
  #chatPanel { width: calc(100vw - 2rem); max-width: 360px; }
}
`;

  const styleEl = document.createElement('style');
  styleEl.id = 'chatWidgetStyles';
  styleEl.textContent = STYLE;
  document.head.appendChild(styleEl);

  // ── Markup ──────────────────────────────────────────────────
  const HTML = `
<div id="chatWidget">
  <div id="chatPanel" style="display:none;">
    <div id="chatPanelHeader">
      <div class="chat-title">Price Intelligence AI</div>
      <span id="chatModelBadge">loading…</span>
    </div>
    <div id="chatMessages">
      <div class="chat-msg system-notice">
        Ask about competitor pricing, trends, or strategy recommendations.
      </div>
      <div class="chat-msg assistant">
        I have access to daily pricing data for all four NYC observation decks: ESB, Edge, Summit, and Top of the Rock. What would you like to know?
      </div>
    </div>
    <div id="chatInputRow">
      <input id="chatInput" type="text" placeholder="How does ESB compare to Edge on sunset pricing?" maxlength="400" />
      <button id="chatSend">Send</button>
    </div>
  </div>

  <button id="chatToggle" title="Price Intelligence AI" aria-label="Toggle chat">
    <svg id="chatIconOpen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
    <svg id="chatIconClose" style="display:none;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  </button>
</div>
`;

  function mount() {
    if (document.getElementById('chatWidget')) return;
    const tmpl = document.createElement('template');
    tmpl.innerHTML = HTML.trim();
    document.body.appendChild(tmpl.content.firstChild);
    init();
  }

  // ── Chatbot logic (mirrors the old index.html inline version) ──
  const DATA = 'data/';
  let chatEnabled = false;
  let chatModel = 'google/gemini-3-flash-preview';
  let systemPrompt = '';
  let pricesIndex = null;
  let history = [];
  let isOpen = false;
  let isStreaming = false;
  let lastDate = null;
  let lastTime = null;

  const CHAT_SYSTEM_PREFIX = `You are a competitive pricing analyst for NYC observation decks (ESB, Edge Hudson Yards, Summit One Vanderbilt, Top of the Rock). Answer directly and concisely using exact numbers from your context.

CRITICAL VOCABULARY RULES (non-negotiable, zero exceptions):
- NEVER write the word "slot" or "slots". The correct term is "tour time" or "tour times". This applies to every response, every phrase, every context. "sunset slot" is wrong. "sunset tour time" is correct. "time slot" is wrong. "tour time" is correct.
- NEVER write the word "venue" or "venues". The correct term is "attraction" or "attractions".
- These are hard errors. Violating them invalidates the response.

Correct: "ESB sunset tour times run 5:00 PM to 7:15 PM."
Wrong:   "ESB sunset slots run 5:00 PM to 7:15 PM."

Rules: Use $X.XX for all prices. Answer in 1 to 3 sentences for simple questions. When a [PRICE DATA ...] block is present in the user message, use those exact scraped numbers as the live source of truth; they override everything else. All-in prices include booking fees.

Example 1:
User: [PRICE DATA 2026-04-20 ~17:00: ESB: 5:00 PM=$61.00★sunset, 5:15 PM=$61.00★sunset | Edge: 4:45 PM=$58.00, 5:00 PM=$61.00 | Summit: 5:00 PM=$63.00 | TOR: 4:30 PM=$55.00, 5:00 PM=$58.00]
USER QUESTION: What's the ESB price at 5 pm on April 20?
Assistant: ESB is $61.00 at 5:00 PM on April 20. This is in the sunset window.

Example 2 (follow-up with no new date):
User: [PRICE DATA 2026-04-20 ~17:00: ESB: 5:00 PM=$61.00★sunset | Edge: 4:45 PM=$58.00, 5:00 PM=$61.00 | Summit: 5:00 PM=$63.00 | TOR: 5:00 PM=$58.00]
USER QUESTION: What about edge?
Assistant: Edge is $58.00 at 4:45 PM and $61.00 at 5:00 PM on April 20.

Example 3 (sunset window question):
User: What time is sunset at each attraction?
Assistant: ESB sunset tour times run 5:00 PM to 7:15 PM. Edge sunset tour times run 5:00 PM to 7:10 PM. Summit and TOR use variable tiered pricing through the evening rather than publishing a fixed sunset window.

MARKET DATA (pricing + website intelligence):
`;

  function parseQueryDate(text) {
    const t = text.toLowerCase();
    if (/\btoday\b/.test(t)) return new Date().toISOString().slice(0, 10);
    if (/\btomorrow\b/.test(t)) {
      const d = new Date(); d.setDate(d.getDate() + 1);
      return d.toISOString().slice(0, 10);
    }
    let m = t.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;
    m = t.match(/(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
    if (m) {
      const yr = m[3] ? (m[3].length === 2 ? '20' + m[3] : m[3]) : '2026';
      return `${yr}-${m[1].padStart(2,'0')}-${m[2].padStart(2,'0')}`;
    }
    const months = {jan:'01',feb:'02',mar:'03',apr:'04',may:'05',jun:'06',
                    jul:'07',aug:'08',sep:'09',oct:'10',nov:'11',dec:'12'};
    m = t.match(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:[a-z]{2})?\b/);
    if (m && months[m[1]]) {
      return `2026-${months[m[1]]}-${m[2].padStart(2,'0')}`;
    }
    return null;
  }

  function parseQueryTime(text) {
    const t = text.toLowerCase();
    let h = null, m = 0;
    let match = t.match(/(\d{1,2}):(\d{2})\s*(am|pm)/);
    if (match) {
      h = parseInt(match[1]); m = parseInt(match[2]);
      if (match[3] === 'pm' && h !== 12) h += 12;
      if (match[3] === 'am' && h === 12) h = 0;
      return { h, m };
    }
    match = t.match(/\b(\d{1,2})\s*(am|pm)\b/);
    if (match) {
      h = parseInt(match[1]);
      if (match[2] === 'pm' && h !== 12) h += 12;
      if (match[2] === 'am' && h === 12) h = 0;
      return { h, m: 0 };
    }
    match = t.match(/\b(\d{2}):(\d{2})\b/);
    if (match) {
      h = parseInt(match[1]); m = parseInt(match[2]);
      if (h >= 0 && h <= 23) return { h, m };
    }
    match = t.match(/\bat\s+(\d{1,2})\b(?!\s*(?:am|pm|:\d))/);
    if (match) {
      h = parseInt(match[1]);
      if (h >= 1 && h <= 11) h += 12;
      if (h >= 12 && h <= 23) return { h, m: 0 };
    }
    return null;
  }

  function parseTourTime(tt) {
    const t = tt.toUpperCase().replace(/\u202F/g, ' ');
    let m = t.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/);
    if (m) {
      let h = parseInt(m[1]); const min = parseInt(m[2]);
      if (m[3] === 'PM' && h !== 12) h += 12;
      if (m[3] === 'AM' && h === 12) h = 0;
      return { h, m: min };
    }
    m = t.match(/(\d{1,2})\s*(AM|PM)/);
    if (m) {
      let h = parseInt(m[1]);
      if (m[2] === 'PM' && h !== 12) h += 12;
      if (m[2] === 'AM' && h === 12) h = 0;
      return { h, m: 0 };
    }
    return null;
  }

  function buildPriceBlock(date, targetTime) {
    if (!pricesIndex) return '';
    const SHORT = { esb: 'ESB', edge: 'Edge', summit: 'Summit', totr: 'TOR' };
    const timeStr = targetTime ? ` ~${targetTime.h}:${String(targetTime.m).padStart(2,'0')}` : '';
    const parts = [];

    for (const vk of ['esb', 'edge', 'summit', 'totr']) {
      const dateRows = pricesIndex[vk]?.[date];
      if (!dateRows || dateRows.length === 0) continue;
      const key = SHORT[vk];

      if (targetTime) {
        const targetMins = targetTime.h * 60 + targetTime.m;
        let rows = dateRows.filter(r => {
          const tt = parseTourTime(r.t);
          return tt && Math.abs((tt.h * 60 + tt.m) - targetMins) <= 90;
        });
        if (rows.length === 0) {
          rows = [...dateRows].sort((a, b) => {
            const ta = parseTourTime(a.t), tb = parseTourTime(b.t);
            if (!ta || !tb) return 0;
            return Math.abs((ta.h*60+ta.m) - targetMins) - Math.abs((tb.h*60+tb.m) - targetMins);
          }).slice(0, 2);
        }
        const items = rows.map(r => `${r.t}=$${(r.p/100).toFixed(2)}${r.s ? '★sunset' : ''}`).join(', ');
        parts.push(`${key}: ${items}`);
      } else {
        const sorted = [...dateRows].sort((a, b) => {
          const ta = parseTourTime(a.t), tb = parseTourTime(b.t);
          if (!ta || !tb) return 0;
          return (ta.h * 60 + ta.m) - (tb.h * 60 + tb.m);
        });
        let sample;
        if (sorted.length <= 10) {
          sample = sorted;
        } else {
          const sunsets = sorted.filter(r => r.s);
          const others  = sorted.filter(r => !r.s);
          const step = Math.max(1, Math.floor(others.length / (10 - sunsets.length)));
          const picked = [];
          for (let i = 0; i < others.length && picked.length < (10 - sunsets.length); i += step) {
            picked.push(others[i]);
          }
          sample = [...picked, ...sunsets].sort((a, b) => {
            const ta = parseTourTime(a.t), tb = parseTourTime(b.t);
            if (!ta || !tb) return 0;
            return (ta.h * 60 + ta.m) - (tb.h * 60 + tb.m);
          });
        }
        const items = sample.map(r => `${r.t}=$${(r.p/100).toFixed(2)}${r.s ? '★' : ''}`).join(', ');
        const extra = sorted.length > 10 ? ` (+${sorted.length - sample.length} more)` : '';
        parts.push(`${key}: ${items}${extra}`);
      }
    }

    if (parts.length === 0) return '';
    return `[PRICE DATA ${date}${timeStr}: ${parts.join(' | ')}]`;
  }

  function init() {
    Promise.all([
      fetch(DATA + 'ai_config.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(DATA + 'chatbot_context.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(DATA + 'chatbot_prices_index.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([cfg, ctx, pidx]) => {
      if (cfg) {
        chatEnabled = cfg.chat_enabled !== false;
        chatModel = cfg.chat_model || chatModel;
      }
      if (ctx) {
        systemPrompt = CHAT_SYSTEM_PREFIX + (ctx.context || '');
      } else {
        systemPrompt = CHAT_SYSTEM_PREFIX + 'Pricing data context not yet loaded. Please run the daily refresh.';
      }
      if (pidx) pricesIndex = pidx;

      const badge = document.getElementById('chatModelBadge');
      if (badge) {
        const parts = [chatModel.split('/').pop()];
        if (ctx?.has_website_intel) parts.push('web intel');
        if (pidx) parts.push('live prices');
        badge.textContent = parts.join(' · ');
      }
    }).catch(() => {});

    document.getElementById('chatToggle').addEventListener('click', toggleChatPanel);
    document.getElementById('chatSend').addEventListener('click', sendMessage);
    document.getElementById('chatInput').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }

  function toggleChatPanel() {
    isOpen = !isOpen;
    const panel = document.getElementById('chatPanel');
    panel.style.display = isOpen ? 'flex' : 'none';
    panel.style.flexDirection = 'column';
    document.getElementById('chatIconOpen').style.display  = isOpen ? 'none' : '';
    document.getElementById('chatIconClose').style.display = isOpen ? ''     : 'none';
    if (isOpen) {
      setTimeout(() => document.getElementById('chatInput').focus(), 80);
    }
  }
  window.toggleChatPanel = toggleChatPanel;

  function sendMessage() {
    if (isStreaming) return;
    const input = document.getElementById('chatInput');
    const text  = input.value.trim();
    if (!text) return;
    if (!chatEnabled) {
      appendMsg('assistant', 'AI is not enabled for this deployment.');
      return;
    }

    input.value = '';
    appendMsg('user', text);

    let augmentedText = text;
    if (pricesIndex) {
      const detectedDate = parseQueryDate(text);
      const detectedTime = parseQueryTime(text);
      if (detectedDate) { lastDate = detectedDate; }
      if (detectedTime) { lastTime = detectedTime; }
      if (detectedTime && !detectedDate && !lastDate) {
        lastDate = new Date().toISOString().slice(0, 10);
      }
      const lookupDate = detectedDate || lastDate;
      const lookupTime = detectedTime || lastTime;
      if (lookupDate) {
        const priceBlock = buildPriceBlock(lookupDate, lookupTime);
        if (priceBlock) {
          augmentedText = priceBlock + '\n\nUSER QUESTION: ' + text;
        }
      }
    }

    history.push({ role: 'user', content: augmentedText });

    isStreaming = true;
    document.getElementById('chatSend').disabled = true;

    const typing = document.createElement('div');
    typing.className = 'chat-typing';
    typing.id = 'chatTyping';
    typing.innerHTML = '<span></span><span></span><span></span>';
    document.getElementById('chatMessages').appendChild(typing);
    scrollChat();

    const messages = [
      { role: 'system', content: systemPrompt },
      ...history.slice(-12),
    ];

    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model:       chatModel,
        messages,
        temperature: 0.3,
        max_tokens:  600,
      }),
    })
    .then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || `API ${r.status}`);
      const reply = data.choices?.[0]?.message?.content || 'No response.';
      history.push({ role: 'assistant', content: reply });
      document.getElementById('chatTyping')?.remove();
      appendMsg('assistant', reply);
    })
    .catch(err => {
      document.getElementById('chatTyping')?.remove();
      appendMsg('assistant', 'Error: ' + err.message);
    })
    .finally(() => {
      isStreaming = false;
      document.getElementById('chatSend').disabled = false;
      document.getElementById('chatInput').focus();
    });
  }

  function appendMsg(role, text) {
    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    div.textContent = text;
    document.getElementById('chatMessages').appendChild(div);
    scrollChat();
  }

  function scrollChat() {
    const el = document.getElementById('chatMessages');
    el.scrollTop = el.scrollHeight;
  }

  // Mount only after all const/let declarations above have initialized
  // (otherwise a synchronous mount() → init() would hit the TDZ on DATA).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
