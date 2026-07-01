from __future__ import annotations

from scripts.deduplicate import deduplicate_jobs


def test_removes_same_job_with_similar_description(make_job):
    original = make_job(
        source_id="one",
        title="Frontend Developer",
        company="Acme",
        description="Desarrollo de aplicaciones web modernas con Vue y TypeScript.",
    )
    duplicate = make_job(
        source_id="two",
        title="Frontend Developer",
        company="Acme",
        description="Desarrollo de aplicaciones web modernas usando Vue y TypeScript.",
    )

    assert deduplicate_jobs([original, duplicate], 0.75) == [original]


def test_keeps_same_identity_when_descriptions_are_different(make_job):
    first = make_job(
        source_id="one",
        title="Técnico IT",
        company="Acme",
        description="Soporte presencial a usuarios y reparación de equipos.",
    )
    second = make_job(
        source_id="two",
        title="Técnico IT",
        company="Acme",
        description="Administración de servidores Linux y redes corporativas.",
    )

    assert deduplicate_jobs([first, second], 0.82) == [first, second]
