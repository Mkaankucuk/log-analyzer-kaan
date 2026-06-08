(function () {
    const MAX_READ_BYTES = 512 * 1024;
    const MAX_FILE_BYTES = 15 * 1024 * 1024;
    const PREVIEW_MAX_LINES = 400;

    function tr(key, fallback) {
        return (window.i18n && window.i18n[key]) || fallback;
    }

    const dropZone = document.getElementById("fileDropZone");
    const fileInput = document.getElementById("fileUploadInput");
    const browseBtn = document.getElementById("fileUploadBrowse");
    const clearBtn = document.getElementById("fileUploadClear");
    const metaEl = document.getElementById("fileUploadMeta");
    const tempStatusEl = document.getElementById("fileUploadTempStatus");
    const lineInfoEl = document.getElementById("fileUploadLineInfo");
    const previewEl = document.getElementById("fileUploadPreview");
    const hintEl = document.getElementById("fileDropHint");

    function formatBytes(n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / (1024 * 1024)).toFixed(1) + " MB";
    }

    function setDragOver(on) {
        dropZone.classList.toggle("is-dragover", on);
    }

    function resetUi() {
        fileInput.value = "";
        metaEl.textContent = "";
        tempStatusEl.textContent = "";
        lineInfoEl.textContent = "";
        previewEl.textContent = tr("file_upload_no_preview", "");
        hintEl.hidden = false;
    }

    function truncateName(name, maxLen) {
        if (!name || name.length <= maxLen) return name || "";
        return name.slice(0, maxLen) + "…";
    }

    async function saveTempOnServer(file) {
        tempStatusEl.textContent = tr("file_upload_temp_saving", "");
        const fd = new FormData();
        fd.append("file", file);
        try {
            const res = await fetch("/dashboard/file-upload/temp", {
                method: "POST",
                body: fd,
                credentials: "same-origin",
            });

            if (res.status === 413) {
                tempStatusEl.textContent = tr("file_upload_error_size", "");
                tempStatusEl.style.color = "#b45309";
                return;
            }

            let data = null;
            try {
                data = await res.json();
            } catch (_) {
                data = null;
            }

            if (!data || !data.ok) {
                tempStatusEl.textContent = tr("file_upload_temp_fail", "");
                tempStatusEl.style.color = "#b45309";
                return;
            }

            const label = tr("file_upload_temp_saved", "").replace(
                "{name}",
                truncateName(data.stored_name || "", 56)
            );
            tempStatusEl.textContent = label;
            tempStatusEl.style.color = "#15803d";
        } catch (_) {
            tempStatusEl.textContent = tr("file_upload_temp_fail", "");
            tempStatusEl.style.color = "#b45309";
        }
    }

    async function clearTempOnServer() {
        try {
            await fetch("/dashboard/file-upload/temp/clear", {
                method: "POST",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
        } catch (_) {
            /* ignore */
        }
    }

    function countLines(text) {
        if (!text) return 0;
        let newlines = 0;
        for (let i = 0; i < text.length; i++) {
            if (text.charCodeAt(i) === 10) newlines++;
        }
        return newlines + 1;
    }

    function slicePreviewLines(text) {
        const lines = text.split(/\r?\n/);
        if (lines.length <= PREVIEW_MAX_LINES) return text;
        return lines.slice(0, PREVIEW_MAX_LINES).join("\n") + "\n…";
    }

    function readChunk(file, callback, onError) {
        const toRead = Math.min(file.size, MAX_READ_BYTES);
        const blob = file.slice(0, toRead);
        const reader = new FileReader();
        reader.onload = function () {
            callback(String(reader.result || ""), toRead < file.size);
        };
        reader.onerror = function () {
            onError();
        };
        reader.readAsText(blob);
    }

    function handleFile(file) {
        if (!file) return;

        if (file.size > MAX_FILE_BYTES) {
            metaEl.textContent = tr("file_upload_error_size", "File too large.");
            tempStatusEl.textContent = "";
            lineInfoEl.textContent = "";
            previewEl.textContent = "";
            hintEl.hidden = true;
            return;
        }

        hintEl.hidden = true;
        metaEl.textContent =
            file.name + " · " + formatBytes(file.size);
        tempStatusEl.style.color = "";

        saveTempOnServer(file);

        readChunk(
            file,
            function (text, truncated) {
                if (text.indexOf("\u0000") !== -1) {
                    lineInfoEl.textContent = tr("file_upload_binary_hint", "");
                    previewEl.textContent = "";
                    return;
                }
                const linesInChunk = countLines(text);
                if (truncated) {
                    lineInfoEl.textContent = tr(
                        "file_upload_lines_partial",
                        ""
                    ).replace("{n}", String(linesInChunk));
                } else {
                    lineInfoEl.textContent = tr(
                        "file_upload_lines_full",
                        ""
                    ).replace("{n}", String(linesInChunk));
                }
                previewEl.textContent = slicePreviewLines(text);
            },
            function () {
                lineInfoEl.textContent = "";
                previewEl.textContent = tr("file_upload_error_read", "");
            }
        );
    }

    dropZone.addEventListener("click", function (e) {
        if (e.target === browseBtn || browseBtn.contains(e.target)) return;
        fileInput.click();
    });

    browseBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener("change", function () {
        const f = fileInput.files && fileInput.files[0];
        handleFile(f);
    });

    ["dragenter", "dragover"].forEach(function (ev) {
        dropZone.addEventListener(ev, function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
            setDragOver(true);
        });
    });

    dropZone.addEventListener("dragleave", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const related = e.relatedTarget;
        if (related && dropZone.contains(related)) return;
        setDragOver(false);
    });

    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        setDragOver(false);
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) handleFile(f);
    });

    clearBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        clearTempOnServer().finally(function () {
            resetUi();
        });
    });
})();
