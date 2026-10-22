import * as pdfjs from './vendor/pdfjs/pdf.mjs';

pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.mjs', import.meta.url).href;

function toViewportRect(viewport, rect) {
  // This vendored PDF.js has convertToViewportPoint only.
  const [x1, y1] = viewport.convertToViewportPoint(rect[0], rect[1]);
  const [x2, y2] = viewport.convertToViewportPoint(rect[2], rect[3]);
  return [x1, y1, x2, y2];
}

function fontFamily(page, item) {
  try {
    if (item?.fontName && page.commonObjs.has(item.fontName)) {
      return page.commonObjs.get(item.fontName).loadedName || "serif";
    }
  } catch {
    /* font dict not ready */
  }
  return "serif";
}

// Like the original Myoverl editor, hit areas come from TeX annotations,
// never guessed HTML line boxes. The displayed glyphs are the PDF itself.
export async function makePdfView(base64, fields, scale, onEdit) {
  const bytes = Uint8Array.from(atob(base64), char => char.charCodeAt(0));
  const task = pdfjs.getDocument({ data: bytes, isEvalSupported: false });
  try {
    const pdf = await task.promise;
    const fragment = document.createDocumentFragment();
    const positions = new Map();
    for (let number = 1; number <= pdf.numPages; number++) {
      const page = await pdf.getPage(number);
      const viewport = page.getViewport({ scale });
      const paper = document.createElement('section');
      paper.className = 'pdf-page';
      paper.setAttribute('aria-label', `Resume page ${number}`);
      paper.style.width = `${viewport.width}px`;
      paper.style.height = `${viewport.height}px`;
      const canvas = document.createElement('canvas');
      canvas.setAttribute('aria-hidden', 'true');
      const density = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.ceil(viewport.width * density);
      canvas.height = Math.ceil(viewport.height * density);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      await page.render({ canvasContext: canvas.getContext('2d'), viewport,
        transform: [density, 0, 0, density, 0, 0] }).promise;
      paper.append(canvas);
      const text = await page.getTextContent();
      for (const annotation of await page.getAnnotations()) {
        const match = /^https:\/\/myoverl\.invalid\/edit\/(f\d+)$/.exec(annotation.unsafeUrl || annotation.url || '');
        if (!match || !fields[match[1]]) continue;
        const key = match[1], field = fields[key];
        const rect = toViewportRect(viewport, annotation.rect);
        const x = Math.min(rect[0], rect[2]), y = Math.min(rect[1], rect[3]);
        const w = Math.abs(rect[2] - rect[0]), h = Math.abs(rect[3] - rect[1]);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'text-hit';
        button.dataset.field = key;
        button.setAttribute('aria-label', `Edit ${field.label}: ${field.raw}`);
        Object.assign(button.style, { left: `${x}px`, top: `${y}px`,
          width: `${Math.max(w, 4 * scale)}px`, height: `${Math.max(h, 7 * scale)}px` });
        button.addEventListener('click', () => onEdit(key));
        paper.append(button);
        const existing = positions.get(key);
        if (existing) {
          existing.rects.push({ x, y, w, h, paper });
          if (existing.paper === paper) {
            existing.width = Math.max(existing.width, x + w - existing.x);
            existing.height = Math.max(existing.height, y + h - existing.y);
          }
          continue;
        }
        const item = text.items.find(item => {
          if (!item.transform || !item.str.trim()) return false;
          const [px, py] = viewport.convertToViewportPoint(item.transform[4], item.transform[5]);
          return px >= x - 4 && px <= x + w + 4 && py >= y - 2 && py <= y + h + 4;
        });
        const family = fontFamily(page, item);
        positions.set(key, { x, y, width: w, height: h, paper,
          pageWidth: viewport.width, family, fontSize: (item?.height || 10) * scale,
          rects: [{ x, y, w, h, paper }] });
      }
      fragment.append(paper);
    }
    return { fragment, positions, pages: pdf.numPages, width: 612 * scale,
      destroy: () => task.destroy() };
  } catch (error) {
    await task.destroy();
    throw error;
  }
}
