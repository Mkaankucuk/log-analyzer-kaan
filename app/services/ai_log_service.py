import json
import re
import socket
from collections import Counter
from pathlib import Path
from urllib import error, request

import pandas as pd
from flask import current_app

from app.services.access_logs_service import load_request_logs
from app.services.security_service import load_security_logs

# Modele giden ham log gövdesi için üst sınır (token/latency için).
FILE_PROMPT_MAX_CHARS = 120_000
PROMPT_SAMPLE_LINES = 10
STATS_ROW_CAP = 120


def _resolve_temp_upload_path(stored_name: str) -> Path | None:
    if not stored_name or "/" in stored_name or "\\" in stored_name or stored_name.startswith("."):
        return None
    root = Path(current_app.config["TEMP_UPLOAD_DIR"]).resolve()
    path = (root / stored_name).resolve()
    try:
        if path.parent != root or not path.is_file():
            return None
    except OSError:
        return None
    return path


def _apply_filters(df, methods=None, endpoint=None, status_group=None):
    if methods:
        df = df[df["method"].isin(methods)]

    if endpoint and endpoint != "all":
        df = df[df["endpoint"] == endpoint]

    if status_group == "2xx":
        df = df[(df["status"] >= 200) & (df["status"] < 300)]
    elif status_group == "3xx":
        df = df[(df["status"] >= 300) & (df["status"] < 400)]
    elif status_group == "4xx":
        df = df[(df["status"] >= 400) & (df["status"] < 500)]
    elif status_group == "5xx":
        df = df[(df["status"] >= 500) & (df["status"] < 600)]

    return df


def _build_language_rules(response_mode):
    if response_mode == "en":
        return (
            "LANGUAGE: English only. No Turkish/Spanish/mixed wording.\n"
            "Use: latency, endpoint, method, status code, error rate, performance.\n"
        )
    return (
        "LANGUAGE: Turkish only. No English/Spanish/mixed wording.\n"
        "Use: gecikme, uç nokta, istek yöntemi, durum kodu, hata oranı, performans, sıklık.\n"
        "Keep log names (Admin, Interact1) unchanged.\n"
    )


def _build_output_instruction(response_mode):
    if response_mode == "en":
        return (
            _build_language_rules("en")
            + "\nOutput format (use exactly these section headers):\n"
            "English Analysis:\n"
            "1) Overall Status (max 2 short sentences)\n"
            "2) Detected Risks (max 3 bullets)\n"
            "3) Action Recommendations (max 3 bullets, priority order)\n"
        )
    return (
        _build_language_rules("tr")
        + "\nOutput format (use exactly these section headers):\n"
        "Türkçe Analiz:\n"
        "1) Genel Durum (en fazla 2 kısa cümle)\n"
        "2) Tespit Edilen Riskler (en fazla 3 madde)\n"
        "3) Aksiyon Önerileri (en fazla 3 madde, öncelik sırasıyla)\n"
        "Use formal business Turkish. Avoid slang and awkward wording.\n"
    )


def _build_expert_preamble(response_mode, domain):
    if response_mode == "en":
        return (
            f"You are an SRE and {domain} analysis expert.\n"
            "Use only the provided data. Do not invent metrics.\n"
            "Write clear, concise, non-repetitive sentences in English only.\n"
        )
    return (
        f"You are an SRE and {domain} analysis expert.\n"
        "Use only the provided data. Do not invent metrics.\n"
        "You may reason internally in any language, but the final answer must be entirely in Turkish.\n"
        "Write clear, concise, non-repetitive sentences. Never mix languages in the output.\n"
    )


