import { makePdfView } from "./pdf-view.mjs?v=3";

const personEl = document.getElementById("person");
const resumeEl = document.getElementById("resume");
const paperEl = document.getElementById("paper");
const statusEl = document.getElementById("status");

let people = [];
let resumes = [];
let current = null;
let pollTimer = null;

function esc(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toPaper(text) {
  return String(text ?? "")
    .replaceAll("---", "\u2014")
    .replaceAll("--", "\u2013");
}

function fromPaper(text) {
  return String(text ?? "")
    .replaceAll("\u2014", "---")
    .replaceAll("\u2013", "--");
}

let pdfView = null;
let preview = null;
let renderGeneration = 0;
let activeEdit = null;
let savingEdit = null;
let resizeTimer = null;
const doneEl = document.getElementById("finish-editing");
const zoomEl = document.getElementById("zoom");
const noticeEl = document.getElementById("preview-notice");

function previewScale() {
  if (zoomEl.value !== "fit") return Number(zoomEl.value);
  const stage = document.querySelector(".stage");
  const style = getComputedStyle(stage);
  return Math.min(4 / 3, (stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)) / 612);
}

async function renderPaper() {
  const generation = ++renderGeneration;
  if (!current) return;
  const snapshot = current;
  setStatus("Building preview...");
  paperEl.inert = true;
  noticeEl.hidden = true;
  document.getElementById("download").disabled = true;
  try {
    let rendered = preview;
    if (!rendered || rendered.resume_id !== snapshot.resume_id || rendered.revision !== snapshot.revision) {
      rendered = await api(`/api/resumes/${snapshot.resume_id}/preview?revision=${snapshot.revision}`);
      if (generation !== renderGeneration) return;
    }
    const next = await makePdfView(rendered.pdf, rendered.fields, previewScale(), beginEditing);
    if (generation !== renderGeneration) { await next.destroy(); return; }
    clearEditor();
    const previous = pdfView;
    paperEl.replaceChildren(next.fragment);
    pdfView = next;
    preview = rendered;
    paperEl.inert = false;
    if (previous) await previous.destroy();
    const overflow = next.pages > 1;
    const pageCountEl = document.getElementById("page-count");
    if (pageCountEl) {
      pageCountEl.textContent = `${next.pages} ${next.pages === 1 ? "page" : "pages"} · Click any text to edit`;
    }
    if (overflow) {
      noticeEl.textContent = "This resume exceeds one page. Shorten the content before downloading.";
      noticeEl.hidden = false;
    }
    document.getElementById("download").disabled = overflow;
    setStatus(overflow ? "Page overflow" : "PDF ready");
  } catch (err) {
    if (generation !== renderGeneration) return;
    noticeEl.textContent = `Preview could not update: ${err.message}`;
    noticeEl.hidden = false;
    setStatus("Preview unavailable");
    // Keep the last valid PDF visible; never substitute a different layout.
  }
}

function clearEditor() {
  if (!activeEdit) return;
  activeEdit.element.remove();
  activeEdit.masks.forEach(mask => mask.remove());
  activeEdit = null;
  doneEl.hidden = true;
}

function findEntry(entryId) {
  for (const section of current?.sections || []) {
    for (const entry of section.entries || []) {
      if (entry.entry_id === entryId) return entry;
    }
  }
  return null;
}

function findSlot(slotId) {
  return current?.heading.slots.find((slot) => slot.slot_id === slotId) || null;
}

function syncLinkFields() {
  const on = document.getElementById("link-show").checked;
  document.getElementById("link-url").disabled = !on;
  document.getElementById("link-text").disabled = !on;
}

function linkPlaceholders(kind) {
  if (kind === "phone") return { url: "tel:+1...", text: "(555) 555-5555" };
  if (kind === "email") return { url: "mailto:you@example.com", text: "you@example.com" };
  if (kind === "project") return { url: "https://", text: "Link" };
  return { url: "https://", text: "Portfolio" };
}

