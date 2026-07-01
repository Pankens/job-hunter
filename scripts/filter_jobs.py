"""Clasificación de ofertas con reglas configurables."""

from __future__ import annotations

import re
from typing import Any

from scripts.normalize import comparable_text


REASON_LABELS = {
    "employment_model": "Modalidad profesional excluida",
    "mobility": "Exige carnet de conducir o vehículo propio",
    "disability": "Exige certificado de discapacidad",
    "training": "Contrato de formación, prácticas o beca",
    "sales": "Venta o captación en calle / comisiones sin base clara",
}


def contains_term(text: str, term: str) -> bool:
    normalized_term = comparable_text(term)
    pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
    return re.search(pattern, text) is not None


def classify_job(job: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    searchable = comparable_text(
        " ".join(
            [
                job.get("title", ""),
                job.get("description", ""),
                job.get("requirements", ""),
                job.get("salaryText", ""),
            ]
        )
    )
    reasons: list[str] = []

    if job.get("city") not in rules["accepted_cities"]:
        reasons.append("Ubicación fuera de las zonas aceptadas")

    for group, terms in rules["rejected_terms"].items():
        matched = [term for term in terms if contains_term(searchable, term)]
        if not matched:
            continue

        if group == "sales" and job.get("hasCommission"):
            minimum = rules["commission_rule"]["minimum_clear_base_salary_eur_month"]
            salary = job.get("salaryBaseEurMonth")
            if salary is not None and float(salary) >= float(minimum):
                non_commission_terms = [
                    term for term in matched if comparable_text(term) not in {"altas comisiones"}
                ]
                if not non_commission_terms:
                    continue

        reasons.append(REASON_LABELS[group])

    allowed_languages = {
        comparable_text(language) for language in rules["allowed_required_languages"]
    }
    rejected_languages = [
        language
        for language in job.get("requiredLanguages", [])
        if comparable_text(language) not in allowed_languages
    ]
    if rejected_languages:
        reasons.append(f"Idioma obligatorio no admitido: {', '.join(rejected_languages)}")

    matched_skills = [term for term in rules["technical_terms"] if contains_term(searchable, term)]
    result = dict(job)
    result.update(
        {
            "type": "technical" if matched_skills else "general",
            "matchedSkills": matched_skills[:5],
            "valid": not reasons,
            "rejectionReasons": list(dict.fromkeys(reasons)),
        }
    )
    return result


def filter_jobs(jobs: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    return [classify_job(job, rules) for job in jobs]
