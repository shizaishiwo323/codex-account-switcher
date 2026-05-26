const accountsEl = document.querySelector("#accounts");
const refreshBtn = document.querySelector("#refreshBtn");
const noticeEl = document.querySelector("#notice");
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

function cardHtml(account) {
  const usage = account.usage || {};
  const title = usage.email || usage.name || "未识别账号";
  const active = account.is_active ? "active" : "";
  const error = account.ok ? "" : "error";
  const badge = account.is_active ? "当前使用" : monitorOnly ? "只读监控" : account.can_switch ? "可切换" : "默认路径";
  const switchDisabled = !account.ok || !account.can_switch || account.is_active;
  const buttonDisabled = monitorOnly || switchDisabled;
  const metaLines = [`计划：${usage.plan || "-"}`];
  if (account.path) {
    metaLines.push(`路径：${account.path}`);
  }
  const metaHtml = metaLines.map(escapeHtml).join("<br>");
  const actionTitle = monitorOnly ? "公网只读监控不能切换账号" : "";
  const downloadHref = `/api/accounts/${encodeURIComponent(account.id)}/auth.json`;
  const downloadName = `${safeFileBase(account.id)}-auth.json`;
  const actionHtml = `
    <div class="card-actions">
      <a class="button" href="${downloadHref}" download="${escapeHtml(downloadName)}" data-download-auth="${escapeHtml(account.id)}">下载认证</a>
      <button class="button ${account.is_active ? "" : "primary"}" data-switch="${escapeHtml(account.id)}" ${buttonDisabled ? "disabled" : ""} title="${actionTitle}">
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

      ${actionHtml}
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
    accountsEl.innerHTML = data.accounts.map(cardHtml).join("");
    bindDownloadButtons();
    bindSwitchButtons();
    loadHistory();
    if (!silent) showNotice("额度已刷新", "good");
  } catch (err) {
    showNotice(`刷新失败：${err.message}`, "bad");
  } finally {
    refreshBtn.disabled = false;
  }
}

function bindSwitchButtons() {
  if (monitorOnly) return;
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
        bindDownloadButtons();
        bindSwitchButtons();
        loadHistory();
        showNotice(`已切换到 ${data.result.label}，Codex 正在重新启动。备份：${data.result.backup}`, "good");
      } catch (err) {
        showNotice(`切换失败：${err.message}`, "bad");
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
historyStartInput.addEventListener("change", () => latestHistory && renderHistory(latestHistory));
historyEndInput.addEventListener("change", () => latestHistory && renderHistory(latestHistory));
loadAccounts({silent: true}).then(hideNotice);
loadHistory();
setInterval(loadHistory, 30 * 1000);
