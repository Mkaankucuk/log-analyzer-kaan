(function () {
    const POLL_MS = 2000;
    const CHART_EVERY_N_POLLS = 3;
    const MAX_ROWS = 40;

    function t(key, fallback) {
        return (window.i18n && window.i18n[key]) || fallback;
    }

    const feedBody = document.getElementById("liveFeedBody");
    const statEvents = document.getElementById("liveStatEvents");
    const statAnomalies = document.getElementById("liveStatAnomalies");
    const statAlarms = document.getElementById("liveStatAlarms");
    const connectionBadge = document.getElementById("liveConnectionBadge");
    const alarmToast = document.getElementById("liveAlarmToast");
    const sidebarBadge = document.getElementById("sidebarAlarmBadge");
    const mailOutboxEl = document.getElementById("liveMailOutbox");
    const mailHintEl = document.getElementById("liveMailHint");

    let sinceEventId = null;
    let sinceAlarmId = null;
    let knownEventIds = new Set();
    let toastTimer = null;
    let chartsInitialized = false;
    let pollCount = 0;
    let lastMailOutboxKey = "";

    const plotLayout = {
        margin: { t: 24, r: 16, b: 48, l: 48 },
        template: "plotly_white",
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
    };

    function renderCharts(charts) {
        if (!charts || !window.Plotly) return;

        const lat = charts.latency_chart || { x: [], y: [] };
        const status = charts.status_chart || { x: [], y: [] };
        const method = charts.method_chart || { x: [], y: [] };
        const stream = charts.stream_chart || { x: [], errors: [], ok: [] };
        const throughput = charts.throughput_chart || { x: [], y: [] };

        const latencyTrace = {
            x: lat.x,
            y: lat.y,
            type: "scatter",
            mode: "lines+markers",
            name: t("js_live_latency", "Latency"),
            line: { color: "#2563eb", width: 2 },
            marker: { size: 5 },
        };

        const statusTrace = {
            x: status.x,
            y: status.y,
            type: "bar",
            name: t("js_live_status_code", "Status"),
            marker: { color: "#6366f1" },
        };

        const methodTrace = {
            x: method.x,
            y: method.y,
            type: "bar",
            name: t("js_live_method", "Method"),
            marker: { color: "#0ea5e9" },
        };

        const streamErrorTrace = {
            x: stream.x,
            y: stream.errors || [],
            type: "bar",
            name: t("js_live_error", "Error"),
            marker: { color: "#dc2626" },
        };

        const streamOkTrace = {
            x: stream.x,
            y: stream.ok || [],
            type: "bar",
            name: t("js_live_ok", "OK"),
            marker: { color: "#16a34a" },
        };

        const throughputTrace = {
            x: throughput.x,
            y: throughput.y,
            type: "scatter",
            mode: "lines+markers",
            fill: "tozeroy",
            name: t("js_live_throughput", "Requests"),
            line: { color: "#7c3aed", width: 2 },
        };

        const plot = chartsInitialized ? Plotly.react : Plotly.newPlot;
        chartsInitialized = true;

        plot(
            "liveLatencyChart",
            [latencyTrace],
            {
                ...plotLayout,
                xaxis: { title: t("js_live_time", "Time") },
                yaxis: { title: t("js_live_latency", "Latency (ms)") },
            }
        );

        plot(
            "liveStatusChart",
            [statusTrace],
            {
                ...plotLayout,
                xaxis: { title: t("js_live_status_code", "Status code") },
                yaxis: { title: t("js_live_count", "Count") },
            }
        );

        plot(
            "liveMethodChart",
            [methodTrace],
            {
                ...plotLayout,
                xaxis: { title: t("js_live_method", "Method") },
                yaxis: { title: t("js_live_count", "Count") },
            }
        );

        plot(
            "liveStreamChart",
            [streamOkTrace, streamErrorTrace],
            {
                ...plotLayout,
                barmode: "stack",
                xaxis: { title: t("js_live_time", "Time") },
                yaxis: { title: t("js_live_count", "Count"), dtick: 1 },
            }
        );

        plot(
            "liveThroughputChart",
            [throughputTrace],
            {
                ...plotLayout,
                xaxis: { title: t("js_live_time", "Time") },
                yaxis: { title: t("js_live_throughput", "Requests") },
            }
        );
    }

    function levelClass(level) {
        if (level === "error") return "live-level-error";
        if (level === "warn") return "live-level-warn";
        return "live-level-info";
    }

    function statusClass(status) {
        const s = Number(status);
        if (s >= 500) return "live-status-5xx";
        if (s >= 400) return "live-status-4xx";
        return "live-status-ok";
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function buildRow(ev) {
        const tr = document.createElement("tr");
        if (ev.anomaly) tr.classList.add("live-row-anomaly");
        const badge = ev.anomaly
            ? '<span class="live-anomaly-pill">' +
              escapeHtml(t("live_anomaly_badge", "Anomaly")) +
              "</span> "
            : "";
        tr.innerHTML =
            "<td>" +
            escapeHtml(ev.time || "") +
            "</td>" +
            "<td><code>" +
            escapeHtml(ev.method || "") +
            "</code></td>" +
            "<td>" +
            escapeHtml(ev.endpoint || "") +
            "</td>" +
            "<td class=\"" +
            statusClass(ev.status) +
            "\">" +
            escapeHtml(String(ev.status ?? "")) +
            "</td>" +
            "<td>" +
            escapeHtml(String(ev.latency_ms ?? "")) +
            "</td>" +
            "<td class=\"" +
            levelClass(ev.level) +
            "\">" +
            badge +
            escapeHtml(ev.level || "") +
            "</td>";
        return tr;
    }

    function prependEvents(events) {
        if (!events || !events.length) return;

        const empty = feedBody.querySelector(".live-empty-row");
        if (empty) empty.remove();

        const frag = document.createDocumentFragment();
        events.forEach(function (ev) {
            if (knownEventIds.has(ev.id)) return;
            knownEventIds.add(ev.id);
            frag.appendChild(buildRow(ev));
        });
        feedBody.insertBefore(frag, feedBody.firstChild);

        while (feedBody.rows.length > MAX_ROWS) {
            feedBody.removeChild(feedBody.lastElementChild);
        }

        if (knownEventIds.size > MAX_ROWS * 3) {
            knownEventIds = new Set();
        }
    }

    function alarmMessage(alarm) {
        const type = alarm.type || "unknown";
        const key = "alarm_type_" + type;
        let template = t(key, "");
        if (!template) template = t("alarm_type_unknown", "");
        return template
            .replace("{method}", alarm.method || "")
            .replace("{endpoint}", alarm.endpoint || "")
            .replace("{status}", String(alarm.status ?? ""))
            .replace("{latency}", String(alarm.latency_ms ?? ""))
            .replace("{window}", "12");
    }

    function showToast(alarms) {
        if (!alarmToast || !alarms.length) return;
        const msg = alarmMessage(alarms[0]);
        alarmToast.textContent = t("live_new_alarm_toast", "").replace(
            "{message}",
            msg
        );
        alarmToast.hidden = false;
        alarmToast.classList.add("is-visible");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            alarmToast.classList.remove("is-visible");
            alarmToast.hidden = true;
        }, 5000);
    }

    function updateSidebarBadge(count) {
        if (!sidebarBadge) return;
        if (count > 0) {
            sidebarBadge.textContent = count > 99 ? "99+" : String(count);
            sidebarBadge.hidden = false;
        } else {
            sidebarBadge.hidden = true;
        }
    }

    function updateMailHint(status) {
        if (!mailHintEl || !status) return;
        if (status.smtp_ready) {
            let hint = t("live_mail_active_note", "").replace(
                "{email}",
                status.recipient || ""
            );
            if (status.last_error) {
                hint +=
                    " " +
                    t("live_mail_error_hint", "").replace(
                        "{error}",
                        status.last_error
                    );
            }
            mailHintEl.textContent = hint;
            mailHintEl.classList.add("is-smtp-active");
        } else {
            mailHintEl.textContent = t("live_mail_preview_note", "");
            mailHintEl.classList.remove("is-smtp-active");
        }
    }

    function renderMailOutbox(mails) {
        if (!mailOutboxEl) return;

        const list = mails || [];
        const key = list.map(function (m) { return m.id; }).join(",");
        if (key === lastMailOutboxKey) return;
        lastMailOutboxKey = key;

        mailOutboxEl.innerHTML = "";
        if (!list.length) {
            const empty = document.createElement("p");
            empty.className = "live-mail-empty";
            empty.textContent = t("live_mail_outbox_empty", "");
            mailOutboxEl.appendChild(empty);
            return;
        }

        list.forEach(function (mail) {
            const card = document.createElement("article");
            card.className = "live-mail-card";
            let badge = t("live_mail_preview_badge", "");
            if (mail.sent_smtp) {
                badge = t("live_mail_sent_badge", "");
            } else if (mail.smtp_error) {
                badge = t("live_mail_failed_badge", "");
            }
            card.innerHTML =
                '<div class="live-mail-card-head">' +
                "<strong>" + escapeHtml(mail.subject || "") + "</strong>" +
                '<span class="live-mail-badge">' + escapeHtml(badge) + "</span>" +
                "</div>" +
                "<time>" + escapeHtml(mail.time || "") + "</time>" +
                '<pre class="live-mail-body">' + escapeHtml(mail.body || "") + "</pre>" +
                (mail.smtp_error
                    ? '<p class="live-mail-error">' +
                      escapeHtml(mail.smtp_error) +
                      "</p>"
                    : "");
            mailOutboxEl.appendChild(card);
        });
    }

    function setConnected(ok) {
        if (!connectionBadge) return;
        connectionBadge.textContent = ok
            ? t("live_status_live", "Live")
            : t("live_status_paused", "Disconnected");
        connectionBadge.classList.toggle("is-live", ok);
        connectionBadge.classList.toggle("is-offline", !ok);
    }

    async function poll() {
        try {
            const params = new URLSearchParams();
            if (sinceEventId) params.set("since_event_id", sinceEventId);
            if (sinceAlarmId) params.set("since_alarm_id", sinceAlarmId);

            const res = await fetch(
                "/api/live/snapshot?" + params.toString(),
                { credentials: "same-origin", headers: { Accept: "application/json" } }
            );

            if (!res.ok) {
                setConnected(false);
                return;
            }

            const data = await res.json();
            if (!data.ok) {
                setConnected(false);
                return;
            }

            setConnected(true);

            if (data.stats) {
                statEvents.textContent = String(data.stats.buffer_size ?? 0);
                statAnomalies.textContent = String(data.stats.recent_anomalies ?? 0);
                statAlarms.textContent = String(data.stats.active_alarms ?? 0);
                updateSidebarBadge(data.stats.active_alarms ?? 0);
                if (data.stats.last_event_id) sinceEventId = data.stats.last_event_id;
                if (data.stats.last_alarm_id) sinceAlarmId = data.stats.last_alarm_id;
            }

            prependEvents(data.events || []);
            pollCount += 1;
            if (pollCount === 1 || pollCount % CHART_EVERY_N_POLLS === 0) {
                renderCharts(data.charts);
            }
            updateMailHint(data.mail_status);
            renderMailOutbox(data.mail_outbox);
            if (data.alarms && data.alarms.length) {
                showToast(data.alarms);
            }
        } catch (_) {
            setConnected(false);
        }
    }

    poll();
    setInterval(poll, POLL_MS);
})();
