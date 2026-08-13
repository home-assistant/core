"""Definitions for TrueNAS update entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.update import UpdateEntityDescription

from .entity import TrueNASEntityDescription


@dataclass(frozen=True, kw_only=True)
class TrueNASUpdateEntityDescription(UpdateEntityDescription, TrueNASEntityDescription):
    """Class describing entities."""

    title: str | None = None
    data_attribute: str = "available"


SENSOR_TYPES: tuple[TrueNASUpdateEntityDescription, ...] = (
    TrueNASUpdateEntityDescription(
        key="system_update",
        name=None,
        ha_group="System",
        title="TrueNAS",
        data_path="system_info",
        data_attribute="update_available",
        data_name=None,
        data_uid=None,
        data_reference=None,
        data_attributes_list=(
            "update_date",
            "update_profile",
            "update_train",
            "update_filename",
        ),
        func="TrueNASUpdate",
    ),
    TrueNASUpdateEntityDescription(
        key="app_update",
        name=None,
        ha_group="Apps",
        data_path="app",
        data_attribute="update_available",
        data_name="name",
        data_uid="id",
        data_reference="id",
        func="TrueNASAppUpdate",
    ),
)

SENSOR_SERVICES: tuple[Any, ...] = ()
