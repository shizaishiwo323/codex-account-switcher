const accountsEl = document.querySelector("#accounts");
const refreshBtn = document.querySelector("#refreshBtn");
const quotaSortBtn = document.querySelector("#quotaSortBtn");
const noticeEl = document.querySelector("#notice");
const switchSyncDialogEl = document.querySelector("#switchSyncDialog");
const switchSyncMessageEl = document.querySelector("#switchSyncMessage");
const switchSyncCloseBtn = document.querySelector("#switchSyncClose");
const accountSummaryEl = document.querySelector("#accountSummary");
const cumulativeChartEl = document.querySelector("#cumulativeChart");
const cumulativeEmptyEl = document.querySelector("#cumulativeEmpty");
const cumulativeValueEl = document.querySelector("#cumulativeValue");
const activityChartEl = document.querySelector("#activityChart");
const activityEmptyEl = document.querySelector("#activityEmpty");
const activityValueEl = document.querySelector("#activityValue");
const historyMetaEl = document.querySelector("#historyMeta");
const historyStartInput = document.querySelector("#historyStart");
const historyEndInput = document.querySelector("#historyEnd");

const cumulativeColor = "#0f766e";
const activityColor = "#2563eb";
let latestHistory = null;
let monitorOnly = false;
let latestAccounts = [];
let quotaSortEnabled = false;

function showNotice(message, type = "") {
  noticeEl.textContent = message;
  noticeEl.className = `notice ${type}`.trim();
}

function hideNotice() {
  noticeEl.className = "notice hidden";
  noticeEl.textContent = "";
}

function showSwitchSyncDialog(message) {
  if (!switchSyncDialogEl || !switchSyncMessageEl) return;
  switchSyncMessageEl.textContent = message;
  switchSyncDialogEl.classList.remove("hidden");
  switchSyncCloseBtn?.focus();
}

function hideSwitchSyncDialog() {
  switchSyncDialogEl?.classList.add("hidden");
}

function pctText(value) {
  return Number.isFinite(value) ? `${value}%` : "-";
}

function numberOrNull(value) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shortTime(timestamp) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp * 1000));
}

function fullTime(timestamp) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp * 1000));
}

function usedText(value) {
  const numberValue = numberOrNull(value);
  if (numberValue === null) return "-";
  return `${Math.round(numberValue * 10) / 10}%`;
}

