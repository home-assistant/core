"""Dataclass models for the Anova integration."""

from dataclasses import dataclass

from anova_wifi import AnovaApi

from .coordinator import AnovaCoordinator


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    coordinators: list[AnovaCoordinator]
    api: AnovaApi
