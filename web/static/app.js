const $ = (id) => document.getElementById(id);

const state = {
  providers: {},
  books: {},
};

function renderMd(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^[-*] (.+)$/gm, "<li>$1</li>")
    .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n/g, "<br>");
}

function settings() {
  return {
    provider: $("provider").value,
    model: $("model").value.trim(),
    api_key: $("api-key").value.trim(),
    top_k: 4,
  };
}

function saveLocal() {
  localStorage.setItem(
    "fkb-settings",
    JSON.stringify({
      provider: $("provider").value,
      model: $("model").value,
      api_key: $("api-key").value,
      search_only: $("search-only").checked,
    })
  );
}

function loadLocal() {
  try {
    return JSON.parse(localStorage.getItem("fkb-settings") || "{}");
  } catch {
    return {};
  }
}

function addMsg(role, html, cls) {
  const box = document.createElement("div");
  box.className = `msg ${role} ${cls || ""}`;
  box.innerHTML = `<div class="role">${role === "user" ? "你" : "知识库"}</div><div class="body">${html}</div>`;
  $("chat").appendChild(box);
  $("chat").scrollTop = $("chat").scrollHeight;
  return box;
}

function renderBooks(books) {
  const names = { 上: "上册 无机氟化工", 中: "中册 有机氟化工", 下: "下册 含氟聚合物" };
  $("book-status").innerHTML = Object.entries(names)
    .map(([k, title]) => {
      const info = books[k] || { pages: 0, ready: false };
      const cls = info.ready ? "ok" : "wait";
      const label = info.ready ? `${info.pages} 页` : "正在入库…";
      return `<div class="book"><span>${title}</span><small class="${cls}">${label}</small></div>`;
    })
    .join("");
}

function renderExtras(extra) {
  const items = (extra && extra.items) || [];
  const box = $("extra-list");
  if (!items.length) {
    box.innerHTML = `<div class="hint">还没有补充资料。</div>`;
    return;
  }
  box.innerHTML = items
    .map((d) => {
      const title = (d.title || "未命名").replace(/</g, "&lt;");
      return `<div class="extra-item" data-id="${d.id}">
        <span>${title}<small>${d.chars || 0} 字 · ${d.pages || 0} 段</small></span>
        <button type="button" data-del="${d.id}">删除</button>
      </div>`;
    })
    .join("");
}

function applyIndex(data) {
  if (data.books) {
    state.books = data.books;
    renderBooks(data.books);
  }
  const extra = data.extra || (data.books && data.books.extra) || { items: [] };
  renderExtras(extra);
  if (data.chunks != null) {
    $("index-meta").textContent = `已切分 ${data.chunks} 段 · 向量 ${data.vector_dim || "-"} 维 · ${data.retriever || "混合检索"}`;
  }
}

function extraError(err) {
  if (!err) return "入库失败";
  if (typeof err === "string") return err;
  if (Array.isArray(err)) return err.map((x) => x.msg || x).join("；");
  return err.msg || err.message || "入库失败";
}

function fillProviders(providers, saved) {
  $("provider").innerHTML = Object.entries(providers)
    .map(([k, v]) => `<option value="${k}">${v.name}</option>`)
    .join("");
  const current = saved.provider && providers[saved.provider] ? saved.provider : "deepseek";
  $("provider").value = current;
  $("model").value = saved.model || providers[current].model;
  $("api-key").value = saved.api_key || "";
  $("search-only").checked = !!saved.search_only;
  $("provider-hint").textContent = providers[current].hint;
}

async function refreshStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  state.providers = data.providers;
  state.books = data.books;
  renderBooks(data.books);
  renderExtras(data.extra || data.books.extra);
  $("index-meta").textContent = data.ready
    ? `已切分 ${data.chunks} 段 · 向量 ${data.vector_dim || "-"} 维 · ${data.retriever || "混合检索"}`
    : "尚未建立向量索引，请点击重建检索索引";
  if (!$("provider").options.length) fillProviders(data.providers, loadLocal());
}

async function rebuild() {
  $("rebuild-btn").disabled = true;
  $("rebuild-btn").textContent = "正在重建…";
  try {
    const res = await fetch("/api/rebuild", { method: "POST" });
    const data = await res.json();
    applyIndex(data);
  } finally {
    $("rebuild-btn").disabled = false;
    $("rebuild-btn").textContent = "重建检索索引";
  }
}

function setExtraBusy(busy, text) {
  $("extra-add-btn").disabled = busy;
  $("extra-file").disabled = busy;
  $("rebuild-btn").disabled = busy;
  $("extra-add-btn").textContent = busy ? text || "正在更新向量库…" : "加入并更新知识库";
}

async function addExtraText() {
  const title = $("extra-title").value.trim();
  const text = $("extra-text").value.trim();
  const msg = $("extra-msg");
  if (!text) {
    msg.className = "hint err";
    msg.textContent = "请先粘贴要入库的正文。";
    return;
  }
  setExtraBusy(true);
  msg.className = "hint";
  msg.textContent = "正在切分文本并重建向量库，请稍候…";
  try {
    const res = await fetch("/api/extra", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, text }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(extraError(data.detail));
    }
    applyIndex(data);
    $("extra-text").value = "";
    msg.className = "hint ok-msg";
    msg.textContent = `已加入「${(data.doc && data.doc.title) || title || "补充资料"}」，知识库已更新。`;
  } catch (err) {
    msg.className = "hint err";
    msg.textContent = extraError(err.message || err);
  } finally {
    setExtraBusy(false);
  }
}

