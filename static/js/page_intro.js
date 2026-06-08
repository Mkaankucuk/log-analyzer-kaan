(function () {
    document.querySelectorAll(".page-intro-banner").forEach(function (banner) {
        const ms = parseInt(banner.getAttribute("data-auto-hide-ms") || "7500", 10);
        const hideDelay = Number.isFinite(ms) ? ms : 7500;

        setTimeout(function () {
            banner.classList.add("is-hiding");
            setTimeout(function () {
                banner.remove();
            }, 450);
        }, hideDelay);
    });
})();
