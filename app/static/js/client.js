// RegEx паттерны для мгновенной валидации на клиенте (Level 1)
const REGEX_PATTERNS = {
  // Email
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b/,

  // Юзернеймы мессенджеров (@...)
  usernames: /(?<!\w)@(?!system\b)(?!admin\b)(?!bot\b)[a-zA-Z0-9_]{3,32}\b/i,

  // Ссылки и домены
  links: /(?:https?:\/\/|ftp:\/\/|tg:\/\/|www\.)[^\s/$.?#].[^\s]*|\b[a-zA-Zа-яА-Я0-9-]+\.(?:com|ru|uz|org|net|info|io|me|biz|su|рф|co|app|xyz|dev|site|online|tech)\b|\b(?:t\.me|telegram\.me|bit\.ly|tinyurl\.com|wa\.me)\b|\bt\s*\.\s*m\s*e\s*\/|(?:точка\s*ком|dot\s*com|точка\s*ру|точка\s*уз)\b|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/i,
  
  // Банковские карты (16 цифр)
  cards: /\b(?:\d{4}[\s-]?){3}\d{4}\b/,
  
  // Стоп-слова (русский, узбекский, английский)
  profanity: /\b(?:х[уеёuy][йеяиюeji]|п[иеie]зд[аеыуoyia]|бл[яеyea][дьdt]|еб[аеиоёuyoea]|ёб[а-я]|пид[оаo]р[а-я]*|муд[аоae]к[а-я]*|сук[аиoy]|шлюх[аиoy]|проститутк[аиoy]|тварь|fuck|shit|bitch|cunt|asshole|bastard|dick|pussy|jalab|s[iı]k[a-z]*|qo['`]?toq|itvachcha|haromi|onangni|жалаб|сикиш|сикаман|куток|қўтоқ|итвачча|ҳароми)\b/i,
  
  // Телефонные номера
  phones: /(?:(?:\+?998|\+?7|8)[\s\-]?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b/
};

function validateTextClientRegEx(text) {
  if (!text || !text.trim()) return { isValid: true };
  const val = text.trim();

  if (REGEX_PATTERNS.email.test(val)) {
    return { isValid: false, reason: "В сообщении запрещено указывать адреса электронной почты" };
  }
  if (REGEX_PATTERNS.usernames.test(val)) {
    return { isValid: false, reason: "В сообщении запрещено указывать контакты мессенджеров (@юзернеймы)" };
  }
  if (REGEX_PATTERNS.links.test(val)) {
    return { isValid: false, reason: "В сообщении обнаружены запрещенные ссылки или упоминания сайтов" };
  }
  if (REGEX_PATTERNS.cards.test(val)) {
    return { isValid: false, reason: "В сообщении обнаружен номер банковской карты или реквизиты" };
  }
  if (REGEX_PATTERNS.phones.test(val)) {
    const digits = val.replace(/\D/g, "");
    if (digits.length >= 7) {
      return { isValid: false, reason: "В сообщении запрещено указывать телефонные номера" };
    }
  }
  if (REGEX_PATTERNS.profanity.test(val)) {
    return { isValid: false, reason: "В сообщении запрещено использовать ненормативную лексику" };
  }

  return { isValid: true };
}

// Элементы формы
const msgText = document.getElementById("msgText");
const userName = document.getElementById("userName");
const msgType = document.getElementById("msgType");
const submitBtn = document.getElementById("submitBtn");
const currentCount = document.getElementById("currentCount");
const regexWarning = document.getElementById("regexWarning");
const regexWarningText = document.getElementById("regexWarningText");
const resultBanner = document.getElementById("resultBanner");
const messageForm = document.getElementById("messageForm");
const feedList = document.getElementById("feedList");
const feedCount = document.getElementById("feedCount");

// Обработка ввода в реальном времени (Pre-check Level 1)
msgText.addEventListener("input", () => {
  const text = msgText.value;
  currentCount.textContent = text.length;

  const check = validateTextClientRegEx(text);
  if (!check.isValid) {
    msgText.classList.add("input-regex-invalid");
    regexWarning.classList.remove("hidden");
    regexWarningText.textContent = check.reason;
    submitBtn.disabled = true;
  } else {
    msgText.classList.remove("input-regex-invalid");
    regexWarning.classList.add("hidden");
    submitBtn.disabled = text.trim().length === 0;
  }
});

// Отправка сообщения
messageForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const text = msgText.value.trim();
  const author = userName.value.trim() || "Аноним";
  const type = msgType.value;

  // Локальная проверка
  const check = validateTextClientRegEx(text);
  if (!check.isValid) {
    showResultBanner("error", "⚠️ Ошибка отправки: " + check.reason);
    return;
  }

  submitBtn.disabled = true;
  const originalBtnText = submitBtn.querySelector(".btn-text").textContent;
  submitBtn.querySelector(".btn-text").textContent = "AI-проверка и перевод...";

  try {
    const res = await fetch("/api/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        original_text: text,
        user_name: author,
        type: type
      })
    });

    const data = await res.json();

    if (res.status === 201) {
      showResultBanner("success", `✅ Ваше сообщение успешно проверено AI и опубликовано! (Язык: ${data.detected_lang || 'RU'})`);
      msgText.value = "";
      currentCount.textContent = "0";
      loadFeed();
    } else if (res.status === 202) {
      showResultBanner("pending", `⏳ Сообщение отправлено на ручную модерацию. Статус: PENDING_MODERATION.`);
      msgText.value = "";
      currentCount.textContent = "0";
    } else if (res.status === 422) {
      const detail = data.detail || {};
      const reason = detail.ai_reason || detail.message || "Сообщение отклонено фильтрами безопасности.";
      const violations = detail.ai_violations ? ` [${detail.ai_violations.join(", ")}]` : "";
      showResultBanner("error", `⛔ Отклонено AI-модератором: ${reason}${violations}`);
    } else if (res.status === 403) {
      showResultBanner("error", `🚫 Доступ заблокирован: ${data.detail}`);
    } else if (res.status === 429) {
      showResultBanner("error", `⏱️ ${data.detail || 'Слишком много запросов. Подождите минуту.'}`);
    } else {
      showResultBanner("error", `Ошибка: ${data.detail || 'Не удалось отправить сообщение'}`);
    }
  } catch (err) {
    showResultBanner("error", "Сетевая ошибка при отправке запроса.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector(".btn-text").textContent = originalBtnText;
  }
});

