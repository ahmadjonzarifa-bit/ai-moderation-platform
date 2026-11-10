let currentQueue = "attention";

// DOM элементы
const statTotal = document.getElementById("statTotal");
const statAttention = document.getElementById("statAttention");
const statPublished = document.getElementById("statPublished");
const statQuarantine = document.getElementById("statQuarantine");
const statRejectedAi = document.getElementById("statRejectedAi");
const statRegexBlocked = document.getElementById("statRegexBlocked");
const tabBadgeAttention = document.getElementById("tabBadgeAttention");

const messagesContainer = document.getElementById("messagesContainer");
const regexContainer = document.getElementById("regexContainer");
const allMessagesFilterBar = document.getElementById("allMessagesFilterBar");
const refreshBtn = document.getElementById("refreshBtn");

const filterStatus = document.getElementById("filterStatus");
const filterType = document.getElementById("filterType");
const filterHasReports = document.getElementById("filterHasReports");

// Загрузка статистики
async function loadStats() {
  try {
    const res = await fetch("/api/v1/admin/stats");
    if (!res.ok) return;
    const s = await res.json();

    statTotal.textContent = s.total_messages;
    const attentionCount = s.quarantined_count + s.pending_count;
    statAttention.textContent = attentionCount;
    tabBadgeAttention.textContent = attentionCount;
    statPublished.textContent = s.published_count;
    statQuarantine.textContent = s.quarantined_count;
    statRejectedAi.textContent = s.rejected_ai_count;
    statRegexBlocked.textContent = s.regex_blocked_count;
  } catch (err) {
    console.error("Ошибка загрузки статистики:", err);
  }
}

