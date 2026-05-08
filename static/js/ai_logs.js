const runAiAnalysisBtn = document.getElementById("runAiAnalysisBtn");
const aiLimit = document.getElementById("aiLimit");
const aiSourceFilter = document.getElementById("aiSourceFilter");
const aiMethodCheckboxes = document.querySelectorAll(".ai-method-checkbox");
const aiStatusGroupFilter = document.getElementById("aiStatusGroupFilter");
const aiEndpointFilter = document.getElementById("aiEndpointFilter");
const aiResult = document.getElementById("aiResult");
const aiModeButtons = document.querySelectorAll(".ai-mode-btn");
let selectedResponseMode = "tr";

function t(key, fallback) {
    return (window.i18n && window.i18n[key]) || fallback;
}

async function runAiAnalysis() {
    runAiAnalysisBtn.disabled = true;
    aiResult.textContent = t("ai_logs_loading", "Running analysis, please wait...");

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
                response_mode: selectedResponseMode
            })
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
    aiMethodCheckboxes.forEach((checkbox) => {
        checkbox.disabled = isSecurity;
    });
    aiEndpointFilter.disabled = isSecurity;
}

aiSourceFilter.addEventListener("change", syncFilterAvailability);
syncFilterAvailability();
aiModeButtons.forEach((button) => {
    button.addEventListener("click", () => setResponseMode(button.dataset.mode));
});
runAiAnalysisBtn.addEventListener("click", runAiAnalysis);
