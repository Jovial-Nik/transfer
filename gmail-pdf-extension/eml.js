// Простой парсер .eml (RFC 822 / MIME) для браузера. Извлекает заголовки
// (Тема, От, Кому, Копия, Дата), текст письма (text/plain, либо текст,
// извлечённый из text/html) и список вложений — без внешних зависимостей.

(function (global) {
  function arrayBufferToLatin1String(buf) {
    const bytes = new Uint8Array(buf);
    let result = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      result += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return result;
  }

  function latin1StringToBytes(str) {
    const bytes = new Uint8Array(str.length);
    for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i) & 0xff;
    return bytes;
  }

  function normalizeCharset(charset) {
    if (!charset) return "utf-8";
    return charset.trim().toLowerCase().replace(/"/g, "");
  }

  function decodeBytesWithCharset(bytes, charset) {
    try {
      return new TextDecoder(normalizeCharset(charset)).decode(bytes);
    } catch (e) {
      try {
        return new TextDecoder("utf-8").decode(bytes);
      } catch (e2) {
        return latin1StringToBytesToString(bytes);
      }
    }
  }

  function latin1StringToBytesToString(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return s;
  }

  function decodeQuotedPrintable(str) {
    str = str.replace(/=\r\n/g, "").replace(/=\n/g, "");
    const bytes = [];
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      if (ch === "=" && i + 2 < str.length) {
        const hex = str.substr(i + 1, 2);
        if (/^[0-9A-Fa-f]{2}$/.test(hex)) {
          bytes.push(parseInt(hex, 16));
          i += 2;
          continue;
        }
      }
      bytes.push(ch.charCodeAt(0) & 0xff);
    }
    return new Uint8Array(bytes);
  }

  function decodeBase64ToBytes(str) {
    const clean = str.replace(/[^A-Za-z0-9+/=]/g, "");
    if (!clean) return new Uint8Array(0);
    let bin;
    try {
      bin = atob(clean);
    } catch (e) {
      return new Uint8Array(0);
    }
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  function decodeHeaderValue(value) {
    if (!value) return "";
    let result = value.replace(
      /=\?([^?\s]+)\?([BbQq])\?([^?]*)\?=/g,
      (m, charset, enc, data) => {
        try {
          let bytes;
          if (enc.toUpperCase() === "B") {
            bytes = decodeBase64ToBytes(data);
          } else {
            bytes = decodeQuotedPrintable(data.replace(/_/g, " "));
          }
          return decodeBytesWithCharset(bytes, charset);
        } catch (e) {
          return m;
        }
      }
    );
    // Убираем пробел между соседними закодированными словами: "?= =?" -> ""
    result = result.replace(/\?=\s+=\?/g, "?==?");
    return result;
  }

  function splitHeadersAndBody(raw) {
    const idxCrlf = raw.indexOf("\r\n\r\n");
    const idxLf = raw.indexOf("\n\n");
    let pos = -1;
    let sepLen = 0;
    if (idxCrlf !== -1 && (idxLf === -1 || idxCrlf <= idxLf)) {
      pos = idxCrlf;
      sepLen = 4;
    } else if (idxLf !== -1) {
      pos = idxLf;
      sepLen = 2;
    }
    if (pos === -1) return { headerText: raw, body: "" };
    return { headerText: raw.slice(0, pos), body: raw.slice(pos + sepLen) };
  }

  function parseHeaders(headerText) {
    const lines = headerText.split(/\r\n|\n/);
    const headers = [];
    let current = null;
    for (const line of lines) {
      if (/^[ \t]/.test(line) && current) {
        current.value += " " + line.trim();
      } else {
        const m = line.match(/^([^:\s][^:]*):\s*(.*)$/);
        if (m) {
          current = { name: m[1].trim().toLowerCase(), value: m[2] };
          headers.push(current);
        } else {
          current = null;
        }
      }
    }
    return headers;
  }

  function getHeader(headers, name) {
    const h = headers.find((x) => x.name === name.toLowerCase());
    return h ? h.value : "";
  }

  function parseParamsString(value) {
    const parts = value.split(";");
    const type = (parts[0] || "").trim().toLowerCase();
    const params = {};
    for (let i = 1; i < parts.length; i++) {
      const p = parts[i];
      const eq = p.indexOf("=");
      if (eq === -1) continue;
      const key = p.slice(0, eq).trim().toLowerCase().replace(/\*$/, "");
      let val = p.slice(eq + 1).trim();
      val = val.replace(/^"(.*)"$/, "$1");
      if (!params[key]) params[key] = val;
    }
    return { type, params };
  }

  function splitByBoundary(body, boundary) {
    if (!boundary) return [body];
    const delim = "--" + boundary;
    const pieces = body.split(delim);
    const result = [];
    for (let i = 1; i < pieces.length; i++) {
      let piece = pieces[i];
      if (piece.indexOf("--") === 0) break;
      piece = piece.replace(/^\r\n/, "").replace(/^\n/, "");
      piece = piece.replace(/\r\n$/, "").replace(/\n$/, "");
      result.push(piece);
    }
    return result;
  }

  function parsePart(rawPart) {
    const { headerText, body } = splitHeadersAndBody(rawPart);
    const headers = parseHeaders(headerText);
    const ctValue = getHeader(headers, "content-type") || "text/plain; charset=us-ascii";
    const { type, params } = parseParamsString(ctValue);
    const cte = (getHeader(headers, "content-transfer-encoding") || "7bit")
      .toLowerCase()
      .trim();
    const dispositionRaw = getHeader(headers, "content-disposition");
    const disposition = dispositionRaw
      ? parseParamsString(dispositionRaw)
      : { type: "", params: {} };

    if (type.indexOf("multipart/") === 0) {
      const boundary = params.boundary;
      const subParts = splitByBoundary(body, boundary);
      const children = subParts.map(parsePart);
      return { type, children };
    }

    let bytes;
    if (cte === "base64") bytes = decodeBase64ToBytes(body);
    else if (cte === "quoted-printable") bytes = decodeQuotedPrintable(body);
    else bytes = latin1StringToBytes(body);

    const filename = decodeHeaderValue(
      disposition.params.filename || params.name || ""
    );
    const isAttachment =
      disposition.type === "attachment" ||
      (!!filename && type.indexOf("text/") !== 0 && type !== "");

    if (type.indexOf("text/") === 0 && !isAttachment) {
      const text = decodeBytesWithCharset(bytes, params.charset);
      return { type, text };
    }

    return {
      type,
      isAttachment: true,
      filename: filename || "(без имени)",
      size: bytes.length,
    };
  }

  function collectParts(node, acc) {
    if (node.children) {
      node.children.forEach((c) => collectParts(c, acc));
    } else if (node.isAttachment) {
      acc.attachments.push(node);
    } else if (node.type === "text/plain" && !acc.plain) {
      acc.plain = node.text;
    } else if (node.type === "text/html" && !acc.html) {
      acc.html = node.text;
    }
    return acc;
  }

  function htmlToText(html) {
    const div = document.createElement("div");
    div.innerHTML = html
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n\n")
      .replace(/<\/div>/gi, "\n")
      .replace(/<\/tr>/gi, "\n")
      .replace(/<\/li>/gi, "\n")
      .replace(/<li[^>]*>/gi, "• ");
    const text = div.textContent || "";
    return text.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  function parseEml(arrayBuffer) {
    const raw = arrayBufferToLatin1String(arrayBuffer);
    const { headerText } = splitHeadersAndBody(raw);
    const headers = parseHeaders(headerText);
    const tree = parsePart(raw);

    const acc = collectParts(tree, { attachments: [] });
    let bodyText = acc.plain;
    if (!bodyText && acc.html) bodyText = htmlToText(acc.html);
    if (!bodyText) bodyText = "";

    return {
      subject: decodeHeaderValue(getHeader(headers, "subject")) || "(без темы)",
      from: decodeHeaderValue(getHeader(headers, "from")),
      to: decodeHeaderValue(getHeader(headers, "to")),
      cc: decodeHeaderValue(getHeader(headers, "cc")),
      date: getHeader(headers, "date"),
      bodyText,
      attachments: acc.attachments,
    };
  }

  global.parseEml = parseEml;
})(window);