// Загрузка очереди сообщений
async function loadMessages() {
  if (currentQueue === "regex") {
    loadRegexLogs();
    return;
  }

  messagesContainer.innerHTML = `<div class="loading-state">Загрузка сообщений...</div>`;

  try {
    let url = "/api/v1/admin/messages?";
    if (currentQueue === "attention") {
      url += "queue=attention";
    } else {
      if (filterStatus.value) url += `status=${filterStatus.value}&`;
      if (filterType.value) url += `type=${filterType.value}&`;
      if (filterHasReports.checked) url += `has_reports=true&`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error("Не удалось загрузить сообщения");
    const list = await res.json();

    if (list.length === 0) {
      messagesContainer.innerHTML = `<div class="loading-state">Нет сообщений в данной очереди 🎉</div>`;
      return;
    }

    messagesContainer.innerHTML = list.map(msg => renderAdminCard(msg)).join("");
  } catch (err) {
    messagesContainer.innerHTML = `<div class="loading-state">Ошибка загрузки: ${err.message}</div>`;
  }
}

// Загрузка логов блокировок RegEx
async function loadRegexLogs() {
  regexContainer.innerHTML = `<div class="loading-state">Загрузка логов RegEx...</div>`;

  try {
    const res = await fetch("/api/v1/admin/regex-logs");
    if (!res.ok) throw new Error("Не удалось загрузить логи");
    const logs = await res.json();

    if (logs.length === 0) {
      regexContainer.innerHTML = `<div class="loading-state">Пока нет зафиксированных блокировок RegEx.</div>`;
      return;
    }

    let html = `
      <table class="regex-table">
        <thead>
          <tr>
            <th>Дата и время</th>
            <th>Пользователь / IP</th>
            <th>Причина блокировки</th>
            <th>Текст сообщения</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const item of logs) {
      const date = new Date(item.created_at).toLocaleString("ru-RU");
      html += `
        <tr>
          <td style="white-space: nowrap; color: #64748b;">${date}</td>
          <td><strong>${escapeHtml(item.user_ip || 'IP не указан')}</strong></td>
          <td style="color: #dc2626; font-weight: 600;">${escapeHtml(item.violation_reason)}</td>
          <td style="word-break: break-word; max-width: 400px;">${escapeHtml(item.original_text)}</td>
        </tr>
      `;
    }

    html += `</tbody></table>`;
    regexContainer.innerHTML = html;
  } catch (err) {
    regexContainer.innerHTML = `<div class="loading-state">Ошибка загрузки логов: ${err.message}</div>`;
  }
}

function renderAdminCard(msg) {
  const statusClass = msg.status.toLowerCase();
  const dateStr = new Date(msg.created_at).toLocaleString("ru-RU");
  const confidencePercent = msg.ai_confidence ? Math.round(msg.ai_confidence * 100) + "%" : "—";

  // Теги нарушений
  const violationsHtml = (msg.ai_violations && msg.ai_violations.length > 0)
    ? msg.ai_violations.map(v => `<span class="v-tag">${v}</span>`).join("")
    : "";

  // Блок жалоб
  let reportsHtml = "";
  if (msg.reports_count > 0 && msg.reports && msg.reports.length > 0) {
    reportsHtml = `
      <div class="card-reports-summary">
        <div class="reports-count-title">⚠️ Поступило жалоб: ${msg.reports_count}</div>
        ${msg.reports.map(r => `
          <div class="report-item">
            <span>• [<strong>${r.reason}</strong>]:</span>
            <span>${escapeHtml(r.comment || 'Без комментария')}</span>
            <span style="color: #991b1b; opacity: 0.8;">(${r.reporter_ip})</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  return `
    <div class="admin-card status-${statusClass}" id="admin-card-${msg.id}">
      <!-- Шапка карточки -->
      <div class="card-meta-bar">
        <div class="meta-left">
          <span class="meta-id">#${msg.id.substring(0, 8)}</span>
          <span class="meta-author">${escapeHtml(msg.user_name)}</span>
          <span class="meta-ip">IP: ${escapeHtml(msg.user_ip || '127.0.0.1')}</span>
          <span class="meta-date">${dateStr}</span>
          <span class="badge-review">${msg.type}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${msg.verified_by_human ? '<span class="human-verified-pill">🛡️ Проверено модератором</span>' : ''}
          <span class="status-badge ${statusClass}">${msg.status}</span>
        </div>
      </div>

      <!-- Блок текста: 3 колонки (Оригинал, Перевод RU, Перевод UZ) -->
      <div class="text-columns-grid">
        <div class="text-col">
          <div class="col-header">
            <span>Оригинал</span>
            <span class="lang-tag-pill">[${escapeHtml(msg.detected_lang || 'UNKNOWN').toUpperCase()}]</span>
          </div>
          <div class="col-content">${escapeHtml(msg.original_text)}</div>
        </div>

        <div class="text-col">
          <div class="col-header">
            <span>Перевод на Русский</span>
            <span class="lang-tag-pill">[RU]</span>
          </div>
          <div class="col-content">${escapeHtml(msg.text_ru || '—')}</div>
        </div>

        <div class="text-col">
          <div class="col-header">
            <span>Перевод на Узбекский</span>
            <span class="lang-tag-pill">[UZ-LATIN]</span>
          </div>
          <div class="col-content">${escapeHtml(msg.text_uz || '—')}</div>
        </div>
      </div>

      <!-- Вердикт AI -->
      <div class="ai-verdict-box">
        <div class="verdict-header">
          <div class="verdict-title">
            <span>🤖 Вердикт Gemini AI:</span>
            <span class="confidence-badge">Уверенность: ${confidencePercent}</span>
          </div>
          <div class="violation-tags">${violationsHtml}</div>
        </div>
        <div class="verdict-reason">
          <strong>Пояснение:</strong> ${escapeHtml(msg.ai_reason || 'Сообщение чистое или ожидает анализа')}
        </div>
      </div>

      <!-- Блок жалоб -->
      ${reportsHtml}

      <!-- Кнопки действий модератора -->
      <div class="card-actions-bar">
        <div class="action-buttons-group">
          <button class="btn btn-success" onclick="moderateAction('${msg.id}', 'APPROVE', false)">
            ✅ Одобрить и опубликовать
          </button>
          <button class="btn btn-danger" onclick="moderateAction('${msg.id}', 'REJECT', false)">
            🚫 Отклонить
          </button>
          <button class="btn btn-ban" onclick="moderateAction('${msg.id}', 'REJECT', true)">
            🔨 Забанить автора
          </button>
        </div>
        <div>
          <button class="btn btn-secondary btn-sm" onclick="retranslateAction('${msg.id}')">
            🔄 Повторить AI перевод
          </button>
        </div>
      </div>
    </div>
  `;
}

// Принятие решения модератором (APPROVE / REJECT / BAN)
window.moderateAction = async function(messageId, action, banUser) {
  if (banUser && !confirm("Вы действительно хотите заблокировать автора этого сообщения?")) {
    return;
  }

  try {
    const res = await fetch(`/api/v1/admin/messages/${messageId}/moderate`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: action,
        ban_user: banUser
      })
    });

    const data = await res.json();
    if (res.ok) {
      loadStats();
      loadMessages();
    } else {
      alert("Ошибка: " + (data.detail || "Не удалось выполнить действие"));
    }
  } catch (err) {
    alert("Сетевая ошибка");
  }
};

// Принудительный повторный вызов Gemini
window.retranslateAction = async function(messageId) {
  try {
    const res = await fetch(`/api/v1/admin/messages/${messageId}/retranslate`, {
      method: "POST"
    });

    const data = await res.json();
    if (res.ok) {
      alert("AI перевод и повторный анализ успешно выполнены!");
      loadMessages();
    } else {
      alert("Ошибка AI: " + (data.detail || "Не удалось получить ответ"));
    }
  } catch (err) {
    alert("Сетевая ошибка при вызове Gemini API");
  }
};

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Переключение вкладок очередей
document.querySelectorAll(".queue-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".queue-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    currentQueue = tab.dataset.queue;

    if (currentQueue === "all") {
      allMessagesFilterBar.classList.remove("hidden");
      messagesContainer.classList.remove("hidden");
      regexContainer.classList.add("hidden");
    } else if (currentQueue === "attention") {
      allMessagesFilterBar.classList.add("hidden");
      messagesContainer.classList.remove("hidden");
      regexContainer.classList.add("hidden");
    } else if (currentQueue === "regex") {
      allMessagesFilterBar.classList.add("hidden");
      messagesContainer.classList.add("hidden");
      regexContainer.classList.remove("hidden");
    }

    loadMessages();
  });
});

// Слушатели фильтров
[filterStatus, filterType, filterHasReports].forEach(el => {
  el.addEventListener("change", () => {
    if (currentQueue === "all") {
      loadMessages();
    }
  });
});

refreshBtn.addEventListener("click", () => {
  loadStats();
  loadMessages();
});

// Автозапуск
loadStats();
loadMessages();
