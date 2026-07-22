"""Provenance envelope shared by decision-bearing API responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from razzle_api.domain.scoring.compiler import CoverageReport


class ProvenanceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    as_of: datetime
    version: str | None = None


class ProvenanceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str | None = None
    sources: list[ProvenanceSource] = Field(default_factory=list)
    coverage: CoverageReport | None = None
    assumptions: list[str] = Field(default_factory=list)
    model_version: str | None = None
