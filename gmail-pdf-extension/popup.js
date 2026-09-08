const fileInput = document.getElementById("file");
const convertBtn = document.getElementById("convert");
const statusEl = document.getElementById("status");

let selectedFile = null;

fileInput.addEventListener("change", () => {
  selectedFile = fileInput.files[0] || null;
  convertBtn.disabled = !selectedFile;
  setStatus("");
});

convertBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  setStatus("Читаю файл…");
  convertBtn.disabled = true;

  try {
    const buffer = await selectedFile.arrayBuffer();
    const email = parseEml(buffer);
    setStatus("Формирую PDF…");
    const filename = buildPdf(email);
    setStatus(`Готово: ${filename}`);
  } catch (err) {
    console.error(err);
    setStatus("Не удалось сконвертировать файл. Смотрите консоль (F12).", true);
  } finally {
    convertBtn.disabled = false;
  }
});

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", !!isError);
}

function sanitizeFileName(name) {
  return (name || "письмо")
    .replace(/[\\/:*?"<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

function buildPdf(email) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "pt", format: "a4" });

  doc.addFileToVFS("Roboto-Cyrillic.ttf", window.ROBOTO_CYRILLIC_TTF_BASE64);
  doc.addFont("Roboto-Cyrillic.ttf", "Roboto", "normal");
  doc.setFont("Roboto");

  const margin = 42;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  function addText(text, size, lineHeight, extraGapAfter) {
    if (!text) return;
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(String(text), maxWidth);
    lines.forEach((line) => {
      if (y > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }
      doc.text(line, margin, y);
      y += lineHeight;
    });
    if (extraGapAfter) y += extraGapAfter;
  }

  addText(email.subject, 16, 20, 8);
  addText(`От: ${email.from}`, 10, 14, 0);
  addText(`Кому: ${email.to}`, 10, 14, 0);
  if (email.cc) addText(`Копия: ${email.cc}`, 10, 14, 0);
  if (email.date) addText(`Дата: ${email.date}`, 10, 14, 0);
  if (email.attachments.length) {
    const names = email.attachments.map((a) => a.filename).join(", ");
    addText(`Вложения: ${names}`, 10, 14, 0);
  }

  y += 6;
  if (y > pageHeight - margin) {
    doc.addPage();
    y = margin;
  }
  doc.setDrawColor(200);
  doc.line(margin, y, pageWidth - margin, y);
  y += 18;

  addText(email.bodyText || "(тело письма пустое)", 11, 15, 0);

  const filename = `${sanitizeFileName(email.subject)}.pdf`;
  doc.save(filename);
  return filename;
}
