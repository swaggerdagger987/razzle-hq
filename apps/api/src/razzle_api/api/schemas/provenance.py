"""Provenance envelope shared by decision-bearing API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    as_of: datetime
    version: str | None = None


class ProvenanceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str | None = None
    sources: list[ProvenanceSource] = Field(default_factory=list)
    coverage: dict[str, Any] | None = None
    assumptions: list[str] = Field(default_factory=list)
    model_version: str | None = None
