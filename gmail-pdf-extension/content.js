// Добавляет в Gmail кнопку "Скачать в PDF", которая сразу генерирует
// PDF-файл из открытого письма и скачивает его — без диалога печати.

const BUTTON_ID = "gmail-pdf-download-btn";
const RENDER_HOLDER_ID = "gmail-pdf-render-holder";

function getOpenMessages() {
  // Развёрнутые (не свёрнутые) сообщения в открытой цепочке писем.
  const nodes = Array.from(document.querySelectorAll(".adn.ads"));
  return nodes.filter((el) => el.offsetParent !== null);
}

function sanitizeFileName(name) {
  return (name || "письмо")
    .replace(/[\\/:*?"<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

function setButtonState(btn, busy) {
  btn.disabled = busy;
  btn.textContent = busy ? "Формируется PDF…" : "Скачать в PDF";
}

function createButton() {
  if (document.getElementById(BUTTON_ID)) return;

  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.type = "button";
  btn.textContent = "Скачать в PDF";
  btn.title = "Сохранить открытое письмо в PDF";
  btn.addEventListener("click", () => downloadCurrentEmailAsPdf(btn));

  document.body.appendChild(btn);
}

function downloadCurrentEmailAsPdf(btn) {
  const messages = getOpenMessages();

  if (messages.length === 0) {
    alert("Откройте письмо, которое хотите сохранить в PDF.");
    return;
  }

  const subjectEl = document.querySelector("h2.hP");
  const subjectText = subjectEl ? subjectEl.textContent.trim() : "письмо";

  let holder = document.getElementById(RENDER_HOLDER_ID);
  if (holder) holder.remove();

  holder = document.createElement("div");
  holder.id = RENDER_HOLDER_ID;

  const title = document.createElement("h1");
  title.className = "gmail-pdf-subject";
  title.textContent = subjectText;
  holder.appendChild(title);

  messages.forEach((msg) => {
    holder.appendChild(msg.cloneNode(true));
  });

  document.body.appendChild(holder);

  setButtonState(btn, true);

  const options = {
    margin: 10,
    filename: `${sanitizeFileName(subjectText)}.pdf`,
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, windowWidth: holder.scrollWidth },
    jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    pagebreak: { mode: ["css", "legacy"] },
  };

  window
    .html2pdf()
    .set(options)
    .from(holder)
    .save()
    .catch((err) => {
      console.error("Не удалось сформировать PDF письма:", err);
      alert("Не удалось сформировать PDF. Подробности — в консоли (F12).");
    })
    .finally(() => {
      holder.remove();
      setButtonState(btn, false);
    });
}

const observer = new MutationObserver(() => {
  if (!document.getElementById(BUTTON_ID)) {
    createButton();
  }
});
observer.observe(document.body, { childList: true, subtree: true });

createButton();