def _build_access_prompt(limit, methods=None, endpoint=None, status_group=None, response_mode="tr"):
    df = load_request_logs()
    if df.empty:
        return None, "Access log verisi bulunamadı. Önce veriyi içeri aktarın.", None

    df = _apply_filters(df, methods=methods, endpoint=endpoint, status_group=status_group)
    if df.empty:
        return None, "Seçtiğiniz filtrelere uygun access log bulunamadı.", None

    sample_df = df.sort_values("Timestamp", ascending=False).head(limit).copy()
    sample_df["Timestamp"] = sample_df["Timestamp"].astype(str)
    stats_df = sample_df.head(STATS_ROW_CAP)

    method_counts = stats_df["method"].value_counts().to_dict()
    status_counts = stats_df["status"].astype(int).value_counts().to_dict()
    endpoint_counts = stats_df["endpoint"].value_counts().head(8).to_dict()
    avg_latency = round(float(stats_df["latency"].mean()), 2)
    p95_latency = round(float(stats_df["latency"].quantile(0.95)), 2)
    error_rate = round(float((stats_df["status"] >= 400).mean() * 100), 2)

    sample_lines = []
    for _, row in sample_df.head(PROMPT_SAMPLE_LINES).iterrows():
        sample_lines.append(
            f"{row['Timestamp']} | {row['method']} | {int(row['status'])} | {row['endpoint']} | {round(float(row['latency']), 2)}ms"
        )

    context = {
        "record_count": len(sample_df),
        "method_counts": method_counts,
        "status_counts": status_counts,
        "endpoint_counts": endpoint_counts,
        "avg_latency": avg_latency,
        "p95_latency": p95_latency,
        "error_rate": error_rate
    }

    prompt = (
        _build_expert_preamble(response_mode, "log")
        + "Analyze the access log summary below and provide practical insights.\n\n"
        f"İncelenen kayıt sayısı: {len(sample_df)}\n"
        f"Method dağılımı: {method_counts}\n"
        f"Status dağılımı: {status_counts}\n"
        f"En sık endpointler: {endpoint_counts}\n"
        f"Ortalama latency: {avg_latency} ms\n"
        f"P95 latency: {p95_latency} ms\n"
        f"Hata oranı: %{error_rate}\n\n"
        "Sample records:\n"
        + "\n".join(sample_lines)
        + "\n\n"
        + _build_output_instruction(response_mode)
    )
    return prompt, None, context


def _build_security_prompt(limit, status_group=None, response_mode="tr"):
    df = load_security_logs()
    if df.empty:
        return None, "Security log verisi bulunamadı. Önce veriyi içeri aktarın.", None

    sample_df = df.sort_values("timestamp", ascending=False).head(limit).copy()

    if status_group and "status_code" in sample_df.columns:
        status_numeric = pd.to_numeric(sample_df["status_code"], errors="coerce")
        if status_group == "2xx":
            sample_df = sample_df[(status_numeric >= 200) & (status_numeric < 300)]
        elif status_group == "3xx":
            sample_df = sample_df[(status_numeric >= 300) & (status_numeric < 400)]
        elif status_group == "4xx":
            sample_df = sample_df[(status_numeric >= 400) & (status_numeric < 500)]
        elif status_group == "5xx":
            sample_df = sample_df[(status_numeric >= 500) & (status_numeric < 600)]

    if sample_df.empty:
        return None, "Seçtiğiniz filtrelere uygun security log bulunamadı.", None

    stats_df = sample_df.head(STATS_ROW_CAP)

    status_counts = {}
    if "status_code" in stats_df.columns:
        status_counts = (
            pd.to_numeric(stats_df["status_code"], errors="coerce")
            .dropna()
            .astype(int)
            .value_counts()
            .to_dict()
        )

    error_counts = {}
    if "error_type" in stats_df.columns:
        error_counts = stats_df["error_type"].astype(str).value_counts().head(8).to_dict()

    service_counts = {}
    if "service" in stats_df.columns:
        service_counts = stats_df["service"].astype(str).value_counts().head(8).to_dict()

    avg_latency = round(float(stats_df["latency_ms"].mean()), 2)
    p95_latency = round(float(stats_df["latency_ms"].quantile(0.95)), 2)

    status_numeric_all = pd.to_numeric(stats_df.get("status_code"), errors="coerce")
    error_rate = round(float((status_numeric_all >= 400).mean() * 100), 2) if not status_numeric_all.empty else 0.0

    sample_lines = []
    for _, row in sample_df.head(PROMPT_SAMPLE_LINES).iterrows():
        ts = str(row.get("timestamp", "-"))
        service_name = str(row.get("service", "-"))
        method = str(row.get("method", "-"))
        endpoint = str(row.get("endpoint", "-"))
        status_code = str(row.get("status_code", "-"))
        latency = row.get("latency_ms", "-")
        sample_lines.append(f"{ts} | {service_name} | {method} | {endpoint} | {status_code} | {latency}ms")

    context = {
        "record_count": len(sample_df),
        "status_counts": status_counts,
        "error_counts": error_counts,
        "service_counts": service_counts,
        "avg_latency": avg_latency,
        "p95_latency": p95_latency,
        "error_rate": error_rate
    }

    insufficient_evidence = (
        "If evidence is insufficient for a claim, explicitly say "
        "'Bu bulgu için veri yetersiz'."
        if response_mode == "tr"
        else "If evidence is insufficient for a claim, explicitly say "
        "'Insufficient data for this finding'."
    )
    prompt = (
        _build_expert_preamble(response_mode, "security log")
        + "For security logs, prioritize concrete risk statements tied to status/error/service distributions.\n"
        + insufficient_evidence
        + "\n\nAnalyze the security log summary below and provide practical insights.\n\n"
        f"İncelenen kayıt sayısı: {len(sample_df)}\n"
        f"Status dağılımı: {status_counts}\n"
        f"Hata tipi dağılımı: {error_counts}\n"
        f"Servis dağılımı: {service_counts}\n"
        f"Ortalama latency: {avg_latency} ms\n"
        f"P95 latency: {p95_latency} ms\n"
        f"Hata oranı: %{error_rate}\n\n"
        "Sample records:\n"
        + "\n".join(sample_lines)
        + "\n\n"
        + _build_output_instruction(response_mode)
    )
    return prompt, None, context