async function uploadExtraFile(e) {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  const msg = $("extra-msg");
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("title", $("extra-title").value.trim());
  setExtraBusy(true);
  msg.className = "hint";
  msg.textContent = `正在解析 ${file.name} 并更新向量库…`;
  try {
    const res = await fetch("/api/extra/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(extraError(data.detail));
    }
    applyIndex(data);
    msg.className = "hint ok-msg";
    msg.textContent = `已加入「${(data.doc && data.doc.title) || file.name}」，知识库已更新。`;
  } catch (err) {
    msg.className = "hint err";
    msg.textContent = extraError(err.message || err);
  } finally {
    setExtraBusy(false);
  }
}

async function deleteExtra(id) {
  if (!window.confirm("删除后会从向量库里去掉这篇资料，确定吗？")) return;
  const msg = $("extra-msg");
  setExtraBusy(true, "正在删除并更新…");
  try {
    const res = await fetch(`/api/extra/${encodeURIComponent(id)}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(extraError(data.detail));
    }
    applyIndex(data);
    msg.className = "hint ok-msg";
    msg.textContent = "已删除，知识库已更新。";
  } catch (err) {
    msg.className = "hint err";
    msg.textContent = extraError(err.message || err);
  } finally {
    setExtraBusy(false);
  }
}

function renderSources(items) {
  if (!items || !items.length) return "";
  const cards = items
    .map((h, i) => {
      const text = (h.snippet || "").replace(/</g, "&lt;").replace(/\n/g, "<br>");
      const score = h.score != null ? ` · 相似度 ${h.score}` : "";
      return `<div class="src"><b>片段${i + 1} ${h.cite || ""}${score}</b><p>${text}</p></div>`;
    })
    .join("");
  return `<details class="sources-wrap" open><summary>检索到的知识片段（向量库 Top ${items.length}）</summary><div class="sources">${cards}</div></details>`;
}

async function ask(question) {
  const q = question.trim();
  if (!q) return;
  const welcome = document.querySelector(".welcome");
  if (welcome) welcome.remove();
  addMsg("user", renderMd(q));
  const bot = addMsg("bot", "正在检索教材原文…");
  const bodyEl = bot.querySelector(".body");
  $("send-btn").disabled = true;
  saveLocal();

  try {
    if ($("search-only").checked) {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, ...settings() }),
      });
      const data = await res.json();
      const answer = data.answer || (data.hits && data.hits[0] && data.hits[0].snippet) || "正在重建索引，请稍后再问一次。";
      bodyEl.innerHTML = `<div class="answer">${renderMd(answer)}</div>${renderSources(data.hits)}`;
      return;
    }

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, ...settings() }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let answer = "";
    let sources = [];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = JSON.parse(line.slice(5).trim());
        if (payload.type === "sources") {
          sources = payload.items || [];
        } else if (payload.type === "token") {
          answer += payload.text;
          bodyEl.innerHTML = `<div class="answer">${renderMd(answer)}</div>`;
        } else if (payload.type === "error") {
          bot.classList.add("error");
          bodyEl.innerHTML = renderMd(payload.text || "调用模型失败");
        } else if (payload.type === "done") {
          bodyEl.innerHTML = `<div class="answer">${renderMd(answer)}</div>${renderSources(sources)}`;
        }
      }
      $("chat").scrollTop = $("chat").scrollHeight;
    }
    if (!answer) {
      bodyEl.innerHTML = `<div class="answer">没有生成回答。请检查 API Key，或改用「仅检索原文」。</div>${renderSources(sources)}`;
    }
  } catch (err) {
    bot.classList.add("error");
    bodyEl.textContent = String(err);
  } finally {
    $("send-btn").disabled = false;
  }
}

$("provider").addEventListener("change", () => {
  const p = state.providers[$("provider").value];
  if (p) {
    $("model").value = p.model;
    $("provider-hint").textContent = p.hint;
  }
  saveLocal();
});
["model", "api-key", "search-only"].forEach((id) => $(id).addEventListener("change", saveLocal));
$("rebuild-btn").addEventListener("click", rebuild);
$("extra-add-btn").addEventListener("click", addExtraText);
$("extra-file").addEventListener("change", uploadExtraFile);
$("extra-list").addEventListener("click", (e) => {
  const id = e.target && e.target.dataset && e.target.dataset.del;
  if (id) deleteExtra(id);
});
$("clear-btn").addEventListener("click", () => {
  $("chat").innerHTML = "";
  showWelcome();
});
$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("question").value;
  $("question").value = "";
  ask(q);
});
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
document.querySelectorAll(".examples button").forEach((btn) => {
  btn.addEventListener("click", () => ask(btn.dataset.q));
});

function showWelcome() {
  $("chat").innerHTML = `
    <div class="welcome">
      <h2>从三册《氟化工生产技术》中检索后再回答</h2>
      <p>教材和你随时加入的补充资料都会切成片段写入向量库。提问时先检索，再归纳成回答；下方「知识片段」是命中原文，与回答不是同一段复制。</p>
    </div>`;
}

showWelcome();
refreshStatus();
setInterval(refreshStatus, 15000);
