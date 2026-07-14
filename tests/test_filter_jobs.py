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
            description=(
                "Desarrollo de interfaces web modernas con Vue 3 y TypeScript, "
                "colaborando con producto, diseno y backend en un equipo tecnico."
            ),
            requirements="Vue, TypeScript, HTML y CSS.",
        ),
        rules,
    )

    assert result["status"] == "valid"
    assert result["type"] == "technical"
    assert "frontend" in result["matched_skills"]
    assert result["reject_reasons"] == []
    assert result["match_reasons"]
    assert isinstance(result["warnings"], list)


def test_accepts_general_offer_without_red_flags(make_job, rules):
    result = classify_job(make_job(), rules)

    assert result["status"] == "valid"
    assert result["type"] == "general"
    assert result["reject_reasons"] == []
    assert "perfil general" in " ".join(result["match_reasons"])


def test_rejects_offer_outside_configured_profiles(make_job, rules):
    result = classify_job(
        make_job(
            title="Account Executive",
            description=(
                "Manage enterprise prospects, coordinate sales cycles, negotiate contracts "
                "and report pipeline progress to revenue leadership every week."
            ),
            requirements="Sales experience and pipeline management.",
        ),
        rules,
    )

    assert result["status"] == "rejected"
    assert any("perfiles general o tecnico" in reason for reason in result["reject_reasons"])


def test_rejects_navigation_like_job_without_company_description_or_direct_url(make_job, rules):
    result = classify_job(
        make_job(
            title="Barcelona",
            company="",
            description="",
            url="https://example.test/ofertas-trabajo/barcelona/dependiente",
            direct_url=False,
        ),
        rules,
    )

    assert result["status"] == "rejected"
    assert any("titulo de puesto" in reason for reason in result["reject_reasons"])
    assert any("empresa no identificable" in reason for reason in result["reject_reasons"])
    assert any("URL no parece" in reason for reason in result["reject_reasons"])
    assert any("descripcion insuficiente" in reason for reason in result["reject_reasons"])


def test_accepts_remote_technical_offer_with_real_company_and_description(make_job, rules):
    result = classify_job(
        make_job(
            title="Frontend Engineer Vue",
            company="Remote SaaS",
            city="Remote",
            location="Remote",
            remote=True,
            description=(
                "Build Vue and TypeScript interfaces for a remote product team, "
                "collaborating with design, backend engineers and customer support."
            ),
            requirements="Vue, TypeScript, HTML and CSS.",
        ),
        rules,
    )

    assert result["status"] == "valid"
    assert result["type"] == "technical"
    assert any("remota" in reason for reason in result["match_reasons"])


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
