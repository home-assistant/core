"""Definitions for TrueNAS switch entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntityDescription

from .entity import TrueNASEntityDescription


@dataclass(frozen=True, kw_only=True)
class TrueNASSwitchEntityDescription(SwitchEntityDescription, TrueNASEntityDescription):
    """Class describing entities."""

    data_is_on: str = "running"
    func: str = "TrueNASServiceSwitch"


SENSOR_TYPES: tuple[TrueNASSwitchEntityDescription, ...] = (
    TrueNASSwitchEntityDescription(
        key="service_switch",
        name=None,
        translation_key="service_switch",
        ha_group="Services",
        data_path="service",
        data_is_on="running",
        data_name="display_name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=("enable", "state"),
        func="TrueNASServiceSwitch",
    ),
    TrueNASSwitchEntityDescription(
        key="cloudsync_switch",
        translation_key="cloudsync_switch",
        ha_group="Cloudsync",
        data_path="cloudsync",
        data_is_on="enabled",
        data_name="description",
        data_uid=None,
        data_reference="id",
        func="TrueNASCloudsyncSwitch",
    ),
    TrueNASSwitchEntityDescription(
        key="cronjob_switch",
        translation_key="cronjob_switch",
        ha_group="Cron Jobs",
        data_path="cronjob",
        data_is_on="enabled",
        data_name="display_name",
        data_uid=None,
        data_reference="id",
        func="TrueNASCronjobSwitch",
    ),
)

SENSOR_SERVICES: tuple[Any, ...] = ()
