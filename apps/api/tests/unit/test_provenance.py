from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from razzle_api.api.schemas.provenance import ProvenanceMeta, ProvenanceSource
from razzle_api.core.provenance import build_meta
from razzle_api.domain.scoring.compiler import CoverageReport

AS_OF = datetime(2026, 7, 22, 12, 30, tzinfo=UTC)


def test_build_meta_is_json_ready_and_omits_unset_optionals() -> None:
    payload = build_meta(
        revision="revision-7",
        sources=(
            ProvenanceSource(name="nflverse", as_of=AS_OF, version="2026.07"),
            {"name": "sleeper", "as_of": AS_OF},
        ),
        coverage=CoverageReport(status="full", supported_keys=["rec", "pass_yd"]),
        assumptions=("regular season only",),
    )

    assert payload["revision"] == "revision-7"
    assert payload["sources"] == [
        {
            "name": "nflverse",
            "as_of": "2026-07-22T12:30:00Z",
            "version": "2026.07",
        },
        {"name": "sleeper", "as_of": "2026-07-22T12:30:00Z"},
    ]
    assert payload["coverage"] == {
        "status": "full",
        "supported_keys": ["rec", "pass_yd"],
        "unsupported_keys": [],
        "ignored_zero_keys": [],
    }
    assert payload["assumptions"] == ["regular season only"]
    assert "model_version" not in payload


def test_build_meta_accepts_single_models_and_mappings() -> None:
    source = ProvenanceSource(name="nflverse", as_of=AS_OF)

    from_model = build_meta(sources=source, model_version="line-v0")
    from_mapping = build_meta(sources={"name": "sleeper", "as_of": AS_OF})
    empty = build_meta()

    assert from_model["sources"][0]["name"] == "nflverse"
    assert from_model["model_version"] == "line-v0"
    assert from_mapping["sources"][0]["name"] == "sleeper"
    assert empty == {"sources": [], "assumptions": []}


def test_provenance_models_and_builder_forbid_extras() -> None:
    with pytest.raises(ValidationError):
        ProvenanceSource.model_validate({"name": "nflverse", "as_of": AS_OF, "invented": True})

    with pytest.raises(ValidationError):
        ProvenanceMeta.model_validate({"sources": [], "invented": True})

    with pytest.raises(ValidationError):
        build_meta(coverage={"status": "full", "invented": True})

    with pytest.raises(ValidationError):
        build_meta(
            sources=(
                {
                    "name": "nflverse",
                    "as_of": AS_OF,
                    "invented": "not allowed",
                },
            )
        )
