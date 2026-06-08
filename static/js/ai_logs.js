const runAiAnalysisBtn = document.getElementById("runAiAnalysisBtn");
const aiLimit = document.getElementById("aiLimit");
const aiLimitLabel = document.getElementById("aiLimitLabel");
const aiSourceFilter = document.getElementById("aiSourceFilter");
const aiDbOnlyFilters = document.querySelector(".ai-db-only-filters");
const aiMethodCheckboxes = document.querySelectorAll(".ai-method-checkbox");
const aiStatusGroupFilter = document.getElementById("aiStatusGroupFilter");
const aiEndpointFilter = document.getElementById("aiEndpointFilter");
const aiResult = document.getElementById("aiResult");
const aiModeButtons = document.querySelectorAll(".ai-mode-btn");
const aiFileSourcePanel = document.getElementById("aiFileSourcePanel");
const aiFileDropZone = document.getElementById("aiFileDropZone");
const aiFileInput = document.getElementById("aiFileInput");
const aiFileBrowse = document.getElementById("aiFileBrowse");
const aiFileMeta = document.getElementById("aiFileMeta");
const aiFileTempStatus = document.getElementById("aiFileTempStatus");
let selectedResponseMode = "tr";
let analysisTimerId = null;

function t(key, fallback) {
    return (window.i18n && window.i18n[key]) || fallback;
}

function truncateName(name, maxLen) {
    if (!name || name.length <= maxLen) return name || "";
    return name.slice(0, maxLen) + "…";
}

function setDragOver(on) {
    aiFileDropZone.classList.toggle("is-dragover", on);
}

async function saveAiTempFile(file) {
    aiFileTempStatus.textContent = t("file_upload_temp_saving", "");
    aiFileTempStatus.style.color = "";
    const fd = new FormData();
    fd.append("file", file);
    try {
        const res = await fetch("/dashboard/file-upload/temp", {
            method: "POST",
            body: fd,
            credentials: "same-origin",
        });

        if (res.status === 413) {
            aiFileTempStatus.textContent = t("file_upload_error_size", "");
            aiFileTempStatus.style.color = "#b45309";
            return false;
        }

        let data = null;
        try {
            data = await res.json();
        } catch (_) {
            data = null;
        }

        if (!data || !data.ok) {
            aiFileTempStatus.textContent = t("file_upload_temp_fail", "");
            aiFileTempStatus.style.color = "#b45309";
            return false;
        }

        const label = t("file_upload_temp_saved", "").replace(
            "{name}",
            truncateName(data.stored_name || "", 48)
        );
        aiFileTempStatus.textContent = label;
        aiFileTempStatus.style.color = "#15803d";
        return true;
    } catch (_) {
        aiFileTempStatus.textContent = t("file_upload_temp_fail", "");
        aiFileTempStatus.style.color = "#b45309";
        return false;
    }
}

function formatBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
}

const MAX_FILE_BYTES = 15 * 1024 * 1024;

