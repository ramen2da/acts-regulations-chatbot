const els = {
  question: document.getElementById("question"),
  askBtn: document.getElementById("askBtn"),
  status: document.getElementById("status"),
  answer: document.getElementById("answer"),
  sources: document.getElementById("sources"),
  regSelect: document.getElementById("regSelect"),
  articleSelect: document.getElementById("articleSelect"),
  lookupBtn: document.getElementById("lookupBtn"),
  lookupStatus: document.getElementById("lookupStatus"),
  lookupResults: document.getElementById("lookupResults"),
};

let corpus = null;
let manifest = null;
const worker = new Worker("./embed-worker.js", { type: "module" });
let pendingRequests = new Map();
let nextRequestId = 0;

worker.onmessage = (e) => {
  const { type, requestId } = e.data;
  if (type === "progress") {
    if (e.data.progress?.status === "progress") {
      setStatus(`임베딩 모델 다운로드 중... ${Math.round(e.data.progress.progress || 0)}%`);
    }
    return;
  }
  const resolver = pendingRequests.get(requestId);
  if (!resolver) return;
  pendingRequests.delete(requestId);
  if (type === "embed_result") resolver.resolve(e.data.dense);
  else resolver.reject(new Error(e.data.error));
};

function embedQuery(text) {
  const requestId = nextRequestId++;
  return new Promise((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    worker.postMessage({ type: "embed_query", text, requestId });
  });
}

function setStatus(text) {
  els.status.textContent = text;
}

async function loadCorpus() {
  setStatus("규정 데이터 불러오는 중...");
  const manifestRes = await fetch(CONFIG.MANIFEST_URL);
  manifest = await manifestRes.json();

  worker.postMessage({ type: "init", modelId: CONFIG.EMBED_MODEL_ID, dtype: CONFIG.EMBED_DTYPE });

  const shards = await Promise.all(
    manifest.shards.map((name) =>
      fetch(`./data/embeddings/${name}?build=${manifest.buildId ?? ""}`).then((r) => r.json())
    )
  );

  corpus = shards.flat().map((c) => ({ ...c, dense: Float32Array.from(c.dense) }));
  setStatus(`${corpus.length}개 조항 로드 완료. 질문을 입력하세요.`);
  populateRegSelect();
}

function populateRegSelect() {
  const seen = new Set();
  els.regSelect.innerHTML = "";
  for (const c of corpus) {
    if (!c.article_no || seen.has(c.regulation)) continue;
    seen.add(c.regulation);
    const opt = document.createElement("option");
    opt.value = c.regulation;
    opt.textContent = c.regulation;
    els.regSelect.appendChild(opt);
  }
  populateArticleSelect();
}

function populateArticleSelect() {
  const regName = els.regSelect.value;
  els.articleSelect.innerHTML = "";
  for (const c of corpus) {
    if (c.regulation !== regName || !c.article_no) continue;
    const opt = document.createElement("option");
    opt.value = c.article_no;
    opt.textContent = `${c.article_no}(${c.article_title || ""})`;
    els.articleSelect.appendChild(opt);
  }
}