function showResultBanner(type, message) {
  resultBanner.className = `result-banner ${type}`;
  resultBanner.textContent = message;
  resultBanner.classList.remove("hidden");
  setTimeout(() => {
    // оставляем видимым или скрываем плавно
  }, 7000);
}

// Загрузка публичной ленты
let currentFilter = "";

async function loadFeed() {
  try {
    const url = currentFilter ? `/api/v1/messages?type=${currentFilter}` : "/api/v1/messages";
    const res = await fetch(url);
    if (!res.ok) throw new Error("Ошибка загрузки");
    const messages = await res.json();

    feedCount.textContent = messages.length;

    if (messages.length === 0) {
      feedList.innerHTML = `<div class="loading-state">Пока нет опубликованных сообщений. Будьте первым!</div>`;
      return;
    }

    feedList.innerHTML = messages.map(msg => renderMessageCard(msg)).join("");
  } catch (err) {
    feedList.innerHTML = `<div class="loading-state">Ошибка загрузки сообщений.</div>`;
  }
}

function renderMessageCard(msg) {
  const typeMap = {
    REVIEW: { label: "⭐ Отзыв", class: "badge-review" },
    COMMENT: { label: "💬 Комментарий", class: "badge-comment" },
    TICKET: { label: "📩 Заявка", class: "badge-ticket" }
  };
  const typeInfo = typeMap[msg.type] || { label: msg.type, class: "" };
  const initial = (msg.user_name || "А")[0].toUpperCase();
  const dateStr = new Date(msg.created_at).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });

  return `
    <div class="message-card" id="msg-${msg.id}">
      <div class="msg-top">
        <div class="author-info">
          <div class="avatar">${initial}</div>
          <div>
            <div class="author-name">${escapeHtml(msg.user_name)}</div>
            <div class="msg-date">${dateStr}</div>
          </div>
        </div>
        <span class="msg-badge ${typeInfo.class}">${typeInfo.label}</span>
      </div>

      <div class="msg-content">${escapeHtml(msg.original_text)}</div>

      <div class="msg-footer">
        <span class="lang-tag">Определен: [${escapeHtml(msg.detected_lang || 'RU').toUpperCase()}]</span>
        <button class="btn-report" onclick="openReportModal('${msg.id}')">
          🚩 Пожаловаться
        </button>
      </div>
    </div>
  `;
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Фильтры ленты
document.querySelectorAll(".pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    currentFilter = pill.dataset.filter;
    loadFeed();
  });
});

// Модальное окно жалоб (Этап 3)
const reportModal = document.getElementById("reportModal");
const reportForm = document.getElementById("reportForm");
const reportMessageId = document.getElementById("reportMessageId");
const reportComment = document.getElementById("reportComment");

window.openReportModal = function(id) {
  reportMessageId.value = id;
  reportComment.value = "";
  reportModal.classList.remove("hidden");
};

document.getElementById("closeReportModal").addEventListener("click", () => {
  reportModal.classList.add("hidden");
});

document.getElementById("cancelReportBtn").addEventListener("click", () => {
  reportModal.classList.add("hidden");
});

reportForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const messageId = reportMessageId.value;
  const reason = document.querySelector('input[name="reportReason"]:checked').value;
  const comment = reportComment.value.trim();

  try {
    const res = await fetch(`/api/v1/messages/${messageId}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: reason,
        comment: comment || null
      })
    });

    const data = await res.json();
    if (res.ok) {
      alert("✅ Ваша жалоба принята. Если сообщение нарушает правила, модераторы примут меры.");
      reportModal.classList.add("hidden");
      // Если сообщение ушло в карантин, перезагружаем ленту
      if (data.current_status === "QUARANTINED") {
        loadFeed();
      }
    } else {
      alert("⚠️ " + (data.detail || "Не удалось отправить жалобу"));
    }
  } catch (err) {
    alert("Сетевая ошибка при отправке жалобы.");
  }
});

// Старт
loadFeed();