async function loadSessionTempFile() {
    if (!aiFileMeta || !aiFileTempStatus) return;

    try {
        const res = await fetch("/dashboard/file-upload/temp", {
            method: "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        });

        if (!res.ok) return;

        let data = null;
        try {
            data = await res.json();
        } catch (_) {
            return;
        }

        if (!data || !data.ok || !data.has_file) return;

        const displayName = data.display_name || data.stored_name || "";
        aiFileMeta.textContent =
            displayName + " · " + formatBytes(data.size_bytes || 0);
        aiFileTempStatus.textContent = t("ai_logs_session_file_ready", "").replace(
            "{name}",
            truncateName(displayName, 48)
        );
        aiFileTempStatus.style.color = "#15803d";
    } catch (_) {
        /* ignore */
    }
}

function handleAiFileSelected(file) {
    if (!file) return;

    if (file.size > MAX_FILE_BYTES) {
        aiFileMeta.textContent = t("file_upload_error_size", "");
        aiFileTempStatus.textContent = "";
        return;
    }

    aiFileMeta.textContent = file.name + " · " + formatBytes(file.size);
    saveAiTempFile(file);
}

function startAnalysisTimer() {
    const started = Date.now();
    const base = t("ai_logs_loading", "Running analysis, please wait...");
    aiResult.textContent = base;
    if (analysisTimerId) clearInterval(analysisTimerId);
    analysisTimerId = setInterval(function () {
        const sec = Math.floor((Date.now() - started) / 1000);
        aiResult.textContent = base + " (" + sec + "s)";
    }, 1000);
}

function stopAnalysisTimer() {
    if (analysisTimerId) {
        clearInterval(analysisTimerId);
        analysisTimerId = null;
    }
}

async function runAiAnalysis() {
    runAiAnalysisBtn.disabled = true;
    startAnalysisTimer();

    try {
        const selectedMethods = Array.from(aiMethodCheckboxes)
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => checkbox.value);
        const response = await fetch("/api/ai-log-analysis", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source: aiSourceFilter.value,
                limit: Number(aiLimit.value),
                methods: selectedMethods,
                status_group: aiStatusGroupFilter.value || null,
                endpoint: aiEndpointFilter.value || "all",
                response_mode: selectedResponseMode,
            }),
        });

        const data = await response.json();
        if (!response.ok || !data.ok) {
            aiResult.textContent = data.message || "AI analysis failed.";
            return;
        }

        aiResult.textContent = data.message || "-";
    } catch (error) {
        aiResult.textContent = `AI analysis failed: ${error}`;
    } finally {
        stopAnalysisTimer();
        runAiAnalysisBtn.disabled = false;
    }
}

function setResponseMode(mode) {
    selectedResponseMode = mode === "en" ? "en" : "tr";
    aiModeButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === selectedResponseMode);
    });
}

function syncFilterAvailability() {
    const isSecurity = aiSourceFilter.value === "security";
    const isFile = aiSourceFilter.value === "file";

    if (aiDbOnlyFilters) {
        aiDbOnlyFilters.classList.toggle("is-collapsed", isFile);
    }

    if (aiFileSourcePanel) {
        aiFileSourcePanel.hidden = !isFile;
    }

    if (isFile) {
        loadSessionTempFile();
    }

    if (aiLimitLabel) {
        aiLimitLabel.textContent = isFile
            ? t("ai_logs_limit_label_file", t("ai_logs_limit_label", ""))
            : t("ai_logs_limit_label", "");
    }

    aiMethodCheckboxes.forEach((checkbox) => {
        checkbox.disabled = isSecurity || isFile;
    });
    aiEndpointFilter.disabled = isSecurity || isFile;
    aiStatusGroupFilter.disabled = isFile;
}

aiSourceFilter.addEventListener("change", syncFilterAvailability);
syncFilterAvailability();

aiModeButtons.forEach((button) => {
    button.addEventListener("click", () => setResponseMode(button.dataset.mode));
});
runAiAnalysisBtn.addEventListener("click", runAiAnalysis);

if (aiFileDropZone && aiFileInput && aiFileBrowse) {
    aiFileDropZone.addEventListener("click", function (e) {
        if (e.target === aiFileBrowse || aiFileBrowse.contains(e.target)) return;
        aiFileInput.click();
    });

    aiFileBrowse.addEventListener("click", function (e) {
        e.stopPropagation();
        aiFileInput.click();
    });

    aiFileInput.addEventListener("change", function () {
        const f = aiFileInput.files && aiFileInput.files[0];
        handleAiFileSelected(f);
    });

    ["dragenter", "dragover"].forEach(function (ev) {
        aiFileDropZone.addEventListener(ev, function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
            setDragOver(true);
        });
    });

    aiFileDropZone.addEventListener("dragleave", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const related = e.relatedTarget;
        if (related && aiFileDropZone.contains(related)) return;
        setDragOver(false);
    });

    aiFileDropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        setDragOver(false);
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) handleAiFileSelected(f);
    });
}