def _build_file_prompt(limit, file_path: Path, response_mode="tr"):
    try:
        raw = file_path.read_bytes()
    except OSError:
        return None, "Dosya okunamadı.", None

    if not raw:
        return None, "Dosya boş.", None

    if b"\x00" in raw[:65536]:
        return None, "İkili dosya desteklenmiyor; metin tabanlı log dosyası seçin.", None

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return None, "Dosyada okunabilir satır yok.", None

    max_lines = max(1, min(int(limit), len(lines)))
    selected = lines[:max_lines]
    body = "\n".join(selected)
    truncated_chars = False
    if len(body) > FILE_PROMPT_MAX_CHARS:
        body = body[:FILE_PROMPT_MAX_CHARS]
        truncated_chars = True

    context = {
        "line_count": len(selected),
        "total_lines": len(lines),
        "truncated_lines": len(lines) > max_lines,
        "truncated_chars": truncated_chars,
    }

    prompt = (
        _build_expert_preamble(response_mode, "log")
        + "Use only the provided log excerpt. Do not invent events or metrics not present in the text.\n"
        + "The user uploaded a plain-text log file. Analyze the excerpt below.\n"
        f"Total lines in file: {len(lines)}. Lines included in this excerpt: {len(selected)}.\n"
        + (f"Note: excerpt truncated to {FILE_PROMPT_MAX_CHARS} characters.\n" if truncated_chars else "")
        + "\nLog excerpt:\n"
        + body
        + "\n\n"
        + _build_output_instruction(response_mode)
    )
    return prompt, None, context


def _looks_low_quality(text):
    if not text or len(text.strip()) < 40:
        return True

    normalized = " ".join(text.split())
    if len(normalized) > 2600:
        return True

    sentences = [s.strip().lower() for s in normalized.split(".") if len(s.strip()) > 15]
    if not sentences:
        return True

    repeated = Counter(sentences).most_common(1)[0][1]
    return repeated >= 3


