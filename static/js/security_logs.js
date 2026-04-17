function drawStatusChart(data) {
    Plotly.newPlot(
        "statusChart",
        [
            {
                x: data.x,
                y: data.y,
                type: "bar",
                marker: { color: "#1f4b99" },
                name: "Status Code"
            }
        ],
        {
            title: "Status Code Distribution",
            xaxis: { title: "Status Code" },
            yaxis: { title: "Count" }
        },
        { responsive: true }
    );
}

function drawErrorTypeChart(data) {
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
                name: "Error Type"
            }
        ],
        {
            title: "Error Type Distribution",
            xaxis: { title: "Error Type" },
            yaxis: { title: "Count" }
        },
        { responsive: true }
    );
}

function drawLatencyChart(data) {
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
                name: "Average Latency"
            }
        ],
        {
            title: "Average Latency Over Time",
            xaxis: { title: "Time" },
            yaxis: { title: "Latency (ms)" }
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
    const interval = document.getElementById("latencyInterval").value;

    const response = await fetch(`/api/security-chart-data?interval=${interval}`);
    const data = await response.json();

    drawLatencyChart(data.latency_chart || { x: [], y: [] });
}

document.addEventListener("DOMContentLoaded", function () {
    const chartData = window.securityChartData || {};
    renderAllSecurityCharts(chartData);

    const filterButton = document.getElementById("applySecurityFilter");
    if (filterButton) {
        filterButton.addEventListener("click", applySecurityFilter);
    }
});