function safeFileBase(value) {
  return String(value || "account").replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "") || "account";
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
      <div class="window">${escapeHtml(windowData?.label || "-")}</div>
      <div class="percent">${pctText(value)}</div>
      <div class="reset">${escapeHtml(windowData?.reset || "-")}</div>
      <div class="meter ${meterClass(value)}"><span style="width: ${width}%"></span></div>
    </div>
  `;
}

function windowRemainingByLabel(usage, label) {
  const windows = [usage.primary, usage.secondary];
  const windowData = windows.find((item) => item?.label === label);
  return numberOrNull(windowData?.remaining_percent);
}

function hasEnoughSwitchQuota(usage) {
  const fiveHourRemaining = windowRemainingByLabel(usage, "5小时");
  const weeklyRemaining = windowRemainingByLabel(usage, "1周");
  if (weeklyRemaining === null || weeklyRemaining <= 0) return false;
  if (fiveHourRemaining === null) return true;
  return fiveHourRemaining > 0;
}

function quotaSortNumber(value, fallback = -1) {
  return value === null ? fallback : value;
}

function accountSortMetrics(account) {
  const usage = account.usage || {};
  return {
    weekly: quotaSortNumber(windowRemainingByLabel(usage, "1周")),
    fiveHour: quotaSortNumber(windowRemainingByLabel(usage, "5小时")),
    ok: account.ok ? 1 : 0,
  };
}

function orderedAccounts(accounts) {
  return accounts
    .map((account, index) => ({account, index, metrics: accountSortMetrics(account)}))
    .sort((left, right) => {
      if (left.account.is_active !== right.account.is_active) {
        return left.account.is_active ? -1 : 1;
      }
      if (!quotaSortEnabled) {
        return left.index - right.index;
      }
      if (left.metrics.weekly !== right.metrics.weekly) {
        return right.metrics.weekly - left.metrics.weekly;
      }
      if (left.metrics.fiveHour !== right.metrics.fiveHour) {
        return right.metrics.fiveHour - left.metrics.fiveHour;
      }
      if (left.metrics.ok !== right.metrics.ok) {
        return right.metrics.ok - left.metrics.ok;
      }
      return left.index - right.index;
    })
    .map((item) => item.account);
}

function updateQuotaSortButton() {
  quotaSortBtn.classList.toggle("active", quotaSortEnabled);
  quotaSortBtn.setAttribute("aria-pressed", String(quotaSortEnabled));
  quotaSortBtn.textContent = quotaSortEnabled ? "恢复默认" : "额度降序";
}

function normalizedPlan(account) {
  return String(account.usage?.plan || "").toLowerCase();
}

function accountSummary(accounts) {
  return accounts.reduce((summary, account) => {
    const plan = normalizedPlan(account);
    summary.total += 1;
    if (plan === "plus") summary.plus += 1;
    if (plan === "free") summary.free += 1;
    if (account.ok && hasEnoughSwitchQuota(account.usage || {})) summary.usable += 1;
    return summary;
  }, {total: 0, plus: 0, free: 0, usable: 0});
}

function renderAccountSummary(accounts) {
  const summary = accountSummary(accounts);
  const items = [
    ["账号", summary.total],
    ["Plus", summary.plus],
    ["免费", summary.free],
    ["可使用", summary.usable],
  ];
  accountSummaryEl.innerHTML = items.map(([label, value]) => `
    <div class="summary-item">
      <span>${label}</span>
      <strong>${value}</strong>
    </div>
  `).join("");
}

function renderAccounts(accounts) {
  latestAccounts = accounts;
  renderAccountSummary(accounts);
  accountsEl.innerHTML = orderedAccounts(accounts).map(cardHtml).join("");
  bindDownloadButtons();
  bindUploadButtons();
  bindSwitchButtons();
  bindKeepaliveButtons();
  updateQuotaSortButton();
}

function keepaliveStatusText(keepalive) {
  if (!keepalive?.enabled) return "";
  const running = keepalive.running ? "运行中" : "未运行";
  if (keepalive.mode === "off") return `后台保活：手动停止 · ${running}`;
  if (keepalive.mode === "on") return `后台保活：手动启动 · ${running}`;
  if (keepalive.reason === "weekly_exhausted" && keepalive.resume_at) {
    return `后台保活：自动暂停到 ${fullTime(keepalive.resume_at)} · ${running}`;
  }
  return `后台保活：自动 · ${running}`;
}

function keepaliveControlsHtml(account) {
  const keepalive = account.keepalive || {};
  if (!keepalive.enabled) return "";
  const disabled = monitorOnly ? "disabled" : "";
  const modes = [
    ["auto", "自动"],
    ["on", "启动"],
    ["off", "停止"],
  ];
  const buttons = modes.map(([mode, label]) => `
    <button class="keepalive-mode ${keepalive.mode === mode ? "active" : ""}" type="button" data-keepalive-id="${escapeHtml(account.id)}" data-keepalive-mode="${mode}" ${disabled}>
      ${label}
    </button>
  `).join("");
  return `
    <div class="keepalive-panel">
      <div class="keepalive-status">${escapeHtml(keepaliveStatusText(keepalive))}</div>
      <div class="keepalive-modes" role="group" aria-label="${escapeHtml(account.label)} 后台保活模式">
        ${buttons}
      </div>
    </div>
  `;
}

function cardHtml(account) {
  const usage = account.usage || {};
  const title = usage.email || usage.name || "未识别账号";
  const active = account.is_active ? "active" : "";
  const error = account.ok ? "" : "error";
  const badge = account.is_active ? "当前使用" : monitorOnly && account.can_switch ? "公网可切换" : account.can_switch ? "可切换" : "默认路径";
  const switchDisabled = !account.ok || !account.can_switch || account.is_active;
  const buttonDisabled = switchDisabled;
  const switchQuotaOk = hasEnoughSwitchQuota(usage);
  const switchButtonClass = account.is_active ? "" : switchQuotaOk ? "primary" : "danger";
  const metaLines = [`计划：${usage.plan || "-"}`];
  if (account.path) {
    metaLines.push(`路径：${account.path}`);
  }
  const metaHtml = metaLines.map(escapeHtml).join("<br>");
  const actionTitle = switchQuotaOk
      ? "5 小时额度和 1 周额度均可用"
      : "5 小时额度或 1 周额度不可用，仍可手动切换";
  const downloadHref = `/api/accounts/${encodeURIComponent(account.id)}/auth.json`;
  const downloadName = `${safeFileBase(account.id)}-auth.json`;
  const uploadButton = account.can_upload
    ? `<button class="button" type="button" data-upload-auth="${escapeHtml(account.id)}">上传认证</button>`
    : "";
  const actionHtml = `
    <div class="card-actions ${account.can_upload ? "has-upload" : ""}">
      <a class="button" href="${downloadHref}" download="${escapeHtml(downloadName)}" data-download-auth="${escapeHtml(account.id)}">下载认证</a>
      ${uploadButton}
      <button class="button ${switchButtonClass}" data-switch="${escapeHtml(account.id)}" ${buttonDisabled ? "disabled" : ""} title="${actionTitle}">
        ${account.is_active ? "正在使用" : "切换到此账号"}
      </button>
    </div>
  `;

  return `
    <article class="card ${active} ${error}">
      <div>
        <div class="card-head">
          <div>
            <h2 class="label">${escapeHtml(account.label)}</h2>
            <p class="email">${account.ok ? escapeHtml(title) : "读取失败"}</p>
          </div>
          <span class="badge ${active}">${badge}</span>
        </div>

        ${account.ok ? `
          <div class="usage">
            ${usageRow(usage.primary)}
            ${usageRow(usage.secondary)}
          </div>
          <p class="meta">${metaHtml}</p>
        ` : `
          <p class="error-text">${escapeHtml(account.error || "未知错误")}</p>
          ${account.path ? `<p class="meta">路径：${escapeHtml(account.path)}</p>` : ""}
        `}
      </div>

      <div class="card-footer">
        ${actionHtml}
        ${keepaliveControlsHtml(account)}
      </div>
    </article>
  `;
}

async function loadAccounts({silent = false} = {}) {
  if (!silent) showNotice("正在刷新所有账号额度...");
  refreshBtn.disabled = true;
  try {
    const res = await fetch("/api/accounts");
    const data = await res.json();
    monitorOnly = Boolean(data.monitor_only);
    document.body.classList.toggle("monitor-only", monitorOnly);
    renderAccounts(data.accounts);
    loadHistory();
    if (!silent) showNotice("额度已刷新", "good");
  } catch (err) {
    showNotice(`刷新失败：${err.message}`, "bad");
  } finally {
    refreshBtn.disabled = false;
  }
}

function preSwitchSyncMessage(result) {
  const sync = result?.pre_switch_sync;
  if (!sync) return "";
  if (sync.changed) {
    return [
      "当前默认认证文件已更新。",
      `已把最新认证覆盖到对应账号池：${sync.synced_to || "未知账号"}`,
      sync.pool_path ? `账号池路径：${sync.pool_path}` : "",
    ].filter(Boolean).join("\n");
  }
  if (sync.synced_to) {
    return [
      "当前认证文件未更新。",
      `默认认证文件和当前使用的账号池认证一致：${sync.synced_to}`,
      sync.pool_path ? `账号池路径：${sync.pool_path}` : "",
    ].filter(Boolean).join("\n");
  }
  return sync.reason || "";
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
        renderAccounts(data.accounts);
        loadHistory();
        const syncMessage = preSwitchSyncMessage(data.result);
        if (syncMessage) {
          showSwitchSyncDialog(syncMessage);
        }
        const syncNotice = syncMessage ? `${syncMessage.split("\n")[0]} ` : "";
        showNotice(`${syncNotice}已切换到 ${data.result.label}，Codex 正在重新启动。备份：${data.result.backup}`, "good");
      } catch (err) {
        showNotice(`切换失败：${err.message}`, "bad");
        btn.disabled = false;
      }
    });
  });
}

function bindKeepaliveButtons() {
  if (monitorOnly) return;
  document.querySelectorAll("[data-keepalive-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-keepalive-id");
      const mode = btn.getAttribute("data-keepalive-mode");
      btn.disabled = true;
      showNotice("正在更新后台保活设置...");
      try {
        const res = await fetch("/api/keepalive", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({id, mode}),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "保活设置更新失败");
        }
        renderAccounts(data.accounts);
        loadHistory();
        showNotice("后台保活设置已更新", "good");
      } catch (err) {
        showNotice(`保活设置更新失败：${err.message}`, "bad");
        btn.disabled = false;
      }
    });
  });
}

function bindDownloadButtons() {
  document.querySelectorAll("[data-download-auth]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      const href = link.getAttribute("href");
      const filename = link.getAttribute("download") || "auth.json";
      if (!href) return;
      showNotice("正在准备认证文件下载...");
      try {
        const res = await fetch(href, {cache: "no-store"});
        if (!res.ok) {
          let message = `HTTP ${res.status}`;
          try {
            const data = await res.json();
            message = data.error || message;
          } catch {
            // Keep the HTTP status when the server returns a non-JSON error page.
          }
          throw new Error(message);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const downloadLink = document.createElement("a");
        downloadLink.href = url;
        downloadLink.download = filename;
        document.body.append(downloadLink);
        downloadLink.click();
        downloadLink.remove();
        URL.revokeObjectURL(url);
        showNotice(`已开始下载 ${filename}`, "good");
      } catch (err) {
        showNotice(`下载失败：${err.message}。如果刚更新过程序，请重启网页服务后重试。`, "bad");
      }
    });
  });
}

function backupSummary(backups) {
  if (!Array.isArray(backups) || !backups.length) return "";
  return `备份：${backups.map((backup) => backup.path).join("；")}`;
}

function uploadConfirmMessage(account, file) {
  return [
    `将把 ${file.name} 上传并覆盖「${account?.label || "目标账号"}」的账号池认证文件。`,
    "如果这个文件来自另一台电脑的“默认配置”，请确认它属于那台电脑当时实际登录的账号。",
    "服务器会先比对文件；相同则不覆盖，不同则先备份目标文件和上传文件再覆盖。",
  ].join("\n\n");
}

function bindUploadButtons() {
  document.querySelectorAll("[data-upload-auth]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-upload-auth");
      const account = latestAccounts.find((item) => item.id === id);
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json,application/json";
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (!file) return;
        if (!window.confirm(uploadConfirmMessage(account, file))) return;

        btn.disabled = true;
        showNotice(`正在上传 ${file.name} 并比对目标认证...`);
        try {
          const res = await fetch(`/api/accounts/${encodeURIComponent(id)}/auth.json`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: file,
          });
          const data = await res.json();
          if (!res.ok || !data.ok) {
            throw new Error(data.error || "上传失败");
          }
          if (Array.isArray(data.accounts)) {
            renderAccounts(data.accounts);
          }
          loadHistory();
          const detail = backupSummary(data.result.backups);
          showNotice(data.result.changed
            ? `已覆盖 ${account?.label || id} 的认证文件。${detail}`
            : `${account?.label || id} 的认证文件没有变化，无需覆盖。`, "good");
        } catch (err) {
          showNotice(`上传失败：${err.message}`, "bad");
          btn.disabled = false;
        }
      }, {once: true});
      input.click();
    });
  });
}

function dateTimeInputValue(timestamp) {
  const date = new Date(timestamp * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function inputTimeSeconds(value) {
  if (!value) return null;
  const timestamp = new Date(value).getTime() / 1000;
  return Number.isFinite(timestamp) ? timestamp : null;
}

function noonTimeSeconds(timestamp) {
  const date = new Date(timestamp * 1000);
  date.setHours(12, 0, 0, 0);
  return date.getTime() / 1000;
}

function accountKey(account) {
  return account.account_id || account.usage_account_id || account.email || account.id;
}

function sampleAccountMap(sample) {
  const byKey = new Map();
  (sample.accounts || []).forEach((account) => {
    const value = numberOrNull(account.used_percent);
    if (value === null || !account.ok) return;
    const key = accountKey(account);
    const existing = byKey.get(key);
    if (!existing || value > existing.value) {
      byKey.set(key, {
        value,
        resetAt: numberOrNull(account.reset_at),
        label: account.label || account.name || account.email || account.id,
      });
    }
  });
  return byKey;
}

function buildUsageTimeline(history) {
  const samples = (history.samples || [])
    .map((sample) => ({
      ...sample,
      timestamp: numberOrNull(sample.timestamp),
    }))
    .filter((sample) => sample.timestamp !== null)
    .sort((a, b) => a.timestamp - b.timestamp);
  const previous = new Map();
  const recentDeltas = [];
  let cumulative = 0;

  return samples.map((sample) => {
    let delta = 0;
    const accounts = sampleAccountMap(sample);
    accounts.forEach((current, key) => {
      const prior = previous.get(key);
      if (prior) {
        const growth = current.value - prior.value;
        if (growth > 0) {
          delta += growth;
        }
      }
      previous.set(key, current);
    });

    cumulative += delta;
    recentDeltas.push({timestamp: sample.timestamp, delta});
    while (recentDeltas.length && sample.timestamp - recentDeltas[0].timestamp > 3600) {
      recentDeltas.shift();
    }

    return {
      timestamp: sample.timestamp,
      cumulative,
      activity: recentDeltas.reduce((sum, item) => sum + item.delta, 0),
      delta,
    };
  });
}

function filterTimeline(points) {
  const start = inputTimeSeconds(historyStartInput.value);
  const end = inputTimeSeconds(historyEndInput.value);
  return points.filter((point) => {
    if (start !== null && point.timestamp < start) return false;
    if (end !== null && point.timestamp > end) return false;
    return true;
  });
}

function rangeCumulativePoints(points) {
  if (!points.length) return [];
  const rangeStart = inputTimeSeconds(historyStartInput.value) || points[0].timestamp;
  let cumulative = 0;
  const result = [{timestamp: rangeStart, value: 0}];
  points.forEach((point) => {
    cumulative += point.delta;
    result.push({timestamp: point.timestamp, value: cumulative});
  });
  return result;
}

function activityPoints(points) {
  return points.map((point) => ({
    timestamp: point.timestamp,
    value: point.activity,
  }));
}

function initializeDateInputs(points) {
  if (!points.length || (historyStartInput.value && historyEndInput.value)) return;
  const latest = points.at(-1).timestamp;
  const defaultStart = noonTimeSeconds(latest);
  historyStartInput.value = dateTimeInputValue(defaultStart);
  historyEndInput.value = dateTimeInputValue(latest);
}

function closestPoint(points, targetTime) {
  return points.reduce((closest, point) => {
    if (!closest) return point;
    return Math.abs(point.timestamp - targetTime) < Math.abs(closest.timestamp - targetTime) ? point : closest;
  }, null);
}

function bindChartHover(svg, points, metrics, options) {
  const hover = svg.querySelector(".chart-hover");
  const vertical = svg.querySelector("[data-hover-vertical]");
  const horizontal = svg.querySelector("[data-hover-horizontal]");
  const dot = svg.querySelector("[data-hover-dot]");
  const label = svg.querySelector("[data-hover-label]");
  const labelTime = svg.querySelector("[data-hover-time]");
  const labelValue = svg.querySelector("[data-hover-value]");
  const labelWidth = 162;
  const labelHeight = 46;

  svg.onpointermove = (event) => {
    const rect = svg.getBoundingClientRect();
    const mouseX = ((event.clientX - rect.left) / rect.width) * metrics.width;
    if (mouseX < metrics.left || mouseX > metrics.width - metrics.right) {
      hover.classList.add("hidden");
      return;
    }

    const ratio = (mouseX - metrics.left) / metrics.plotWidth;
    const targetTime = metrics.minTime + ratio * (metrics.maxTime - metrics.minTime);
    const point = closestPoint(points, targetTime);
    if (!point) return;

    const pointX = metrics.x(point.timestamp);
    const pointY = metrics.y(point.value);
    vertical.setAttribute("x1", pointX);
    vertical.setAttribute("x2", pointX);
    horizontal.setAttribute("y1", pointY);
    horizontal.setAttribute("y2", pointY);
    dot.setAttribute("cx", pointX);
    dot.setAttribute("cy", pointY);
    labelTime.textContent = fullTime(point.timestamp);
    labelValue.textContent = `${options.label || "用量"}：${usedText(point.value)}`;

    const labelX = Math.min(Math.max(pointX + 12, metrics.left), metrics.width - metrics.right - labelWidth);
    const labelY = pointY - labelHeight - 10 < metrics.top ? pointY + 12 : pointY - labelHeight - 10;
    label.setAttribute("transform", `translate(${labelX} ${labelY})`);
    hover.classList.remove("hidden");
  };

  svg.onpointerleave = () => hover.classList.add("hidden");
}

function drawLineChart(svg, emptyEl, points, options) {
  if (!points.length) {
    svg.innerHTML = "";
    svg.onpointermove = null;
    svg.onpointerleave = null;
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  const width = 900;
  const height = options.height;
  const left = 56;
  const right = 22;
  const top = 16;
  const bottom = 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  let minTime = Math.min(...points.map((point) => point.timestamp));
  let maxTime = Math.max(...points.map((point) => point.timestamp));
  if (minTime === maxTime) {
    minTime -= 12 * 3600;
    maxTime += 12 * 3600;
  }

  const maxValue = Math.max(options.minimumMax || 10, ...points.map((point) => point.value));
  const step = maxValue > 1000 ? 500 : maxValue > 300 ? 100 : 25;
  const yMax = Math.max(options.minimumMax || 10, Math.ceil((maxValue * 1.12) / step) * step);
  const x = (timestamp) => left + ((timestamp - minTime) / (maxTime - minTime)) * plotWidth;
  const y = (value) => top + plotHeight - (value / yMax) * plotHeight;
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(yMax * ratio));
  const xTicks = [0, 0.33, 0.66, 1].map((ratio) => minTime + (maxTime - minTime) * ratio);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.timestamp).toFixed(1)} ${y(point.value).toFixed(1)}`)
    .join(" ");
  const last = points.at(-1);

  const grid = [
    ...yTicks.map((tick) => `
      <g class="chart-grid">
        <line x1="${left}" x2="${width - right}" y1="${y(tick)}" y2="${y(tick)}"></line>
        <text x="${left - 10}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>
      </g>
    `),
    ...xTicks.map((tick) => `
      <g class="chart-grid x-grid">
        <line x1="${x(tick)}" x2="${x(tick)}" y1="${top}" y2="${height - bottom}"></line>
        <text x="${x(tick)}" y="${height - 14}" text-anchor="middle">${options.dateAxis ? fullTime(tick) : shortTime(tick)}</text>
      </g>
    `),
  ].join("");

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `
    <rect class="chart-bg" x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}"></rect>
    ${grid}
    <line class="chart-axis" x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}"></line>
    <line class="chart-axis" x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}"></line>
    <path class="chart-line" d="${path}" stroke="${options.color}"></path>
    <circle class="chart-point" cx="${x(last.timestamp)}" cy="${y(last.value)}" r="4" fill="${options.color}"></circle>
    <text class="chart-end-label" x="${width - right - 4}" y="${Math.max(top + 12, y(last.value) - 8)}" text-anchor="end" fill="${options.color}">${escapeHtml(usedText(last.value))}</text>
    <g class="chart-hover hidden">
      <line data-hover-vertical class="chart-crosshair" x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}"></line>
      <line data-hover-horizontal class="chart-crosshair" x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}"></line>
      <circle data-hover-dot class="chart-hover-dot" r="5" fill="${options.color}"></circle>
      <g data-hover-label class="chart-tooltip">
        <rect width="162" height="46" rx="6"></rect>
        <text data-hover-time x="10" y="18"></text>
        <text data-hover-value x="10" y="36"></text>
      </g>
    </g>
    <rect class="chart-hitbox" x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}"></rect>
  `;
  bindChartHover(svg, points, {
    width,
    height,
    left,
    right,
    top,
    bottom,
    plotWidth,
    minTime,
    maxTime,
    x,
    y,
  }, options);
}

