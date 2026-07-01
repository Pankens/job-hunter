from __future__ import annotations

import pytest

from scripts.filter_jobs import classify_job


@pytest.mark.parametrize(
    ("requirements", "reason_fragment"),
    [
        ("Imprescindible carnet de conducir B.", "carnet de conducir B"),
        ("Alta como autónomo mediante contrato mercantil.", "Modalidad profesional excluida"),
        ("Contrato de formación con periodo de prácticas.", "formación, prácticas o beca"),
        ("Venta fría y captación a pie de calle.", "Venta fría, captación"),
        ("Imprescindible certificado de discapacidad.", "certificado de discapacidad"),
    ],
)
def test_rejects_hard_exclusions(make_job, rules, requirements, reason_fragment):
    result = classify_job(make_job(requirements=requirements), rules)

    assert result["status"] == "rejected"
    assert result["valid"] is False
    assert any(reason_fragment in reason for reason in result["reject_reasons"])


def test_rejects_required_language_other_than_spanish_or_english(make_job, rules):
    result = classify_job(
        make_job(
            requirements="Alemán C1 obligatorio.",
            required_languages=["alemán"],
        ),
        rules,
    )

    assert result["status"] == "rejected"
    assert any("alemán" in reason for reason in result["reject_reasons"])


def test_accepts_technical_vue_typescript_offer(make_job, rules):
    result = classify_job(
        make_job(
            title="Frontend Developer Vue",
            description="Desarrollo de interfaces web con Vue 3 y TypeScript.",
            requirements="Vue, TypeScript, HTML y CSS.",
        ),
        rules,
    )

    assert result["status"] == "valid"
    assert result["type"] == "technical"
    assert {"vue", "typescript"}.issubset(result["matched_skills"])
    assert result["reject_reasons"] == []
    assert result["match_reasons"]
    assert isinstance(result["warnings"], list)


def test_accepts_general_offer_without_red_flags(make_job, rules):
    result = classify_job(make_job(), rules)

    assert result["status"] == "valid"
    assert result["type"] == "general"
    assert result["reject_reasons"] == []
    assert "Oferta general" in " ".join(result["match_reasons"])


def test_rejects_location_outside_allowed_cities(make_job, rules):
    result = classify_job(make_job(city="Madrid", location="Madrid"), rules)

    assert result["status"] == "rejected"
    assert any("Ubicación no admitida" in reason for reason in result["reject_reasons"])


def test_rejects_commission_below_minimum_base_salary(make_job, rules):
    result = classify_job(
        make_job(
            requirements="Salario base más comisiones.",
            salary_text="799 € brutos/mes + comisiones",
            salary_base_eur_month=799,
            has_commission=True,
        ),
        rules,
    )

    assert result["status"] == "rejected"
    assert any("al menos 800 €/mes" in reason for reason in result["reject_reasons"])


def test_accepts_commission_with_clear_minimum_base_salary(make_job, rules):
    result = classify_job(
        make_job(
            requirements="Salario base más comisiones.",
            salary_text="800 € brutos/mes + comisiones",
            salary_base_eur_month=800,
            has_commission=True,
        ),
        rules,
    )

    assert result["status"] == "valid"
    assert any("Comisiones admitidas" in reason for reason in result["match_reasons"])
    assert any("parte variable" in warning for warning in result["warnings"])


def test_rejects_commission_only_even_with_reported_base(make_job, rules):
    result = classify_job(
        make_job(
            requirements="Retribución basada solo en comisiones.",
            salary_text="Solo comisiones",
            salary_base_eur_month=1200,
            has_commission=True,
        ),
        rules,
    )

    assert result["status"] == "rejected"
    assert any("solo comisiones" in reason for reason in result["reject_reasons"])
