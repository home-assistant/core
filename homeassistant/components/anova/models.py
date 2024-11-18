"""Dataclass models for the Anova integration."""

from dataclasses import dataclass

from anova_wifi import AnovaApi

from homeassistant.config_entries import ConfigEntry

from .coordinator import AnovaCoordinator

type AnovaConfigEntry = ConfigEntry[AnovaData]


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    coordinators: list[AnovaCoordinator]
    api: AnovaApi