function findSimilarAcrossRegulations(baseChunk, k) {
  const scored = [];
  for (const c of corpus) {
    if (c.regulation === baseChunk.regulation || !c.article_no) continue;
    let dot = 0;
    for (let i = 0; i < baseChunk.dense.length; i++) dot += baseChunk.dense[i] * c.dense[i];
    scored.push({ chunk: c, score: dot });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}

function renderLookupResults(baseChunk, results) {
  els.lookupResults.innerHTML = "";

  results.forEach(({ chunk, score }) => {
    const card = document.createElement("div");
    card.className = "result-card";

    const head = document.createElement("div");
    head.className = "result-head";
    head.innerHTML = `<span>${chunk.section_path}</span><span class="result-score">유사도 ${score.toFixed(3)}</span>`;

    const text = document.createElement("p");
    text.className = "result-text collapsed";
    text.textContent = chunk.text;

    const toggle = document.createElement("button");
    toggle.className = "toggle-btn";
    toggle.textContent = "더보기";
    toggle.addEventListener("click", () => {
      text.classList.toggle("collapsed");
      toggle.textContent = text.classList.contains("collapsed") ? "더보기" : "접기";
    });

    card.append(head, text, toggle);
    els.lookupResults.appendChild(card);
  });

  const compareBtn = document.createElement("button");
  compareBtn.className = "compare-btn";
  compareBtn.textContent = "AI로 비교 설명 요청";
  compareBtn.addEventListener("click", () => handleCompare(baseChunk, results, compareBtn));
  els.lookupResults.appendChild(compareBtn);
}

function buildComparePrompt(baseChunk, results) {
  const excerpts = results
    .map(({ chunk }, i) => `[발췌 ${i + 1}] (${chunk.section_path})\n${chunk.text}`)
    .join("\n\n");

  return (
    "너는 아신대학교(ACTS) 규정집을 검토하는 어시스턴트다. " +
    "아래 [기준 조항]과 [발췌 N]들을 비교해서, 서로 같은 내용을 다루는지, " +
    "기준·수치·용어가 다르거나 상충되는 부분이 있는지, " +
    "기준 조항을 개정하면 함께 검토해야 할 발췌가 무엇인지 구체적으로 짚어줘. " +
    "근거로 쓴 발췌문 번호를 [발췌 N] 형식으로 표시해라.\n\n" +
    `[기준 조항] (${baseChunk.section_path})\n${baseChunk.text}\n\n${excerpts}`
  );
}

async function handleCompare(baseChunk, results, triggerBtn) {
  triggerBtn.disabled = true;
  els.answer.textContent = "";
  els.sources.textContent = "";
  setStatus("비교 설명 생성 중...");

  try {
    const prompt = buildComparePrompt(baseChunk, results);
    const answer = await askGemini(prompt);
    els.answer.textContent = answer;
    els.sources.textContent =
      "출처: " +
      [baseChunk, ...results.map((r) => r.chunk)].map(sourceLabel).join(" · ");
    setStatus("완료");
    els.answer.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    els.answer.textContent = `오류: ${err.message}`;
    setStatus("오류 발생");
  } finally {
    triggerBtn.disabled = false;
  }
}

function handleLookup() {
  if (!corpus) return;
  const regName = els.regSelect.value;
  const articleNo = els.articleSelect.value;
  const baseChunk = corpus.find((c) => c.regulation === regName && c.article_no === articleNo);
  if (!baseChunk) {
    els.lookupStatus.textContent = "해당 조항을 찾을 수 없습니다.";
    return;
  }

  els.lookupStatus.textContent = "다른 규정에서 유사한 조항 검색 중...";
  const results = findSimilarAcrossRegulations(baseChunk, 8);
  renderLookupResults(baseChunk, results);
  els.lookupStatus.textContent = `${baseChunk.section_path} 기준 유사 조항 ${results.length}건`;
}

function topKByCosine(queryDense, k) {
  const scored = corpus.map((chunk) => {
    let dot = 0;
    for (let i = 0; i < queryDense.length; i++) dot += queryDense[i] * chunk.dense[i];
    return { chunk, score: dot };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}

function sourceLabel(chunk) {
  return `${chunk.regulation} p.${chunk.pdf_page_start}`;
}

function buildPrompt(question, topChunks) {
  const excerpts = topChunks
    .map(
      ({ chunk }, i) =>
        `[발췌 ${i + 1}] (${chunk.section_path})\n${chunk.text}`
    )
    .join("\n\n");

  return (
    "너는 아신대학교(ACTS) 규정집을 근거로만 답하는 어시스턴트다. " +
    "아래 발췌문에 있는 내용만 사용해서 답하고, 발췌에 없는 내용은 모른다고 말해라. " +
    "규정 간에 서로 다른 기준이나 상충되는 내용이 보이면 반드시 짚어서 알려줘. " +
    "답변에서 근거로 쓴 발췌문 번호를 [발췌 N] 형식으로 표시해라.\n\n" +
    `${excerpts}\n\n질문: ${question}`
  );
}

async function askGemini(prompt) {
  const res = await fetch(CONFIG.GEMINI_PROXY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.2 },
    }),
  });
  if (!res.ok) throw new Error(`Gemini 프록시 오류: ${res.status}`);
  const data = await res.json();
  return data?.candidates?.[0]?.content?.parts?.map((p) => p.text).join("") ?? "(응답 없음)";
}

async function handleAsk() {
  const question = els.question.value.trim();
  if (!question || !corpus) return;

  els.askBtn.disabled = true;
  els.answer.textContent = "";
  els.sources.textContent = "";

  try {
    setStatus("질문 임베딩 중...");
    const queryDense = await embedQuery(question);

    setStatus("관련 조항 검색 중...");
    const topChunks = topKByCosine(queryDense, CONFIG.TOP_K);

    setStatus("답변 생성 중...");
    const prompt = buildPrompt(question, topChunks);
    const answer = await askGemini(prompt);

    els.answer.textContent = answer;
    els.sources.textContent =
      "출처: " + topChunks.map(({ chunk }) => sourceLabel(chunk)).join(" · ");
    setStatus("완료");
  } catch (err) {
    els.answer.textContent = `오류: ${err.message}`;
    setStatus("오류 발생");
  } finally {
    els.askBtn.disabled = false;
  }
}

els.askBtn.addEventListener("click", handleAsk);
els.question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleAsk();
  }
});

els.regSelect.addEventListener("change", populateArticleSelect);
els.lookupBtn.addEventListener("click", handleLookup);

loadCorpus().catch((err) => setStatus(`로드 오류: ${err.message}`));
