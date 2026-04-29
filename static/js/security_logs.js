function drawStatusChart(data) {
    const t = window.i18n || {};
    Plotly.newPlot(
        "statusChart",
        [
            {
                x: data.x,
                y: data.y,
                type: "bar",
                marker: { color: "#1f4b99" },
                name: t.js_status_code
            }
        ],
        {
            title: t.js_status_code_distribution,
            xaxis: { title: t.js_status_code },
            yaxis: { title: t.js_count }
        },
        { responsive: true }
    );
}

function drawErrorTypeChart(data) {
    const t = window.i18n || {};
    const colors = ["#163b65", "#245c93", "#2f7f8f", "#4b5d9a", "#3f4a56"];

    Plotly.newPlot(
        "errorTypeChart",
        [
            {
                x: data.x,
                y: data.y,
                type: "bar",
                marker: {
                    color: colors.slice(0, data.x.length)
                },
                name: t.js_error_type
            }
        ],
        {
            title: t.js_error_type_distribution,
            xaxis: { title: t.js_error_type },
            yaxis: { title: t.js_count }
        },
        { responsive: true }
    );
}

function drawLatencyChart(data) {
    const t = window.i18n || {};
    Plotly.newPlot(
        "latencyChart",
        [
            {
                x: data.x,
                y: data.y,
                type: "scatter",
                mode: "lines+markers",
                line: {
                    color: "#245c93",
                    width: 2
                },
                marker: {
                    color: "#245c93",
                    size: 6
                },
                name: t.js_average_latency
            }
        ],
        {
            title: t.js_average_latency_over_time,
            xaxis: { title: t.time },
            yaxis: { title: t.js_latency_ms }
        },
        { responsive: true }
    );
}

function renderAllSecurityCharts(chartData) {
    drawStatusChart(chartData.statusChart || { x: [], y: [] });
    drawErrorTypeChart(chartData.errorTypeChart || { x: [], y: [] });
    drawLatencyChart(chartData.latencyChart || { x: [], y: [] });
}

async function applySecurityFilter() {
    const t = window.i18n || {};
    const interval = document.getElementById("latencyInterval").value;
    try {
        const response = await fetch(`/api/security-chart-data?interval=${interval}`);
        const data = await response.json();
        drawLatencyChart(data.latency_chart || { x: [], y: [] });
    } catch (error) {
        console.log(t.js_security_filter_error, error);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const chartData = window.securityChartData || {};
    renderAllSecurityCharts(chartData);

    const filterButton = document.getElementById("applySecurityFilter");
    if (filterButton) {
        filterButton.addEventListener("click", applySecurityFilter);
    }
});