// Добавляет в Gmail кнопку "Скачать в PDF", которая печатает открытое
// письмо через стандартный диалог печати Chrome (в нём можно выбрать
// принтер "Сохранить как PDF"). Прямое программное сохранение в PDF
// недоступно расширениям без диалога печати браузера.

const BUTTON_ID = "gmail-pdf-download-btn";
const PRINT_HOLDER_ID = "gmail-pdf-print-holder";

function getOpenMessages() {
  // Развёрнутые (не свёрнутые) сообщения в открытой цепочке писем.
  const nodes = Array.from(document.querySelectorAll(".adn.ads"));
  return nodes.filter((el) => el.offsetParent !== null);
}

function createButton() {
  if (document.getElementById(BUTTON_ID)) return;

  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.type = "button";
  btn.textContent = "Скачать в PDF";
  btn.title = "Сохранить открытое письмо в PDF";
  btn.addEventListener("click", downloadCurrentEmailAsPdf);

  document.body.appendChild(btn);
}

function downloadCurrentEmailAsPdf() {
  const messages = getOpenMessages();

  if (messages.length === 0) {
    alert("Откройте письмо, которое хотите сохранить в PDF.");
    return;
  }

  let holder = document.getElementById(PRINT_HOLDER_ID);
  if (holder) holder.remove();

  holder = document.createElement("div");
  holder.id = PRINT_HOLDER_ID;

  const subjectEl = document.querySelector("h2.hP");
  if (subjectEl) {
    const title = document.createElement("h1");
    title.className = "gmail-pdf-subject";
    title.textContent = subjectEl.textContent;
    holder.appendChild(title);
  }

  messages.forEach((msg) => {
    holder.appendChild(msg.cloneNode(true));
  });

  document.body.appendChild(holder);

  // Даём браузеру отрисовать holder перед вызовом печати.
  window.requestAnimationFrame(() => {
    window.print();
  });
}

window.addEventListener("afterprint", () => {
  const holder = document.getElementById(PRINT_HOLDER_ID);
  if (holder) holder.remove();
});

const observer = new MutationObserver(() => {
  if (!document.getElementById(BUTTON_ID)) {
    createButton();
  }
});
observer.observe(document.body, { childList: true, subtree: true });

createButton();