function renderHistory(history) {
  latestHistory = history;
  const timeline = buildUsageTimeline(history);
  initializeDateInputs(timeline);
  const filtered = filterTimeline(timeline);
  const latestPoint = timeline.at(-1);
  const shortWindowStart = latestPoint ? latestPoint.timestamp - 6 * 3600 : 0;
  const shortWindow = timeline.filter((point) => point.timestamp >= shortWindowStart);
  const cumulativePoints = rangeCumulativePoints(filtered);
  const recentActivityPoints = activityPoints(shortWindow);
  const latestSample = [...(history.samples || [])].reverse().find((sample) => numberOrNull(sample.timestamp) !== null);

  drawLineChart(cumulativeChartEl, cumulativeEmptyEl, cumulativePoints, {
    color: cumulativeColor,
    dateAxis: true,
    height: 260,
    label: "累计",
    minimumMax: 100,
  });
  drawLineChart(activityChartEl, activityEmptyEl, recentActivityPoints, {
    color: activityColor,
    dateAxis: false,
    height: 220,
    label: "短期",
    minimumMax: 25,
  });

  cumulativeValueEl.textContent = usedText(cumulativePoints.at(-1)?.value);
  activityValueEl.textContent = usedText(recentActivityPoints.at(-1)?.value);
  historyMetaEl.textContent = latestSample
    ? `${timeline.length} 个采样点 · 最近 ${fullTime(latestSample.timestamp)} · 短期为最近 1 小时增量`
    : "等待采样";
}

async function loadHistory() {
  try {
    const res = await fetch("/api/usage-history");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    renderHistory(data);
  } catch (err) {
    historyMetaEl.textContent = `历史读取失败：${err.message}`;
  }
}

refreshBtn.addEventListener("click", () => loadAccounts());
switchSyncCloseBtn?.addEventListener("click", hideSwitchSyncDialog);
switchSyncDialogEl?.addEventListener("click", (event) => {
  if (event.target === switchSyncDialogEl) hideSwitchSyncDialog();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hideSwitchSyncDialog();
});
quotaSortBtn.addEventListener("click", () => {
  quotaSortEnabled = !quotaSortEnabled;
  renderAccounts(latestAccounts);
});
historyStartInput.addEventListener("change", () => latestHistory && renderHistory(latestHistory));
historyEndInput.addEventListener("change", () => latestHistory && renderHistory(latestHistory));
loadAccounts({silent: true}).then(hideNotice);
loadHistory();
setInterval(loadHistory, 30 * 1000);
