import json
import socket
from collections import Counter
from urllib import error, request

import pandas as pd
from flask import current_app

from app.services.access_logs_service import load_request_logs
from app.services.security_service import load_security_logs


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


def _build_output_instruction(response_mode):
    if response_mode == "en":
        return (
            "Output format (use exactly these section headers):\n"
            "English Analysis:\n"
            "1) Overall Status (max 2 short sentences)\n"
            "2) Detected Risks (max 3 bullets)\n"
            "3) Action Recommendations (max 3 bullets, priority order)\n"
        )
    return (
        "Output format (use exactly these section headers):\n"
        "Turkish Analysis:\n"
        "1) Genel Durum (en fazla 2 kısa cümle)\n"
        "2) Tespit Edilen Riskler (en fazla 3 madde)\n"
        "3) Aksiyon Önerileri (en fazla 3 madde, öncelik sırasıyla)\n"
        "Write the final output only in Turkish.\n"
        "Use formal business Turkish. Avoid slang and awkward wording.\n"
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

    method_counts = sample_df["method"].value_counts().to_dict()
    status_counts = sample_df["status"].astype(int).value_counts().to_dict()
    endpoint_counts = sample_df["endpoint"].value_counts().head(8).to_dict()
    avg_latency = round(float(sample_df["latency"].mean()), 2)
    p95_latency = round(float(sample_df["latency"].quantile(0.95)), 2)
    error_rate = round(float((sample_df["status"] >= 400).mean() * 100), 2)

    sample_lines = []
    for _, row in sample_df.head(20).iterrows():
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
        "You are an SRE and log analysis expert.\n"
        "Think and reason in English.\n"
        "Use only the provided data. Do not invent metrics.\n"
        "Write clear, concise, non-repetitive sentences.\n"
        "When output language is Turkish, use professional business language.\n"
        "Avoid colloquial words, vague claims, and mixed-language wording.\n\n"
        "Analyze the access log summary below and provide practical insights.\n\n"
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

    status_counts = {}
    if "status_code" in sample_df.columns:
        status_counts = (
            pd.to_numeric(sample_df["status_code"], errors="coerce")
            .dropna()
            .astype(int)
            .value_counts()
            .to_dict()
        )

    error_counts = {}
    if "error_type" in sample_df.columns:
        error_counts = sample_df["error_type"].astype(str).value_counts().head(8).to_dict()

    service_counts = {}
    if "service" in sample_df.columns:
        service_counts = sample_df["service"].astype(str).value_counts().head(8).to_dict()

    avg_latency = round(float(sample_df["latency_ms"].mean()), 2)
    p95_latency = round(float(sample_df["latency_ms"].quantile(0.95)), 2)

    status_numeric_all = pd.to_numeric(sample_df.get("status_code"), errors="coerce")
    error_rate = round(float((status_numeric_all >= 400).mean() * 100), 2) if not status_numeric_all.empty else 0.0

    sample_lines = []
    for _, row in sample_df.head(20).iterrows():
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

    prompt = (
        "You are an SRE and security log analysis expert.\n"
        "Think and reason in English.\n"
        "Use only the provided data. Do not invent metrics.\n"
        "Write clear, concise, non-repetitive sentences.\n"
        "When output language is Turkish, use professional business language.\n"
        "Avoid colloquial words, vague claims, and mixed-language wording.\n"
        "For security logs, prioritize concrete risk statements tied to status/error/service distributions.\n"
        "If evidence is insufficient for a claim, explicitly say 'Bu bulgu için veri yetersiz'.\n\n"
        "Analyze the security log summary below and provide practical insights.\n\n"
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


def _fallback_analysis(context, source, response_mode="tr"):
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
            "Turkish Analysis:\n"
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
        "Turkish Analysis:\n"
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


def run_ai_log_analysis(limit=100, methods=None, endpoint=None, status_group=None, source="access", response_mode="tr"):
    source = (source or "access").lower()
    response_mode = (response_mode or "tr").lower()
    if response_mode not in {"en", "tr"}:
        response_mode = "tr"
    if source == "security":
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

    payload = {
        "model": current_app.config["OLLAMA_MODEL"],
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.15,
            "num_predict": 260
        }
    }
    body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        f"{current_app.config['OLLAMA_BASE_URL'].rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=current_app.config["OLLAMA_TIMEOUT_SECONDS"]) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            generated = parsed.get("response", "").strip()
            if _looks_low_quality(generated):
                return {"ok": True, "message": _fallback_analysis(context, source, response_mode=response_mode)}
            source_title = "Security Logs" if source == "security" else "Access Logs"
            return {"ok": True, "message": f"Source/Kaynak: {source_title}\n\n{generated}"}
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
        return {
            "ok": False,
            "message": "AI analiz süresi doldu (timeout). Kayıt sayısını düşürüp tekrar deneyin."
        }
    except Exception as exc:
        return {"ok": False, "message": f"AI analiz hatası: {exc}"}
