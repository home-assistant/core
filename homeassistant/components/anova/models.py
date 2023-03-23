"""Dataclass models for the Anova integration."""
from dataclasses import dataclass

from anova_wifi import AnovaPrecisionCooker

from .coordinator import AnovaCoordinator


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    precision_cookers: list[AnovaPrecisionCooker]
    coordinators: list[AnovaCoordinator]
