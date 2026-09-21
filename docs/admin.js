const REPO = { owner: "ramen2da", name: "acts-regulations-chatbot", branch: "main" };
const CATEGORIES = ["정관", "대학", "대학원", "일반행정", "부속기관 및 부설기관", "산학협력단"];
const SECTION_TYPES = [
  { value: "article", label: "조항" },
  { value: "table", label: "별표" },
  { value: "form", label: "양식" },
  { value: "note", label: "기타/전문" },
];

const els = {
  tokenGate: document.getElementById("tokenGate"),
  tokenInput: document.getElementById("tokenInput"),
  tokenSaveBtn: document.getElementById("tokenSaveBtn"),
  tokenStatus: document.getElementById("tokenStatus"),
  adminArea: document.getElementById("adminArea"),
  newRegBtn: document.getElementById("newRegBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  regList: document.getElementById("regList"),
  editorCard: document.getElementById("editorCard"),
  editorHeading: document.getElementById("editorHeading"),
  fTitle: document.getElementById("fTitle"),
  fCategory: document.getElementById("fCategory"),
  fOrder: document.getElementById("fOrder"),
  sectionsList: document.getElementById("sectionsList"),
  addSectionBtn: document.getElementById("addSectionBtn"),
  saveBtn: document.getElementById("saveBtn"),
  deleteRegBtn: document.getElementById("deleteRegBtn"),
  cancelBtn: document.getElementById("cancelBtn"),
  saveStatus: document.getElementById("saveStatus"),
};

let currentDoc = null; // { id, sha (null if new), title, category, order, sourceFile, sections: [] }

function b64EncodeUnicode(str) {
  return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => String.fromCharCode(parseInt(p1, 16))));
}

function b64DecodeUnicode(b64) {
  const clean = b64.replace(/\n/g, "");
  return decodeURIComponent(
    atob(clean)
      .split("")
      .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
      .join("")
  );
}

function getToken() {
  return localStorage.getItem("gh_token") || "";
}

async function ghApi(path, options = {}) {
  const res = await fetch(`https://api.github.com/repos/${REPO.owner}/${REPO.name}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${getToken()}`,
      Accept: "application/vnd.github+json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub API ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.status === 204 ? null : res.json();
}

function slugify(name) {
  return (
    name
      .normalize("NFC")
      .replace(/[^\w가-힣.\-]+/g, "_")
      .replace(/^_+|_+$/g, "") || "unnamed"
  );
}

function contentPath(id) {
  return `content/regulations/${id}.json`;
}

async function fetchIndex() {
  const data = await ghApi(`/contents/content/index.json?ref=${REPO.branch}`);
  return { entries: JSON.parse(b64DecodeUnicode(data.content)), sha: data.sha };
}

async function fetchRegulation(id) {
  const data = await ghApi(`/contents/${contentPath(id)}?ref=${REPO.branch}`);
  return { doc: JSON.parse(b64DecodeUnicode(data.content)), sha: data.sha };
}

async function putFile(path, obj, sha, message) {
  const body = {
    message,
    content: b64EncodeUnicode(JSON.stringify(obj, null, 2)),
    branch: REPO.branch,
  };
  if (sha) body.sha = sha;
  return ghApi(`/contents/${path}`, { method: "PUT", body: JSON.stringify(body) });
}

async function deleteFile(path, sha, message) {
  return ghApi(`/contents/${path}`, {
    method: "DELETE",
    body: JSON.stringify({ message, sha, branch: REPO.branch }),
  });
}

// ---------- UI: token gate ----------

function showAdmin() {
  els.tokenGate.classList.add("hidden");
  els.adminArea.classList.remove("hidden");
  loadRegList();
}

els.tokenSaveBtn.addEventListener("click", () => {
  const t = els.tokenInput.value.trim();
  if (!t) return;
  localStorage.setItem("gh_token", t);
  showAdmin();
});

els.logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("gh_token");
  location.reload();
});

// ---------- UI: regulation list ----------

