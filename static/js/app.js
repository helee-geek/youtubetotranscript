const form = document.getElementById("transcript-form");
const urlInput = document.getElementById("url-input");
const languageSelect = document.getElementById("language-select");
const translateInput = document.getElementById("translate-input");
const whisperFallback = document.getElementById("whisper-fallback");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const metaSource = document.getElementById("meta-source");
const metaLanguage = document.getElementById("meta-language");
const transcriptOutput = document.getElementById("transcript-output");

const sourceLabels = {
  youtube_captions: "Source: YouTube captions",
  yt_dlp_captions: "Source: YouTube captions (yt-dlp)",
  text_translation: "Source: Text translation",
  faster_whisper: "Source: faster-whisper (slow)",
};

let languageTimer = null;
let cachedSource = null;

function showStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function showResult(data) {
  metaSource.textContent = sourceLabels[data.source] || `Source: ${data.source}`;
  metaLanguage.textContent = `Language: ${data.language || data.language_code} (${data.language_code})`;
  transcriptOutput.value = data.text;
  resultEl.classList.remove("hidden");
}

async function loadLanguages(url) {
  if (!url.trim()) return;

  try {
    const response = await fetch(`/api/languages?url=${encodeURIComponent(url.trim())}`);
    const data = await response.json();
    if (!response.ok) return;

    languageSelect.innerHTML = '<option value="">Auto (Hindi → English)</option>';
    for (const lang of data.languages) {
      const option = document.createElement("option");
      option.value = lang.code;
      option.textContent = `${lang.name} (${lang.code})${lang.is_generated ? " · auto" : ""}`;
      languageSelect.appendChild(option);
    }
  } catch {
    // Optional helper — ignore failures.
  }
}

urlInput.addEventListener("input", () => {
  cachedSource = null;
  clearTimeout(languageTimer);
  languageTimer = setTimeout(() => loadLanguages(urlInput.value), 1200);
});

languageSelect.addEventListener("change", () => {
  cachedSource = null;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideStatus();
  resultEl.classList.add("hidden");

  const url = urlInput.value.trim();
  const language = languageSelect.value || null;
  const translateTo = translateInput.value.trim() || null;
  if (!url) return;

  submitBtn.disabled = true;
  submitBtn.textContent = translateTo ? "Translating..." : "Fetching...";

  const canTranslateOnly =
    translateTo &&
    cachedSource &&
    cachedSource.url === url &&
    cachedSource.language === language;

  showStatus(
    canTranslateOnly
      ? "Translating cached transcript (fast)..."
      : translateTo
        ? "Fetching captions, then translating..."
        : "Fetching transcript..."
  );

  try {
    let data;

    if (canTranslateOnly) {
      const response = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: cachedSource.text,
          source_lang: cachedSource.language_code,
          target_lang: translateTo,
        }),
      });
      data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Translation failed");
      data.language = translateTo;
    } else {
      const response = await fetch("/api/transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          language,
          translate_to: translateTo,
          use_whisper_fallback: whisperFallback.checked,
        }),
      });
      data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Request failed");

      if (!translateTo) {
        cachedSource = {
          url,
          language,
          text: data.text,
          language_code: data.language_code,
        };
      } else if (data.source_text) {
        cachedSource = {
          url,
          language,
          text: data.source_text,
          language_code: data.source_language_code,
        };
      }
    }

    showResult(data);
    showStatus("Transcript ready!", "success");
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Get Free Transcript";
  }
});
