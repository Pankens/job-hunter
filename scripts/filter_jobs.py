"""Clasifica ofertas normalizadas aplicando las reglas duras del usuario."""

from __future__ import annotations

import re
from typing import Any

from scripts.normalize import comparable_text


REASON_LABELS = {
    "employment_model": "Modalidad profesional excluida",
    "mobility": "Exige carnet de conducir B o vehículo propio",
    "disability": "Exige certificado de discapacidad",
    "training": "Contrato de formación, prácticas o beca",
    "street_sales": "Venta fría, captación o trabajo en la calle",
}


def contains_term(text: str, term: str) -> bool:
    """Busca términos completos sin confundir `IT` con partes de otras palabras."""
    normalized_term = comparable_text(term)
    pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
    return re.search(pattern, text) is not None


def _searchable_text(job: dict[str, Any]) -> str:
    return comparable_text(
        " ".join(
            str(job.get(field, ""))
            for field in ("title", "description", "requirements", "salaryText", "salary_text")
        )
    )


def _monthly_salary(job: dict[str, Any]) -> float | None:
    value = job.get("salaryBaseEurMonth", job.get("salary_base_eur_month"))
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_languages(job: dict[str, Any], searchable: str, rules: dict[str, Any]) -> list[str]:
    language_rule = rules["language_rule"]
    explicit = job.get("requiredLanguages", job.get("required_languages", [])) or []
    detected = [str(language).strip().lower() for language in explicit if str(language).strip()]

    has_mandatory_marker = any(
        contains_term(searchable, marker) for marker in language_rule["mandatory_markers"]
    )
    if has_mandatory_marker:
        for language in language_rule["known_other_languages"]:
            if contains_term(searchable, language) and language.lower() not in detected:
                detected.append(language.lower())
    return detected


def _commission_result(
    job: dict[str, Any], searchable: str, rules: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    commission_rule = rules["commission_rule"]
    always_rejected = [
        term for term in commission_rule["always_rejected_terms"] if contains_term(searchable, term)
    ]
    commission_detected = bool(job.get("hasCommission", job.get("has_commission", False))) or any(
        contains_term(searchable, term) for term in commission_rule["indicators"]
    )
    if not commission_detected and not always_rejected:
        return [], [], []

    if always_rejected:
        return (
            [f"Retribución excluida: {', '.join(always_rejected)}"],
            [],
            [],
        )

    salary = _monthly_salary(job)
    minimum = float(commission_rule["minimum_clear_base_salary_eur_month"])
    if salary is None or salary < minimum:
        return (
            [f"Comisiones sin salario base claro de al menos {minimum:.0f} €/mes"],
            [],
            [],
        )

    return (
        [],
        [f"Comisiones admitidas con salario base de {salary:.0f} €/mes"],
        ["La oferta incluye una parte variable o comisiones"],
    )


def classify_job(job: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    searchable = _searchable_text(job)
    reject_reasons: list[str] = []
    match_reasons: list[str] = []
    warnings: list[str] = []

    accepted_cities = {
        comparable_text(city): city for city in rules["accepted_cities"]
    }
    normalized_city = comparable_text(job.get("city", ""))
    if normalized_city not in accepted_cities:
        reject_reasons.append(
            f"Ubicación no admitida: {job.get('city') or 'no indicada'}"
        )
    else:
        match_reasons.append(f"Ubicación admitida: {accepted_cities[normalized_city]}")

    for group, terms in rules["rejected_terms"].items():
        matched = [term for term in terms if contains_term(searchable, term)]
        if matched:
            reject_reasons.append(f"{REASON_LABELS[group]}: {', '.join(matched)}")

    language_rule = rules["language_rule"]
    allowed_languages = {
        comparable_text(language) for language in language_rule["allowed_required_languages"]
    }
    rejected_languages = [
        language
        for language in _required_languages(job, searchable, rules)
        if comparable_text(language) not in allowed_languages
    ]
    if rejected_languages:
        reject_reasons.append(
            f"Idioma obligatorio distinto de español o inglés: {', '.join(rejected_languages)}"
        )

    commission_rejects, commission_matches, commission_warnings = _commission_result(
        job, searchable, rules
    )
    reject_reasons.extend(commission_rejects)
    match_reasons.extend(commission_matches)
    warnings.extend(commission_warnings)

    matched_skills = [
        term for term in rules["technical_terms"] if contains_term(searchable, term)
    ]
    job_type = "technical" if matched_skills else "general"
    if matched_skills:
        match_reasons.append(
            f"Coincide con el perfil técnico: {', '.join(matched_skills[:5])}"
        )
    else:
        match_reasons.append("Oferta general sin requisitos técnicos específicos")

    if job.get("source") == "indeed":
        warnings.append("Indeed está configurada como fuente experimental")
    if not job.get("salaryText", job.get("salary_text", "")):
        warnings.append("La oferta no informa de un salario claro")

    unique_rejects = list(dict.fromkeys(reject_reasons))
    unique_matches = list(dict.fromkeys(match_reasons))
    unique_warnings = list(dict.fromkeys(warnings))
    is_valid = not unique_rejects

    result = dict(job)
    result.update(
        {
            "type": job_type,
            "matched_skills": matched_skills[:5],
            "valid": is_valid,
            "status": "valid" if is_valid else "rejected",
            "reject_reasons": unique_rejects,
            "match_reasons": unique_matches,
            "warnings": unique_warnings,
        }
    )
    return result


def filter_jobs(jobs: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Clasifica todas las ofertas sin eliminar las rechazadas del resultado."""
    return [classify_job(job, rules) for job in jobs]