async function openLinkEditor(field) {
  const showEl = document.getElementById("link-show");
  const urlEl = document.getElementById("link-url");
  const textEl = document.getElementById("link-text");
  const titleEl = document.getElementById("link-title");
  const helpEl = document.getElementById("link-help");
  const slot = field.kind === "slot-text" ? findSlot(field.id) : null;
  const entry = field.kind === "link" ? findEntry(field.id) : null;
  const kind = slot?.kind || "project";
  const hints = linkPlaceholders(kind);
  titleEl.textContent = field.kind === "slot-text" ? "Contact link" : "Project link";
  helpEl.textContent = "Paste the address. Uncheck to hide it on the resume.";
  showEl.checked = field.kind === "slot-text" ? true : Boolean(entry?.link_url);
  urlEl.value = field.kind === "slot-text" ? (slot?.href || "") : (entry?.link_url || "");
  textEl.value = field.kind === "slot-text" ? (slot?.text || "") : (entry?.link_text || "Link");
  urlEl.placeholder = hints.url;
  textEl.placeholder = hints.text;
  syncLinkFields();
  const dlg = openDialog("dlg-link");
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok" || !current) return;
    const show = showEl.checked;
    const url = urlEl.value.trim();
    const text = textEl.value.trim();
    if (show && !url) {
      setStatus("Need an address to show the link");
      noticeEl.textContent = "Paste a link address, or uncheck Show on resume.";
      noticeEl.hidden = false;
      return;
    }
    if (field.kind === "slot-text") {
      const slots = [];
      for (const item of current.heading.slots) {
        if (item.slot_id === field.id) {
          if (show) slots.push({ kind: item.kind, href: url, text });
        } else {
          slots.push({ kind: item.kind, href: item.href, text: item.text });
        }
      }
      await savePatch({ heading: { slots } });
      return;
    }
    await savePatch({
      entry_fields: [{
        entry_id: field.id,
        fields: {},
        link_url: show ? url : "",
        link_text: text || "Link",
      }],
    });
  };
}

async function beginEditing(key) {
  if (paperEl.inert || preview?.resume_id !== current?.resume_id || preview?.revision !== current?.revision) return;
  if (activeEdit?.key === key) { activeEdit.element.focus(); return; }
  if (!await finishEditing()) return;
  const box = pdfView?.positions.get(key), field = preview?.fields[key];
  if (!box || !field) return;
  if (field.kind === "link" || field.kind === "slot-text") {
    await openLinkEditor(field);
    return;
  }
  const element = document.createElement("div");
  element.className = "text-editor";
  element.contentEditable = "plaintext-only";
  element.setAttribute("role", "textbox");
  element.setAttribute("aria-label", `Edit ${field.label}`);
  element.setAttribute("aria-multiline", "true");
  element.spellcheck = false;
  element.textContent = field.kind === "link" ? field.raw : toPaper(field.raw);
  const fontSize = Math.max(16, box.fontSize), ratio = box.fontSize / fontSize;
  const paragraph = ["bullet", "coursework", "honors", "skill-items", "techs"].includes(field.kind);
  const width = paragraph ? box.pageWidth - box.x - 18 * previewScale() : Math.max(box.width, 48 * previewScale());
  Object.assign(element.style, { left: `${box.x}px`, top: `${box.y}px`,
    width: `${width / ratio}px`, minHeight: `${box.height / ratio}px`,
    fontFamily: `"${box.family}", serif`, fontSize: `${fontSize}px`, transform: `scale(${ratio})` });
  const masks = box.rects.map(rect => {
    const mask = document.createElement("div");
    mask.className = "edit-mask";
    Object.assign(mask.style, { left: `${rect.x - 1}px`, top: `${rect.y - 1}px`, width: `${rect.w + 2}px`, height: `${rect.h + 2}px` });
    rect.paper.append(mask);
    return mask;
  });
  box.paper.append(element);
  activeEdit = { key, field, element, masks };
  doneEl.hidden = false;
  element.focus({ preventScroll: true });
  const range = document.createRange();
  range.selectNodeContents(element);
  if (field.kind !== "link") range.collapse(false);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  element.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); clearEditor(); }
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); finishEditing(); }
  });
}

function finishEditing() {
  if (savingEdit) return savingEdit;
  if (!activeEdit) return Promise.resolve(true);
  const edit = activeEdit;
  const raw = edit.element.innerText.trim();
  const text = edit.field.kind === "link" ? raw : fromPaper(raw);
  if (text === edit.field.raw) { clearEditor(); return Promise.resolve(true); }
  edit.element.contentEditable = "false";
  savingEdit = commitField(edit.field, text).then(saved => {
    if (saved) clearEditor();
    else if (activeEdit === edit) { edit.element.contentEditable = "plaintext-only"; edit.element.focus(); }
    return saved;
  }).finally(() => { savingEdit = null; });
  return savingEdit;
}

doneEl.addEventListener("click", finishEditing);
zoomEl.addEventListener("change", async () => { if (await finishEditing()) await renderPaper(); });
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(async () => {
    if (zoomEl.value === "fit" && !activeEdit) await renderPaper();
  }, 150);
});

