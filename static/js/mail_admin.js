(function () {
    function t(key, fallback) {
        return (window.i18n && window.i18n[key]) || fallback;
    }

    const form = document.getElementById("mailAdminForm");
    const feedback = document.getElementById("mailAdminFeedback");
    const testBtn = document.getElementById("mailTestBtn");
    const smtpStatus = document.getElementById("mailAdminSmtpStatus");
    const cooldownDisplay = document.getElementById("mailAdminCooldownDisplay");
    const scanDisplay = document.getElementById("mailAdminScanDisplay");

    function showFeedback(msg, ok) {
        if (!feedback) return;
        feedback.textContent = msg;
        feedback.hidden = false;
        feedback.classList.toggle("is-ok", ok);
        feedback.classList.toggle("is-error", !ok);
    }

    function collectSettings() {
        return {
            mail_enabled: document.getElementById("mailEnabled").checked,
            job_enabled: document.getElementById("jobEnabled").checked,
            scan_interval_seconds: Number(document.getElementById("scanInterval").value),
            cooldown_seconds: Number(document.getElementById("mailCooldown").value),
            mail_to: document.getElementById("mailTo").value.trim(),
            send_major_only: document.getElementById("sendMajorOnly").checked,
            include_recommendations: document.getElementById("includeRecs").checked,
            include_buffer_stats: document.getElementById("includeBuffer").checked,
        };
    }

    function updateStatusDisplay(status) {
        if (!status) return;
        if (smtpStatus) {
            smtpStatus.textContent = status.smtp_ready
                ? t("mail_admin_smtp_ok", "")
                : t("mail_admin_smtp_off", "");
        }
        if (cooldownDisplay && status.cooldown_seconds) {
            cooldownDisplay.textContent =
                String(status.cooldown_seconds) + " " + t("mail_admin_seconds", "");
        }
    }

    function updateSettingsDisplay(settings) {
        if (!settings) return;
        if (scanDisplay && settings.scan_interval_seconds) {
            scanDisplay.textContent =
                String(settings.scan_interval_seconds) + " " + t("mail_admin_seconds", "");
        }
    }

    if (form) {
        form.addEventListener("submit", async function (e) {
            e.preventDefault();
            try {
                const res = await fetch("/api/mail-admin/settings", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify(collectSettings()),
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    showFeedback(t("mail_admin_save_fail", ""), false);
                    return;
                }
                updateStatusDisplay(data.status);
                updateSettingsDisplay(data.settings);
                showFeedback(t("mail_admin_save_ok", ""), true);
            } catch (_) {
                showFeedback(t("mail_admin_save_fail", ""), false);
            }
        });
    }

    if (testBtn) {
        testBtn.addEventListener("click", async function () {
            try {
                const saveRes = await fetch("/api/mail-admin/settings", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify(collectSettings()),
                });
                if (!saveRes.ok) {
                    showFeedback(t("mail_admin_test_fail", ""), false);
                    return;
                }
                const res = await fetch("/api/mail-admin/test", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    showFeedback(t("mail_admin_test_fail", ""), false);
                    return;
                }
                showFeedback(t("mail_admin_test_ok", ""), true);
            } catch (_) {
                showFeedback(t("mail_admin_test_fail", ""), false);
            }
        });
    }
})();
