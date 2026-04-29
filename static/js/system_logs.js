async function updateDashboard() {
    const t = window.i18n || {};
    try {
        const response = await fetch("/metrics");
        if (!response.ok) {
            return;
        }

        const data = await response.json();

        document.getElementById("total-logs").textContent = data.total_logs;
        document.getElementById("error-logs").textContent = data.error_logs;
        document.getElementById("warning-logs").textContent = data.warning_logs;
        document.getElementById("cpu-usage").textContent = `%${data.cpu_usage}`;
        document.getElementById("memory-usage").textContent = `%${data.memory_usage}`;

        document.getElementById("cpu-card").className = `card ${data.cpu_class}`;
        document.getElementById("memory-card").className = `card ${data.memory_class}`;

        const processBody = document.getElementById("process-body");
        processBody.innerHTML = "";

        data.top_processes.forEach((proc) => {
            processBody.innerHTML += `
                <tr>
                    <td>${proc.name}</td>
                    <td>${proc.cpu}</td>
                    <td>${proc.memory}</td>
                </tr>
            `;
        });
    } catch (error) {
        console.log(t.js_system_update_error, error);
    }
}

setInterval(updateDashboard, 5000);
