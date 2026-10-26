import json
import re
import httpx
from app.core.config import settings
from app.schemas import AnalysisResult


def _extract_demo(text: str, language: str, level: str) -> dict:
    """Deterministic fallback: extract only strings visibly present in the source."""
    lines = [line.strip(" •\t-–") for line in text.splitlines() if line.strip()]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    title = next((line for line in lines if len(line) < 100), "Notice summary")
    date_pattern = r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b"
    deadline_sentence = next((sentence for sentence in sentences if re.search(date_pattern, sentence, re.I) and re.search(r"deadline|last date|submit(?:ted)? by|due on|before", sentence, re.I)), None)
    date_match = re.search(date_pattern, deadline_sentence or "", re.I)
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    urls = re.findall(r"https?://[^\s)>,]+", text)
    money = re.findall(r"(?:₹|Rs\.?\s*)[\d,]+(?:\.\d{1,2})?", text, re.I)
    evidence = []
    eligibility = [sentence for sentence in sentences if re.search(r"eligible|eligibility|must be .*student|only .*applicant|resident of", sentence, re.I)][:5]
    documents = [sentence for sentence in sentences if re.search(r"documents?|certificates?|proof of|attach|academic record", sentence, re.I)][:6]
    fee_sentence = next((sentence for sentence in sentences if re.search(r"fee|charge|cost", sentence, re.I) and (money or re.search(r"free|no fee", sentence, re.I))), None)
    contact_sentence = next((sentence for sentence in sentences if re.search(r"contact|email|phone|telephone", sentence, re.I) and (emails or re.search(r"\+?\d[\d ()-]{7,}", sentence))), None)
    for item, label in [(deadline_sentence, "Deadline"), *[(sentence, "Eligibility") for sentence in eligibility], *[(sentence, "Required documents") for sentence in documents], (fee_sentence, "Fees"), (contact_sentence, "Contact")]:
        if item:
            evidence.append({"field": label, "quote": item[:420]})
    steps = []
    for index, line in enumerate(lines):
        if re.search(r"apply|submit|visit|upload|send|email|register|complete", line, re.I):
            steps.append(line)
        if len(steps) == 4:
            break
    if not steps:
        steps = ["Review the full notice and confirm the required process with the issuing organization."]
    summary = "This notice contains instructions and details that may require action. Review the original source carefully and verify any unclear information with the issuing organization."
    if len(text.strip()) < 70:
        summary = "The notice text is too short to summarize reliably. Add the complete notice or upload a clearer document."
    return {
        "notice_title": title,
        "purpose": "The notice describes an announcement or process. The issuing organization and context should be confirmed in the original text.",
        "eligibility": eligibility,
        "deadline": date_match.group(0) if date_match else None,
        "required_documents": documents,
        "application_steps": steps,
        "fees": ", ".join(money) if money else None,
        "contact_information": ", ".join(emails) if emails else None,
        "website": urls[0] if urls else None,
        "missing_information": [label for label, missing in [("eligibility", not eligibility), ("required documents", not documents), ("official deadline", not date_match), ("fees", not money), ("contact information", not emails), ("application link", not urls)] if missing],
        "uncertain_information": ["Demo extraction uses simple text patterns. Verify all details against the original notice."],
        "plain_language_summary": summary,
        "translated_summary": None,
        "checklist": [{"text": step, "due_date": None} for step in steps],
        "source_evidence": evidence,
        "demo_mode": True,
        "language": language,
        "reading_level": level,
    }


def _json_from_text(content: str) -> dict:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    return json.loads(cleaned)


async def analyze_notice(text: str, language: str = "English", level: str = "Simple") -> dict:
    if not settings.ai_base_url or not settings.ai_api_key:
        return AnalysisResult.model_validate(_extract_demo(text, language, level)).model_dump()
    system = "You are ActionLens, a careful notice accessibility assistant. Use only the supplied notice as factual evidence. Never infer missing dates, criteria, amounts, links, or documents. Use 'Not specified in the notice' when absent. Preserve names, dates and amounts. Return only valid JSON matching: notice_title, purpose, eligibility (array), deadline (string or null), required_documents (array), application_steps (array), fees (string or null), contact_information (string or null), website (string or null), missing_information (array), uncertain_information (array), plain_language_summary (string), translated_summary (string or null), checklist (array of {text,due_date}), source_evidence (array of {field,quote})."
    prompt = f"Summarize this notice at a {level.lower()} reading level. Write the summary in {language}. Include short exact source quotes for important facts.\n\nNOTICE:\n{text[:30000]}"
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            settings.ai_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            json={"model": settings.ai_model, "temperature": 0.1, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        )
        response.raise_for_status()
    data = _json_from_text(response.json()["choices"][0]["message"]["content"])
    required = ["notice_title", "purpose", "eligibility", "deadline", "required_documents", "application_steps", "fees", "contact_information", "missing_information", "uncertain_information", "plain_language_summary", "checklist", "source_evidence"]
    for key in required:
        data.setdefault(key, None if key in {"deadline", "fees", "contact_information"} else [] if key in {"eligibility", "required_documents", "application_steps", "missing_information", "uncertain_information", "checklist", "source_evidence"} else "")
    data["demo_mode"] = False
    data["language"] = language
    data["reading_level"] = level
    return AnalysisResult.model_validate(data).model_dump()


async def answer_question(text: str, question: str) -> str:
    if not settings.ai_base_url or not settings.ai_api_key:
        return "The configured AI provider is unavailable in demo mode, so I can’t reliably answer that from the notice. Please review the source text or confirm with the issuing organization."
    prompt = f"Answer only from this notice. If it does not contain the answer, say so. Give a brief source quote.\n\nNOTICE:\n{text[:25000]}\n\nQUESTION: {question}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(settings.ai_base_url.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {settings.ai_api_key}"}, json={"model": settings.ai_model, "temperature": 0.1, "messages": [{"role": "system", "content": "You are a grounded notice assistant. Never invent information."}, {"role": "user", "content": prompt}]})
        response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


async def translate_text(text: str, language: str) -> str:
    if not settings.ai_base_url or not settings.ai_api_key:
        raise RuntimeError("Translation needs a configured AI provider. Demo mode does not generate unverified translations.")
    prompt = f"Translate the text below into {language}. Preserve names, dates, amounts, and meaning. Return only the translation.\n\n{text[:20000]}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(settings.ai_base_url.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {settings.ai_api_key}"}, json={"model": settings.ai_model, "temperature": 0.1, "messages": [{"role": "system", "content": "Translate faithfully. Do not add facts."}, {"role": "user", "content": prompt}]})
        response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