async function loadRegList() {
  els.regList.innerHTML = "불러오는 중...";
  try {
    const { entries } = await fetchIndex();
    els.regList.innerHTML = "";
    for (const cat of CATEGORIES) {
      const items = entries.filter((e) => e.category === cat).sort((a, b) => a.order - b.order);
      if (!items.length) continue;
      const block = document.createElement("div");
      block.className = "reg-category";
      block.innerHTML = `<h3>${cat} (${items.length})</h3>`;
      for (const item of items) {
        const row = document.createElement("div");
        row.className = "reg-item";
        row.innerHTML = `<span><span class="reg-order">${item.order}</span>${item.title}</span>`;
        row.addEventListener("click", () => openEditor(item.id));
        block.appendChild(row);
      }
      els.regList.appendChild(block);
    }
  } catch (err) {
    els.regList.textContent = `목록 로드 오류: ${err.message}`;
  }
}

// ---------- UI: editor ----------

function renderSections(sections) {
  els.sectionsList.innerHTML = "";
  sections.forEach((s, i) => addSectionRow(s, i));
}

function addSectionRow(section, index) {
  const row = document.createElement("div");
  row.className = "section-item";
  row.dataset.index = index;

  const typeOptions = SECTION_TYPES.map(
    (t) => `<option value="${t.value}" ${t.value === (section.type || "article") ? "selected" : ""}>${t.label}</option>`
  ).join("");

  row.innerHTML = `
    <div class="section-row1">
      <select class="s-type">${typeOptions}</select>
      <input class="s-no" type="text" placeholder="제N조" value="${section.no ?? ""}" />
      <input class="s-title" type="text" placeholder="제목" value="${section.title ?? ""}" />
      <div class="section-controls">
        <button type="button" class="s-up" title="위로">▲</button>
        <button type="button" class="s-down" title="아래로">▼</button>
        <button type="button" class="s-del" title="삭제">삭제</button>
      </div>
    </div>
    <textarea class="s-text" placeholder="본문">${section.text ?? ""}</textarea>
    <div class="amend-row">
      <input class="s-amend-date" type="date" value="${todayIso()}" />
      <button type="button" class="s-amend-insert">＋ 개정일자 태그를 커서 위치에 삽입</button>
    </div>
  `;

  row.querySelector(".s-del").addEventListener("click", () => row.remove());
  row.querySelector(".s-up").addEventListener("click", () => {
    const prev = row.previousElementSibling;
    if (prev) row.parentNode.insertBefore(row, prev);
  });
  row.querySelector(".s-down").addEventListener("click", () => {
    const next = row.nextElementSibling;
    if (next) row.parentNode.insertBefore(next, row);
  });
  row.querySelector(".s-amend-insert").addEventListener("click", () => {
    const dateVal = row.querySelector(".s-amend-date").value; // yyyy-mm-dd
    if (!dateVal) return;
    const [y, m, d] = dateVal.split("-").map((n) => parseInt(n, 10));
    const tag = `<개정 ${y}. ${m}. ${d}.>`;
    insertAtCursor(row.querySelector(".s-text"), tag);
  });

  els.sectionsList.appendChild(row);
}

function todayIso() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function insertAtCursor(textarea, text) {
  const start = textarea.selectionStart ?? textarea.value.length;
  const end = textarea.selectionEnd ?? textarea.value.length;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  // keep tags visually separated from surrounding text like the existing
  // documents do ("...한다. <개정 2023. 4. 4.> <개정 2023. 12. 14.>...")
  const spacedBefore = before && !before.endsWith(" ") ? before + " " : before;
  const spacedAfter = after && !after.startsWith(" ") ? " " + after : after;
  textarea.value = spacedBefore + text + spacedAfter;
  const cursorPos = spacedBefore.length + text.length;
  textarea.focus();
  textarea.setSelectionRange(cursorPos, cursorPos);
}

function readSectionsFromForm() {
  return Array.from(els.sectionsList.children).map((row) => ({
    type: row.querySelector(".s-type").value,
    no: row.querySelector(".s-no").value.trim() || null,
    title: row.querySelector(".s-title").value.trim() || null,
    text: row.querySelector(".s-text").value,
  }));
}

els.addSectionBtn.addEventListener("click", () => {
  addSectionRow({ type: "article", no: "", title: "", text: "" }, els.sectionsList.children.length);
});

