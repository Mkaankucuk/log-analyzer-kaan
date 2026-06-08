(function () {
    const POLL_MS = 1500;

    function t(key, fallback) {
        return (window.i18n && window.i18n[key]) || fallback;
    }

    const activeList = document.getElementById("alarmsActiveList");
    const historyList = document.getElementById("alarmsHistoryList");
    const ackAllBtn = document.getElementById("alarmsAckAllBtn");
    const ackSelectedBtn = document.getElementById("alarmsAckSelectedBtn");
    const selectAllCheckbox = document.getElementById("alarmsSelectAll");
    const sidebarBadge = document.getElementById("sidebarAlarmBadge");
    const mailOutboxEl = document.getElementById("alarmsMailOutbox");
    const mailHintEl = document.getElementById("alarmsMailHint");
    const jobStateEl = document.getElementById("alarmJobState");
    const jobIntervalEl = document.getElementById("alarmJobInterval");
    const jobLastRunEl = document.getElementById("alarmJobLastRun");
    const jobNextRunEl = document.getElementById("alarmJobNextRun");
    const jobRowsEl = document.getElementById("alarmJobRows");
    const jobCreatedEl = document.getElementById("alarmJobCreated");
    const jobRunBtn = document.getElementById("alarmJobRunBtn");
    const jobFeedback = document.getElementById("alarmJobFeedback");

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function severityLabel(sev) {
        if (sev === "critical") return t("alarms_severity_critical", "Critical");
        return t("alarms_severity_warning", "Warning");
    }

    function alarmMessage(alarm) {
        const type = alarm.type || "unknown";
        const key = "alarm_type_" + type;
        let template = t(key, "");
        if (!template) {
            template = t("alarm_type_unknown", "");
        }
        return template
            .replace("{method}", alarm.method || "")
            .replace("{endpoint}", alarm.endpoint || "")
            .replace("{status}", String(alarm.status ?? ""))
            .replace("{latency}", String(alarm.latency_ms ?? ""))
            .replace("{window}", "12");
    }

    function alarmTypeLabel(type) {
        const key = "alarm_label_" + (type || "unknown");
        return t(key, type || "");
    }

    function renderCard(alarm, options) {
        const opts = options || {};
        const card = document.createElement("article");
        card.className =
            "alarm-card alarm-severity-" + (alarm.severity || "warning");
        if (alarm.acknowledged) card.classList.add("is-acknowledged");

        const checkboxHtml = opts.showCheckbox
            ? '<label class="alarm-select-label">' +
              '<input type="checkbox" class="alarm-select-cb" value="' +
              escapeHtml(alarm.id) +
              '">' +
              "</label>"
            : "";

        const ackBtn =
            opts.showAckBtn && !opts.showCheckbox
                ? '<button type="button" class="alarm-ack-btn" data-alarm-id="' +
                  escapeHtml(alarm.id) +
                  '">' +
                  escapeHtml(t("alarms_ack", "Ack")) +
                  "</button>"
                : "";

        card.innerHTML =
            '<div class="alarm-card-head">' +
            checkboxHtml +
            '<span class="alarm-severity-pill">' +
            escapeHtml(severityLabel(alarm.severity)) +
            "</span>" +
            "<time>" +
            escapeHtml(alarm.time || "") +
            "</time>" +
            ackBtn +
            "</div>" +
            '<span class="alarm-type-pill">' +
            escapeHtml(alarmTypeLabel(alarm.type)) +
            "</span>" +
            '<p class="alarm-message">' +
            escapeHtml(alarmMessage(alarm)) +
            "</p>" +
            '<p class="alarm-meta"><code>' +
            escapeHtml((alarm.method || "") + " " + (alarm.endpoint || "")) +
            "</code> · " +
            escapeHtml(t("alarms_meta_status", "Status")) +
            " " +
            escapeHtml(String(alarm.status ?? "")) +
            " · " +
            escapeHtml(t("alarms_meta_latency", "Latency")) +
            " " +
            escapeHtml(String(alarm.latency_ms ?? "")) +
            " ms</p>";

        return card;
    }

    function getSelectedAlarmIds() {
        const ids = [];
        activeList.querySelectorAll(".alarm-select-cb:checked").forEach(function (cb) {
            if (cb.value) ids.push(cb.value);
        });
        return ids;
    }

    function syncSelectAllState() {
        if (!selectAllCheckbox) return;
        const boxes = activeList.querySelectorAll(".alarm-select-cb");
        if (!boxes.length) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.disabled = true;
            return;
        }
        selectAllCheckbox.disabled = false;
        const checked = activeList.querySelectorAll(".alarm-select-cb:checked").length;
        selectAllCheckbox.checked = checked === boxes.length;
        selectAllCheckbox.indeterminate = checked > 0 && checked < boxes.length;
    }

    function renderMailOutbox(mails) {
        if (!mailOutboxEl) return;

        const list = mails || [];
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

    async function loadMailOutbox() {
        try {
            const [outRes, snapRes] = await Promise.all([
                fetch("/api/live/mail-outbox", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                }),
                fetch("/api/live/snapshot", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                }),
            ]);
            if (outRes.ok) {
                const data = await outRes.json();
                renderMailOutbox(data.mails || []);
            }
            if (snapRes.ok) {
                const snap = await snapRes.json();
                updateMailHint(snap.mail_status);
            }
        } catch (_) {
            /* ignore */
        }
    }

    function renderJobStatus(job) {
        if (!job) return;
        let stateLabel = job.enabled
            ? t("alarms_job_enabled", "")
            : t("alarms_job_disabled", "");
        if (job.running) {
            stateLabel += " · " + t("alarms_job_running", "");
        } else {
            stateLabel += " · " + t("alarms_job_idle", "");
        }
        if (jobStateEl) jobStateEl.textContent = stateLabel;
        if (jobIntervalEl) {
            jobIntervalEl.textContent =
                String(job.scan_interval_seconds || "") +
                " " +
                t("mail_admin_seconds", "s");
        }
        if (jobLastRunEl) {
            jobLastRunEl.textContent = job.last_run_label || "—";
        }
        if (jobNextRunEl) {
            const next = job.next_run_label || "—";
            const sec = job.seconds_until_next;
            jobNextRunEl.textContent =
                typeof sec === "number" && sec > 0
                    ? next + " (" + sec + "s)"
                    : next;
        }
        if (jobRowsEl) {
            jobRowsEl.textContent = String(job.rows_scanned ?? "—");
        }
        if (jobCreatedEl) {
            jobCreatedEl.textContent =
                String(job.alarms_created_last_run ?? "0") +
                " / " +
                String(job.run_count ?? "0") +
                " " +
                t("alarms_job_runs", "");
        }
        if (job.last_error && jobFeedback) {
            jobFeedback.hidden = false;
            jobFeedback.classList.add("is-error");
            jobFeedback.textContent =
                t("alarms_job_error", "") + ": " + job.last_error;
        }
    }

    async function loadJobStatus() {
        try {
            const res = await fetch("/api/live/alarm-job", {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) return;
            const data = await res.json();
            renderJobStatus(data.job);
        } catch (_) {
            /* ignore */
        }
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

    function bindAckButtons(root) {
        root.querySelectorAll(".alarm-ack-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const id = btn.getAttribute("data-alarm-id");
                if (id) acknowledge([id]);
            });
        });
    }

    function bindCheckboxes(root) {
        root.querySelectorAll(".alarm-select-cb").forEach(function (cb) {
            cb.addEventListener("change", syncSelectAllState);
        });
    }

    async function acknowledge(ids) {
        if (!ids.length) return;
        try {
            await fetch("/api/live/alarms/ack", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify({ alarm_ids: ids }),
            });
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            }
            refresh();
        } catch (_) {
            /* ignore */
        }
    }

    async function refresh() {
        try {
            const [activeRes, historyRes] = await Promise.all([
                fetch("/api/live/alarms", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                }),
                fetch("/api/live/alarms?include_acknowledged=1", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                }),
            ]);

            if (!activeRes.ok || !historyRes.ok) return;

            const activeData = await activeRes.json();
            const historyData = await historyRes.json();

            const active = (activeData.alarms || []).filter(function (a) {
                return !a.acknowledged;
            });
            const history = historyData.alarms || [];

            updateSidebarBadge(active.length);

            activeList.innerHTML = "";
            if (!active.length) {
                const p = document.createElement("p");
                p.className = "alarms-empty-msg";
                p.textContent = t("alarms_empty", "");
                activeList.appendChild(p);
            } else {
                active.forEach(function (al) {
                    activeList.appendChild(
                        renderCard(al, { showCheckbox: true })
                    );
                });
                bindCheckboxes(activeList);
            }
            syncSelectAllState();

            historyList.innerHTML = "";
            history.slice(0, 30).forEach(function (al) {
                historyList.appendChild(
                    renderCard(al, { showAckBtn: !al.acknowledged })
                );
            });
            bindAckButtons(historyList);
        } catch (_) {
            /* ignore */
        }
    }

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener("change", function () {
            const checked = selectAllCheckbox.checked;
            activeList.querySelectorAll(".alarm-select-cb").forEach(function (cb) {
                cb.checked = checked;
            });
            selectAllCheckbox.indeterminate = false;
        });
    }

    if (ackSelectedBtn) {
        ackSelectedBtn.addEventListener("click", function () {
            const ids = getSelectedAlarmIds();
            if (ids.length) acknowledge(ids);
        });
    }

    if (ackAllBtn) {
        ackAllBtn.addEventListener("click", function () {
            const ids = [];
            activeList.querySelectorAll(".alarm-select-cb").forEach(function (cb) {
                if (cb.value) ids.push(cb.value);
            });
            if (ids.length) acknowledge(ids);
        });
    }

    if (jobRunBtn) {
        jobRunBtn.addEventListener("click", async function () {
            jobRunBtn.disabled = true;
            try {
                const res = await fetch("/api/live/alarm-job/run", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    if (jobFeedback) {
                        jobFeedback.hidden = false;
                        jobFeedback.classList.add("is-error");
                        jobFeedback.textContent = t("alarms_job_run_fail", "");
                    }
                    return;
                }
                renderJobStatus(data.job);
                if (jobFeedback) {
                    jobFeedback.hidden = false;
                    jobFeedback.classList.remove("is-error");
                    jobFeedback.classList.add("is-ok");
                    jobFeedback.textContent = t("alarms_job_run_ok", "");
                }
                refresh();
                loadMailOutbox();
            } catch (_) {
                if (jobFeedback) {
                    jobFeedback.hidden = false;
                    jobFeedback.classList.add("is-error");
                    jobFeedback.textContent = t("alarms_job_run_fail", "");
                }
            } finally {
                jobRunBtn.disabled = false;
            }
        });
    }

    refresh();
    loadMailOutbox();
    loadJobStatus();
    setInterval(refresh, POLL_MS);
    setInterval(loadMailOutbox, POLL_MS);
    setInterval(loadJobStatus, POLL_MS);
})();