_TURKISH_REPLACEMENTS = {
    "Turkish Analysis": "Türkçe Analiz",
    "English Analysis": "İngilizce Analiz",
    "Overall Status": "Genel Durum",
    "Detected Risks": "Tespit Edilen Riskler",
    "Action Recommendations": "Aksiyon Önerileri",
    "high frequency": "yüksek sıklık",
    "High Frequency": "Yüksek Sıklık",
    "high latency": "yüksek gecikme",
    "High Latency": "Yüksek Gecikme",
    "error rate": "hata oranı",
    "Error Rate": "Hata Oranı",
    "status codes": "durum kodları",
    "status code": "durum kodu",
    "Status Code": "Durum Kodu",
    "latency": "gecikme",
    "Latency": "Gecikme",
    "endpoint": "uç nokta",
    "Endpoint": "Uç Nokta",
    "method": "istek yöntemi",
    "Method": "İstek Yöntemi",
    "performance": "performans",
    "Performance": "Performans",
    "throughput": "istek yoğunluğu",
    "Throughput": "İstek Yoğunluğu",
    "bottleneck": "darboğaz",
    "Bottleneck": "Darboğaz",
    "service": "servis",
    "Service": "Servis",
    "error": "hata",
    "Error": "Hata",
    "request": "istek",
    "Request": "İstek",
    "response": "yanıt",
    "Response": "Yanıt",
    "traffic": "trafik",
    "Traffic": "Trafik",
    "spike": "artış",
    "Spike": "Artış",
    "alert": "alarm",
    "Alert": "Alarm",
    "threshold": "eşik",
    "Threshold": "Eşik",
    "timeout": "zaman aşımı",
    "Timeout": "Zaman Aşımı",
    "retry": "yeniden deneme",
    "Retry": "Yeniden Deneme",
    "optimize": "iyileştir",
    "Optimize": "İyileştir",
    "optimized": "iyileştirilmiş",
    "Optimized": "İyileştirilmiş",
    "frecuencia": "sıklık",
    "Frecuencia": "Sıklık",
    "frequency": "sıklık",
    "Frequency": "Sıklık",
    "frequencia": "sıklık",
    "Frequencia": "Sıklık",
}

_TURKISH_PHRASE_PATTERNS = [
    (re.compile(r"yüksek\s+frecuen\w*", re.I), "yüksek sıklıkta"),
    (re.compile(r"yüksek\s+frequen\w*", re.I), "yüksek sıklıkta"),
    (re.compile(r"yüksek\s+sıklıkda\b", re.I), "yüksek sıklıkta"),
    (re.compile(r"high\s+frequen\w*", re.I), "yüksek sıklıkta"),
    (re.compile(r"frecuen\w*['’]?da\b", re.I), "sıklıkta"),
    (re.compile(r"frecuen\w*['’]?de\b", re.I), "sıklıkta"),
    (re.compile(r"frequen\w*['’]?da\b", re.I), "sıklıkta"),
    (re.compile(r"frequen\w*['’]?de\b", re.I), "sıklıkta"),
    (re.compile(r"\bsıklıkda\b", re.I), "sıklıkta"),
    (re.compile(r"performans[ıi]\s+optimize", re.I), "performansı iyileştirilmeli"),
    (re.compile(r"performans[ıi]\s+iyileştir\s+edilmelidir", re.I), "performansı iyileştirilmelidir"),
    (re.compile(r"optimize\s+edilmelidir", re.I), "iyileştirilmelidir"),
    (re.compile(r"iyileştir\s+edilmelidir", re.I), "iyileştirilmelidir"),
]

_ENGLISH_REPLACEMENTS = {
    "Türkçe Analiz": "English Analysis",
    "Genel Durum": "Overall Status",
    "Tespit Edilen Riskler": "Detected Risks",
    "Aksiyon Önerileri": "Action Recommendations",
    "gecikme": "latency",
    "Gecikme": "Latency",
    "uç nokta": "endpoint",
    "Uç nokta": "Endpoint",
    "istek yöntemi": "method",
    "durum kodu": "status code",
    "hata oranı": "error rate",
    "performans": "performance",
    "sıklık": "frequency",
    "Sıklık": "Frequency",
    "frecuencia": "frequency",
    "Frecuencia": "Frequency",
    "iyileştirilmelidir": "should be optimized",
    "iyileştir": "optimize",
}


