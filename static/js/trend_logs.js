async function updateDashboard() {
    try {
        const response = await fetch("/metrics");
        if (!response.ok) {
            return;
        }

        const data = await response.json();

        document.getElementById("failed-login-count").textContent = data.failed_login_count;
        document.getElementById("failed-login-rate").textContent = `%${data.failed_login_rate}`;

        const loginLogsBody = document.getElementById("login-logs-body");
        loginLogsBody.innerHTML = "";

        data.failed_logins.forEach((log) => {
            loginLogsBody.innerHTML += `
                <tr style="color:red;">
                    <td>${log.username}</td>
                    <td>Hatali</td>
                    <td>${log.time}</td>
                </tr>
            `;
        });

        data.successful_logins.forEach((log) => {
            loginLogsBody.innerHTML += `
                <tr style="color:green;">
                    <td>${log.username}</td>
                    <td>Basarili</td>
                    <td>${log.time}</td>
                </tr>
            `;
        });
    } catch (error) {
        console.log("Trend guncelleme hatasi:", error);
    }
}

setInterval(updateDashboard, 5000);
