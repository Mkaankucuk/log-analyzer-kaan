function drawStatusChart(data) {
    Plotly.newPlot("statusChart", [
        {
            x: data.x,
            y: data.y,
            type: "bar",
            name: "Status Code"
        }
    ], {
        title: "Status Code Distribution",
        xaxis: { title: "Status Code" },
        yaxis: { title: "Count" }
    }, {
        responsive: true
    });
}

function drawErrorTypeChart(data) {
    Plotly.newPlot("errorTypeChart", [
        {
            x: data.x,
            y: data.y,
            type: "bar",
            name: "Error Type"
        }
    ], {
        title: "Error Type Distribution",
        xaxis: { title: "Error Type" },
        yaxis: { title: "Count" }
    }, {
        responsive: true
    });
}

function drawLatencyChart(data) {
    Plotly.newPlot("latencyChart", [
        {
            x: data.x,
            y: data.y,
            type: "scatter",
            mode: "lines+markers",
            name: "Average Latency"
        }
    ], {
        title: "Average Latency Over Time",
        xaxis: { title: "Time" },
        yaxis: { title: "Latency (ms)" }
    }, {
        responsive: true
    });
}

document.addEventListener("DOMContentLoaded", function () {
    const chartData = window.securityChartData || {};

    drawStatusChart(chartData.statusChart || { x: [], y: [] });
    drawErrorTypeChart(chartData.errorTypeChart || { x: [], y: [] });
    drawLatencyChart(chartData.latencyChart || { x: [], y: [] });
});