def _normalize_turkish_text(text):
    normalized = text
    for pattern, replacement in _TURKISH_PHRASE_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    for old, new in _TURKISH_REPLACEMENTS.items():
        normalized = normalized.replace(old, new)
    return normalized


def _normalize_english_text(text):
    normalized = text
    for old, new in _ENGLISH_REPLACEMENTS.items():
        normalized = normalized.replace(old, new)
    return normalized


def _finalize_output(text, response_mode):
    if response_mode == "en":
        return _normalize_english_text(text)
    return _normalize_turkish_text(text)


def _fallback_analysis(context, source, response_mode="tr"):
    if source == "file":
        lc = context.get("line_count", 0)
        tl = context.get("total_lines", lc)
        note_lines = "Excerpt covers all lines." if not context.get("truncated_lines") else f"Only first {lc} of {tl} lines were in the excerpt."
        note_chars = " Full excerpt shown." if not context.get("truncated_chars") else " Excerpt was also truncated by character limit."

        english = (
            "English Analysis:\n"
            "1) Overall Status\n"
            f"- Plain-text log file with {tl} line(s); analysis used {lc} line(s). {note_lines}{note_chars}\n\n"
            "2) Detected Risks\n"
            "- Automated model output was unavailable; review the raw log excerpt manually for errors, auth failures, and anomalies.\n\n"
            "3) Action Recommendations\n"
            "- Re-run analysis when the AI service is available, or grep/filter the file for ERROR, WARN, 5xx, and failed auth patterns.\n\n"
        )
        if response_mode == "en":
            return english
        return (
            "Türkçe Analiz:\n"
            "1) Genel Durum\n"
            f"- Düz metin log dosyası: toplam {tl} satır; analizde {lc} satır kullanıldı. {note_lines}{note_chars}\n\n"
            "2) Tespit Edilen Riskler\n"
            "- Otomatik model çıktısı alınamadı; ham logda hata, kimlik doğrulama ve anomali için manuel inceleme önerilir.\n\n"
            "3) Aksiyon Önerileri\n"
            "- AI servisi hazır olduğunda analizi tekrar çalıştırın veya dosyada ERROR, WARN, 5xx ve başarısız giriş kalıplarını arayın.\n"
        )

    if source == "security":
        top_services = sorted(context["service_counts"].items(), key=lambda x: x[1], reverse=True)[:3]
        top_errors = sorted(context["error_counts"].items(), key=lambda x: x[1], reverse=True)[:3]
        top_status = sorted(context["status_counts"].items(), key=lambda x: x[1], reverse=True)[:3]

        service_text = ", ".join([f"{name}: {count}" for name, count in top_services]) or "-"
        error_text = ", ".join([f"{name}: {count}" for name, count in top_errors]) or "-"
        status_text = ", ".join([f"{code}: {count}" for code, count in top_status]) or "-"

        english = (
            "English Analysis:\n"
            "1) Overall Status\n"
            f"- Reviewed records: {context['record_count']}. Error rate: %{context['error_rate']}.\n"
            f"- Average latency is {context['avg_latency']} ms, P95 latency is {context['p95_latency']} ms.\n\n"
            "2) Detected Risks\n"
            f"- Most frequent status codes: {status_text}.\n"
            f"- Most frequent error types: {error_text}.\n"
            f"- Services with highest traffic/load: {service_text}.\n\n"
            "3) Action Recommendations\n"
            "- Define service-level alert thresholds for 4xx/5xx rates.\n"
            "- If P95 is high, review dependency timeout and retry settings on busy services.\n"
            "- Create runbooks for top error types and map them to automated alerts.\n\n"
        )
        if response_mode == "en":
            return english
        return (
            "Türkçe Analiz:\n"
            "1) Genel Durum\n"
            f"- İncelenen kayıt sayısı: {context['record_count']}. Hata oranı: %{context['error_rate']}.\n"
            f"- Ortalama gecikme {context['avg_latency']} ms, P95 gecikme {context['p95_latency']} ms.\n\n"
            "2) Tespit Edilen Riskler\n"
            f"- En sık durum kodları: {status_text}.\n"
            f"- En sık hata tipleri: {error_text}.\n"
            f"- Trafik/yükün en yoğun olduğu servisler: {service_text}.\n\n"
            "3) Aksiyon Önerileri\n"
            "- 4xx/5xx oranları için servis bazlı alarm eşikleri tanımlayın.\n"
            "- P95 yüksekse yoğun servislerde bağımlılık timeout ve retry ayarlarını gözden geçirin.\n"
            "- En sık hata tipleri için runbook oluşturup otomatik alarmlarla eşleştirin.\n"
        )

    top_methods = sorted(context["method_counts"].items(), key=lambda x: x[1], reverse=True)[:2]
    top_endpoints = sorted(context["endpoint_counts"].items(), key=lambda x: x[1], reverse=True)[:3]
    top_status = sorted(context["status_counts"].items(), key=lambda x: x[1], reverse=True)[:3]

    method_text = ", ".join([f"{name}: {count}" for name, count in top_methods]) or "-"
    endpoint_text = ", ".join([f"{name}: {count}" for name, count in top_endpoints]) or "-"
    status_text = ", ".join([f"{code}: {count}" for code, count in top_status]) or "-"

    english = (
        "English Analysis:\n"
        "1) Overall Status\n"
        f"- Reviewed records: {context['record_count']}. Error rate: %{context['error_rate']}.\n"
        f"- Average latency is {context['avg_latency']} ms, P95 latency is {context['p95_latency']} ms.\n\n"
        "2) Detected Risks\n"
        f"- Method distribution may be imbalanced ({method_text}).\n"
        f"- Most frequent status codes: {status_text}. Monitor for 4xx/5xx growth.\n"
        f"- Most loaded endpoints: {endpoint_text}. Potential bottleneck risk.\n\n"
        "3) Action Recommendations\n"
        "- Define endpoint-level alerts and error budgets for 4xx/5xx rates.\n"
        "- If P95 is high, apply caching and query optimizations on hot endpoints.\n"
        "- Track daily trends by method and endpoint to detect anomalies early.\n\n"
    )
    if response_mode == "en":
        return english
    return (
        "Türkçe Analiz:\n"
        "1) Genel Durum\n"
        f"- İncelenen kayıt sayısı: {context['record_count']}. Hata oranı: %{context['error_rate']}.\n"
        f"- Ortalama gecikme {context['avg_latency']} ms, P95 gecikme {context['p95_latency']} ms.\n\n"
        "2) Tespit Edilen Riskler\n"
        f"- Method dağılımı dengesiz olabilir ({method_text}).\n"
        f"- En sık durum kodları: {status_text}. 4xx/5xx artışı izlenmeli.\n"
        f"- En yoğun endpointler: {endpoint_text}. Darboğaz riski olabilir.\n\n"
        "3) Aksiyon Önerileri\n"
        "- 4xx/5xx oranları için endpoint bazlı alarm ve hata bütçesi tanımlayın.\n"
        "- P95 yüksekse yoğun endpointlerde cache ve sorgu optimizasyonu uygulayın.\n"
        "- Method ve endpoint bazlı günlük trend takibiyle sapmaları erken tespit edin.\n"
    )