const urlParams = new URLSearchParams(window.location.search);
let authToken = urlParams.get("token") || localStorage.getItem("underleaf_token") || "";
if (urlParams.get("token")) {
  localStorage.setItem("underleaf_token", urlParams.get("token"));
}

async function api(path, opts) {
  const headers = { "Content-Type": "application/json", ...(opts?.headers || {}) };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  const res = await fetch(path, {
    headers,
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.error || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/pdf")) return res.blob();
  if (res.status === 204) return null;
  return res.json();
}

function setStatus(text) {
  statusEl.textContent = text;
}

async function loadPeople(preferred) {
  people = await api("/api/people");
  personEl.innerHTML = people
    .map((p) => `<option value="${esc(p.name)}">${esc(p.name)}</option>`)
    .join("");
  if (preferred) personEl.value = preferred;
  if (!personEl.value && people[0]) personEl.value = people[0].name;
}

async function loadResumes(keepId) {
  const person = personEl.value;
  resumes = await api(`/api/resumes?person=${encodeURIComponent(person)}`);
  resumeEl.innerHTML = resumes
    .map((r) => {
      const label = r.role === "source" ? `${r.name} (source)` : r.name;
      return `<option value="${esc(r.resume_id)}">${esc(label)}</option>`;
    })
    .join("");
  const params = new URLSearchParams(location.search);
  const wanted = keepId || params.get("resume") || resumeEl.value;
  if (wanted && [...resumeEl.options].some((o) => o.value === wanted)) {
    resumeEl.value = wanted;
  }
}

async function loadResume(id) {
  current = await api(`/api/resumes/${id}`);
  history.replaceState(null, "", `/?resume=${id}`);
  await renderPaper();
}

async function refreshLists(keepId) {
  await loadPeople(personEl.value);
  await loadResumes(keepId);
  if (resumeEl.value) await loadResume(resumeEl.value);
}

async function savePatch(patch) {
  if (!current) return false;
  setStatus("Saving...");
  try {
    current = await api(`/api/resumes/${current.resume_id}/update`, {
      method: "POST",
      body: JSON.stringify({ base_revision: current.revision, ...patch }),
    });
    await renderPaper();
    return true;
  } catch (err) {
    setStatus("Could not save");
    noticeEl.textContent = err.message;
    noticeEl.hidden = false;
    return false;
  }
}

function splitList(text) {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

async function commitField(field, text) {
  const { kind, id, extra } = field;
  if (kind === "heading-name") return savePatch({ heading: { name: text } });
  if (kind === "bullet") return savePatch({ bullets: [{ bullet_id: id, text }] });
  if (kind === "title") return savePatch({ entry_fields: [{ entry_id: id, fields: {}, title: text }] });
  if (kind === "field") return savePatch({ entry_fields: [{ entry_id: id, fields: { [extra]: text } }] });
  if (kind === "link") {
    return savePatch({ entry_fields: [{ entry_id: id, fields: {}, link_url: text || null }] });
  }
  if (kind === "honors") return savePatch({ entry_fields: [{ entry_id: id, honors: splitList(text) }] });
  if (kind === "coursework") return savePatch({ coursework: [{ entry_id: id, items: splitList(text) }] });
  if (kind === "techs") return savePatch({ entry_fields: [{ entry_id: id, technologies: splitList(text) }] });
  if (kind === "skill-title") return savePatch({ skill_rows: [{ row_id: id, title: text }] });
  if (kind === "skill-items") return savePatch({ skill_rows: [{ row_id: id, items: splitList(text) }] });
  if (kind === "slot-text") {
    const slots = current.heading.slots.map((s) =>
      s.slot_id === id ? { kind: s.kind, href: s.href, text } : { kind: s.kind, href: s.href, text: s.text }
    );
    return savePatch({ heading: { slots } });
  }
}

personEl.addEventListener("change", async () => {
  if (await finishEditing()) await refreshLists();
});
resumeEl.addEventListener("change", async () => {
  if (await finishEditing()) await loadResume(resumeEl.value);
});

function openDialog(id) {
  const dlg = document.getElementById(id);
  dlg.showModal();
  return dlg;
}

document.getElementById("copy").onclick = async () => {
  if (!await finishEditing()) return;
  const dlg = openDialog("dlg-copy");
  document.getElementById("copy-name").value = "";
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok" || !current) return;
    const name = document.getElementById("copy-name").value.trim() || "Untitled copy";
    const copied = await api(`/api/resumes/${current.resume_id}/copy`, {
      method: "POST",
      body: JSON.stringify({ copy_name: name }),
    });
    await refreshLists(copied.resume_id);
  };
};

document.getElementById("rename").onclick = async () => {
  if (!await finishEditing()) return;
  const dlg = openDialog("dlg-rename");
  document.getElementById("resume-name").value = current?.name || "";
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok" || !current) return;
    const updated = await api(`/api/resumes/${current.resume_id}/rename`, {
      method: "POST",
      body: JSON.stringify({ name: document.getElementById("resume-name").value }),
    });
    await refreshLists(updated.resume_id);
  };
};

document.getElementById("add-person").onclick = async () => {
  if (!await finishEditing()) return;
  const dlg = openDialog("dlg-person");
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok") return;
    const created = await api("/api/people", {
      method: "POST",
      body: JSON.stringify({
        person_name: document.getElementById("person-name").value,
        heading_name: document.getElementById("heading-name").value,
      }),
    });
    await loadPeople(created.name);
    await refreshLists(created.resume_id);
  };
};