async function openEditor(id) {
  els.saveStatus.textContent = "불러오는 중...";
  try {
    const { doc, sha } = await fetchRegulation(id);
    currentDoc = { ...doc, sha, isNew: false };
    els.editorHeading.textContent = `규정 편집: ${doc.title}`;
    els.fTitle.value = doc.title;
    els.fCategory.value = doc.category;
    els.fOrder.value = doc.order;
    renderSections(doc.sections || []);
    els.deleteRegBtn.classList.remove("hidden");
    els.editorCard.classList.remove("hidden");
    els.editorCard.scrollIntoView({ behavior: "smooth" });
    els.saveStatus.textContent = "";
  } catch (err) {
    els.saveStatus.textContent = `불러오기 오류: ${err.message}`;
  }
}

els.newRegBtn.addEventListener("click", () => {
  currentDoc = { id: null, sha: null, isNew: true, sourceFile: "관리자 신설" };
  els.editorHeading.textContent = "새 규정 만들기";
  els.fTitle.value = "";
  els.fCategory.value = "일반행정";
  els.fOrder.value = "";
  renderSections([{ type: "article", no: "제1조", title: "목적", text: "" }]);
  els.deleteRegBtn.classList.add("hidden");
  els.editorCard.classList.remove("hidden");
  els.editorCard.scrollIntoView({ behavior: "smooth" });
  els.saveStatus.textContent = "";
});

els.cancelBtn.addEventListener("click", () => {
  els.editorCard.classList.add("hidden");
  currentDoc = null;
});

async function updateIndexEntry(entry) {
  const { entries, sha } = await fetchIndex();
  const i = entries.findIndex((e) => e.id === entry.id);
  if (i >= 0) entries[i] = entry;
  else entries.push(entry);
  await putFile("content/index.json", entries, sha, `색인 갱신: ${entry.title}`);
}

async function removeIndexEntry(id) {
  const { entries, sha } = await fetchIndex();
  const filtered = entries.filter((e) => e.id !== id);
  await putFile("content/index.json", filtered, sha, `색인에서 제거: ${id}`);
}

els.saveBtn.addEventListener("click", async () => {
  if (!currentDoc) return;
  const title = els.fTitle.value.trim();
  const category = els.fCategory.value;
  const order = parseInt(els.fOrder.value, 10) || 1;
  if (!title) {
    els.saveStatus.textContent = "규정명을 입력하세요.";
    return;
  }

  const id = currentDoc.isNew ? slugify(title) : currentDoc.id;
  const doc = {
    id,
    title,
    category,
    order,
    sourceFile: currentDoc.sourceFile || "관리자 편집",
    sections: readSectionsFromForm(),
  };

  els.saveBtn.disabled = true;
  els.saveStatus.textContent = "저장 중...";
  try {
    await putFile(
      contentPath(id),
      doc,
      currentDoc.isNew ? null : currentDoc.sha,
      currentDoc.isNew ? `규정 신설: ${title}` : `규정 수정: ${title}`
    );
    await updateIndexEntry({ id, title, category, order });
    els.saveStatus.textContent = "저장 완료. 검색 색인은 자동으로 몇 분 내 갱신됩니다.";
    currentDoc.isNew = false;
    currentDoc.id = id;
    await loadRegList();
  } catch (err) {
    els.saveStatus.textContent = `저장 오류: ${err.message}`;
  } finally {
    els.saveBtn.disabled = false;
  }
});

els.deleteRegBtn.addEventListener("click", async () => {
  if (!currentDoc || currentDoc.isNew) return;
  if (!confirm(`"${currentDoc.title}" 규정을 정말 삭제할까요? 되돌리려면 GitHub 커밋 기록에서 복구해야 합니다.`)) return;

  els.saveStatus.textContent = "삭제 중...";
  try {
    await deleteFile(contentPath(currentDoc.id), currentDoc.sha, `규정 삭제: ${currentDoc.title}`);
    await removeIndexEntry(currentDoc.id);
    els.editorCard.classList.add("hidden");
    currentDoc = null;
    await loadRegList();
  } catch (err) {
    els.saveStatus.textContent = `삭제 오류: ${err.message}`;
  }
});

if (getToken()) showAdmin();
