const accountsEl = document.querySelector("#accounts");
const refreshBtn = document.querySelector("#refreshBtn");
const noticeEl = document.querySelector("#notice");

function showNotice(message, type = "") {
  noticeEl.textContent = message;
  noticeEl.className = `notice ${type}`.trim();
}

function hideNotice() {
  noticeEl.className = "notice hidden";
  noticeEl.textContent = "";
}

function pctText(value) {
  return Number.isFinite(value) ? `${value}%` : "-";
}

function meterClass(value) {
  if (!Number.isFinite(value)) return "";
  if (value <= 15) return "bad";
  if (value <= 35) return "warn";
  return "";
}

function usageRow(windowData) {
  const value = Number(windowData?.remaining_percent);
  const width = Number.isFinite(value) ? value : 0;
  return `
    <div class="usage-row">
      <div class="window">${windowData?.label || "-"}</div>
      <div class="percent">${pctText(value)}</div>
      <div class="reset">${windowData?.reset || "-"}</div>
      <div class="meter ${meterClass(value)}"><span style="width: ${width}%"></span></div>
    </div>
  `;
}

function cardHtml(account) {
  const usage = account.usage || {};
  const title = usage.email || usage.name || "未识别账号";
  const active = account.is_active ? "active" : "";
  const error = account.ok ? "" : "error";
  const badge = account.is_active ? "当前使用" : account.can_switch ? "可切换" : "默认路径";
  const switchDisabled = !account.ok || !account.can_switch || account.is_active;

  return `
    <article class="card ${active} ${error}">
      <div>
        <div class="card-head">
          <div>
            <h2 class="label">${account.label}</h2>
            <p class="email">${account.ok ? title : "读取失败"}</p>
          </div>
          <span class="badge ${active}">${badge}</span>
        </div>

        ${account.ok ? `
          <div class="usage">
            ${usageRow(usage.primary)}
            ${usageRow(usage.secondary)}
          </div>
          <p class="meta">计划：${usage.plan || "-"}<br>路径：${account.path}</p>
        ` : `
          <p class="error-text">${account.error || "未知错误"}</p>
          <p class="meta">路径：${account.path}</p>
        `}
      </div>

      <button class="button ${account.is_active ? "" : "primary"}" data-switch="${account.id}" ${switchDisabled ? "disabled" : ""}>
        ${account.is_active ? "正在使用" : "切换到此账号"}
      </button>
    </article>
  `;
}

async function loadAccounts({silent = false} = {}) {
  if (!silent) showNotice("正在刷新所有账号额度...");
  refreshBtn.disabled = true;
  try {
    const res = await fetch("/api/accounts");
    const data = await res.json();
    accountsEl.innerHTML = data.accounts.map(cardHtml).join("");
    bindSwitchButtons();
    if (!silent) showNotice("额度已刷新", "good");
  } catch (err) {
    showNotice(`刷新失败：${err.message}`, "bad");
  } finally {
    refreshBtn.disabled = false;
  }
}

function bindSwitchButtons() {
  document.querySelectorAll("[data-switch]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-switch");
      btn.disabled = true;
      showNotice("正在关闭 Codex、备份当前认证并切换账号...");
      try {
        const res = await fetch("/api/switch", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({id}),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "切换失败");
        }
        accountsEl.innerHTML = data.accounts.map(cardHtml).join("");
        bindSwitchButtons();
        showNotice(`已切换到 ${data.result.label}，Codex 正在重新启动。备份：${data.result.backup}`, "good");
      } catch (err) {
        showNotice(`切换失败：${err.message}`, "bad");
        btn.disabled = false;
      }
    });
  });
}

refreshBtn.addEventListener("click", () => loadAccounts());
loadAccounts({silent: true}).then(hideNotice);
