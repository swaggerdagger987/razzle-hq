"""Validated construction of JSON-ready provenance envelopes."""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from razzle_api.api.schemas.provenance import ProvenanceMeta

SourceInput = BaseModel | Mapping[str, Any]
CoverageInput = BaseModel | Mapping[str, Any]


def build_meta(
    *,
    revision: str | None = None,
    sources: SourceInput | Sequence[SourceInput] = (),
    coverage: CoverageInput | None = None,
    assumptions: Sequence[str] = (),
    model_version: str | None = None,
) -> dict[str, Any]:
    source_items = _source_items(sources)
    coverage_payload = _mapping_payload(coverage) if coverage is not None else None
    if isinstance(assumptions, (str, bytes)):
        raise TypeError("assumptions must be a sequence of strings")
    meta = ProvenanceMeta.model_validate(
        {
            "revision": revision,
            "sources": source_items,
            "coverage": coverage_payload,
            "assumptions": list(assumptions),
            "model_version": model_version,
        }
    )
    return meta.model_dump(mode="json", exclude_none=True)


def _source_items(
    sources: SourceInput | Sequence[SourceInput],
) -> list[dict[str, Any]]:
    if isinstance(sources, BaseModel):
        return [sources.model_dump(mode="python")]
    if isinstance(sources, Mapping):
        return [dict(sources)]
    if isinstance(sources, (str, bytes)):
        raise TypeError("sources must be source models, mappings, or a sequence of them")
    return [
        source.model_dump(mode="python") if isinstance(source, BaseModel) else dict(source)
        for source in sources
    ]


def _mapping_payload(value: CoverageInput) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    return dict(value)