def _resolve_ollama_settings() -> dict[str, object]:
    return {
        "model": current_app.config["OLLAMA_MODEL"],
        "num_predict": 200,
        "num_ctx": 2048,
        "timeout": int(current_app.config["OLLAMA_TIMEOUT_SECONDS"]),
        "keep_alive": current_app.config.get("OLLAMA_KEEP_ALIVE", "15m"),
    }


def warmup_ollama() -> None:
    """Keep the default model loaded in Ollama memory (faster first analysis)."""
    settings = _resolve_ollama_settings()
    payload = {
        "model": settings["model"],
        "prompt": "ok",
        "stream": False,
        "keep_alive": settings["keep_alive"],
        "options": {"num_predict": 1, "num_ctx": 512},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{current_app.config['OLLAMA_BASE_URL'].rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            response.read()
    except Exception:
        pass


def run_ai_log_analysis(
    limit=100,
    methods=None,
    endpoint=None,
    status_group=None,
    source="access",
    response_mode="tr",
    file_stored_name=None,
):
    source = (source or "access").lower()
    response_mode = (response_mode or "tr").lower()
    if response_mode not in {"en", "tr"}:
        response_mode = "tr"
    if source == "file":
        if not file_stored_name:
            return {"ok": False, "message": "Geçici dosya adı eksik. Önce dosya yükleyin."}
        path = _resolve_temp_upload_path(file_stored_name)
        if not path:
            return {"ok": False, "message": "Geçici dosya bulunamadı. Dosyayı tekrar yükleyin."}
        prompt, error_message, context = _build_file_prompt(limit, path, response_mode=response_mode)
    elif source == "security":
        prompt, error_message, context = _build_security_prompt(
            limit,
            status_group=status_group,
            response_mode=response_mode
        )
    else:
        prompt, error_message, context = _build_access_prompt(
            limit,
            methods=methods,
            endpoint=endpoint,
            status_group=status_group,
            response_mode=response_mode
        )
    if error_message:
        return {"ok": False, "message": error_message}

    ollama = _resolve_ollama_settings()
    payload = {
        "model": ollama["model"],
        "prompt": prompt,
        "stream": False,
        "keep_alive": ollama["keep_alive"],
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_predict": ollama["num_predict"],
            "num_ctx": ollama["num_ctx"],
        },
    }
    body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        f"{current_app.config['OLLAMA_BASE_URL'].rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=int(ollama["timeout"])) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            generated = parsed.get("response", "").strip()
            if _looks_low_quality(generated):
                fallback_message = _fallback_analysis(context, source, response_mode=response_mode)
                fallback_message = _finalize_output(fallback_message, response_mode)
                return {"ok": True, "message": fallback_message}
            if source == "file":
                source_title = "Yüklenen dosya" if response_mode == "tr" else "Uploaded file"
            else:
                source_title = "Security Logs" if source == "security" else "Access Logs"
            generated = _finalize_output(generated, response_mode)
            if response_mode == "tr":
                return {"ok": True, "message": f"Kaynak: {source_title}\n\n{generated}"}
            return {"ok": True, "message": f"Source: {source_title}\n\n{generated}"}
    except error.HTTPError as http_exc:
        details = ""
        try:
            details = http_exc.read().decode("utf-8")
        except Exception:
            details = str(http_exc)
        return {
            "ok": False,
            "message": f"Ollama yanıt hatası ({http_exc.code}). Model yüklü olmayabilir. Detay: {details}"
        }
    except error.URLError:
        return {
            "ok": False,
            "message": "Ollama servisine bağlanılamadı. `ollama serve` çalıştığından emin olun."
        }
    except (TimeoutError, socket.timeout):
        fallback_message = _fallback_analysis(context, source, response_mode=response_mode)
        fallback_message = _finalize_output(fallback_message, response_mode)
        if response_mode == "tr":
            prefix = (
                "Not: AI modeli yanıt vermedi (zaman aşımı). "
                "Aşağıdaki özet kural tabanlı yedek analizdir. "
                "Daha hızlı sonuç için kayıt sayısını düşürün veya .env içinde "
                "OLLAMA_TIMEOUT_SECONDS değerini artırın.\n\n"
            )
        else:
            prefix = (
                "Note: AI model timed out. Showing rule-based fallback summary. "
                "Lower the record count or increase OLLAMA_TIMEOUT_SECONDS in .env.\n\n"
            )
        return {"ok": True, "message": prefix + fallback_message, "fallback": True}
    except Exception as exc:
        return {"ok": False, "message": f"AI analiz hatası: {exc}"}
