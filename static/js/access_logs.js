const initialDataElement = document.getElementById("access-logs-initial-data");
const initialData = initialDataElement ? JSON.parse(initialDataElement.textContent) : {};

let methodChartData = initialData.method_chart_data || {};
let requestErrorChart = initialData.request_error_chart || { x: [], total_requests: [], error_count: [] };
let latencyChart = initialData.latency_chart || { x: [], avg_latency: [] };

const methodCheckboxes = document.querySelectorAll(".method-checkbox");
const statusGroupFilter = document.getElementById("statusGroupFilter");
const statusCodeFilter = document.getElementById("statusCodeFilter");
const endpointFilter = document.getElementById("endpointFilter");
const intervalFilter = document.getElementById("intervalFilter");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");
const resetFiltersBtn = document.getElementById("resetFiltersBtn");

function getSelectedMethods() {
    return Array.from(methodCheckboxes)
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
}

function drawMethodChart() {
    const selectedMethods = Object.keys(methodChartData);

    const traces = selectedMethods
        .filter((method) => methodChartData[method])
        .map((method) => ({
            x: methodChartData[method].x,
            y: methodChartData[method].y,
            mode: "lines+markers",
            type: "scatter",
            name: method
        }));

    Plotly.newPlot("requestMethodChart", traces, {
        title: "Istek Sayisi Zamanla",
        xaxis: { title: "Zaman" },
        yaxis: { title: "Istek Sayisi" },
        template: "plotly_white"
    }, { responsive: true });
}

function drawRequestErrorChart() {
    Plotly.newPlot("requestErrorChart", [
        {
            x: requestErrorChart.x,
            y: requestErrorChart.total_requests,
            mode: "lines+markers",
            type: "scatter",
            name: "Total Requests"
        },
        {
            x: requestErrorChart.x,
            y: requestErrorChart.error_count,
            mode: "lines+markers",
            type: "scatter",
            name: "Error Count",
            yaxis: "y2"
        }
    ], {
        title: "Request and Error Counts Over Time",
        xaxis: { title: "Time" },
        yaxis: { title: "Total Requests" },
        yaxis2: {
            title: "Error Count",
            overlaying: "y",
            side: "right"
        },
        template: "plotly_white"
    }, { responsive: true });
}

function drawLatencyChart() {
    Plotly.newPlot("latencyChart", [
        {
            x: latencyChart.x,
            y: latencyChart.avg_latency,
            mode: "lines+markers",
            type: "scatter",
            name: "Average Latency"
        }
    ], {
        title: "Average Latency Over Time",
        xaxis: { title: "Time" },
        yaxis: { title: "Latency (ms)" },
        template: "plotly_white"
    }, { responsive: true });
}

function renderAllCharts() {
    drawMethodChart();
    drawRequestErrorChart();
    drawLatencyChart();
}

async function applyFilters() {
    const methods = getSelectedMethods();
    const params = new URLSearchParams();

    methods.forEach((m) => params.append("method", m));

    if (statusGroupFilter.value) {
        params.append("status_group", statusGroupFilter.value);
    }

    if (statusCodeFilter.value) {
        params.append("status_code", statusCodeFilter.value);
    }

    if (endpointFilter.value) {
        params.append("endpoint", endpointFilter.value);
    }

    if (intervalFilter.value) {
        params.append("interval", intervalFilter.value);
    }

    try {
        const response = await fetch(`/api/access-logs-data?${params.toString()}`);
        const data = await response.json();

        methodChartData = data.method_chart_data;
        requestErrorChart = data.request_error_chart;
        latencyChart = data.latency_chart;

        renderAllCharts();
    } catch (error) {
        console.log("Filtre uygulama hatasi:", error);
    }
}

function resetFilters() {
    methodCheckboxes.forEach((cb) => {
        cb.checked = true;
    });
    statusGroupFilter.value = "";
    statusCodeFilter.value = "";
    endpointFilter.value = "all";
    intervalFilter.value = "hour";
}

applyFiltersBtn.addEventListener("click", applyFilters);
resetFiltersBtn.addEventListener("click", resetFilters);

renderAllCharts();