document.getElementById("add-project").onclick = async () => {
  if (!await finishEditing()) return;
  const dlg = openDialog("dlg-project");
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok" || !current) return;
    const updated = await api(`/api/resumes/${current.resume_id}/projects`, {
      method: "POST",
      body: JSON.stringify({
        title: document.getElementById("proj-title").value,
        technologies: splitList(document.getElementById("proj-tech").value),
        link_url: document.getElementById("proj-link").value,
        link_text: document.getElementById("proj-link-text").value,
        bullets: document
          .getElementById("proj-bullets")
          .value.split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      }),
    });
    current = updated;
    await renderPaper();
  };
};

document.getElementById("contacts").onclick = async () => {
  if (!await finishEditing()) return;
  const root = document.getElementById("contact-fields");
  root.innerHTML = (current?.heading.slots || [])
    .map(
      (s, i) => `<label>Kind
        <input data-i="${i}" data-f="kind" value="${esc(s.kind)}">
      </label><label>Href
        <input data-i="${i}" data-f="href" value="${esc(s.href)}">
      </label><label>Text
        <input data-i="${i}" data-f="text" value="${esc(s.text)}">
      </label>`
    )
    .join("");
  const dlg = openDialog("dlg-contacts");
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok" || !current) return;
    const inputs = [...root.querySelectorAll("input")];
    const byIndex = {};
    for (const input of inputs) {
      const i = input.dataset.i;
      byIndex[i] ??= {};
      byIndex[i][input.dataset.f] = input.value;
    }
    const slots = Object.keys(byIndex)
      .sort()
      .map((i) => byIndex[i]);
    await savePatch({ heading: { slots } });
  };
};

document.getElementById("link-show").addEventListener("change", syncLinkFields);

document.getElementById("add-slot").onclick = (event) => {
  event.preventDefault();
  const root = document.getElementById("contact-fields");
  const i = root.querySelectorAll("[data-f=kind]").length;
  root.insertAdjacentHTML(
    "beforeend",
    `<label>Kind <input data-i="${i}" data-f="kind" value="other"></label>
     <label>Href <input data-i="${i}" data-f="href" value="https://"></label>
     <label>Text <input data-i="${i}" data-f="text" value=""></label>`
  );
};

document.getElementById("download").onclick = async () => {
  if (!await finishEditing() || !current || !pdfView || pdfView.pages > 1) return;
  setStatus("Building PDF…");
  try {
    const blob = await api(`/api/resumes/${current.resume_id}/pdf`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${current.name}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    setStatus("PDF ready");
  } catch (err) {
    setStatus(err.message);
  }
};

async function poll() {
  if (!current || activeEdit || savingEdit) return;
  try {
    const latest = await api(`/api/resumes/${current.resume_id}`);
    if (latest.revision !== current.revision && !activeEdit && !savingEdit) {
      current = latest;
      await renderPaper();
    }
  } catch {
    /* ignore */
  }
}

document.querySelectorAll("dialog").forEach((dlg) => {
  dlg.querySelectorAll("button[value]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      dlg.close(btn.value);
    });
  });
});

document.querySelectorAll(".actions-dropdown .menu-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    btn.closest("details")?.removeAttribute("open");
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".actions-dropdown")) {
    document.querySelectorAll(".actions-dropdown[open]").forEach((d) => d.removeAttribute("open"));
  }
});

refreshLists().then(() => {
  pollTimer = setInterval(poll, 2500);
}).catch(error => { setStatus("Could not open resume"); noticeEl.textContent = error.message; noticeEl.hidden = false; });
