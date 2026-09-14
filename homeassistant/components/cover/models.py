"""Data models for the cover integration."""

from dataclasses import dataclass

from homeassistant.helpers.automation import DomainSpec


@dataclass(frozen=True, slots=True)
class CoverDomainSpec(DomainSpec):
    """DomainSpec with a target value for comparison."""

    target_value: str | bool | None = None
