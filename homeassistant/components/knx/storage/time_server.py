"""Time server controller for KNX integration."""

from __future__ import annotations

from typing import Any, TypedDict

import voluptuous as vol
from xknx import XKNX

from ..expose import KnxExposeTime, create_time_server_exposures
from .entity_store_validation import validate_config_store_data
from .knx_selector import GASelector


class KNXTimeServerStoreModel(TypedDict, total=False):
    """Represent KNX time server configuration store data."""

    time: dict[str, Any] | None
    date: dict[str, Any] | None
    datetime: dict[str, Any] | None


TIME_SERVER_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("time"): GASelector(
            state=False, passive=False, valid_dpt="10.001"
        ),
        vol.Optional("date"): GASelector(
            state=False, passive=False, valid_dpt="11.001"
        ),
        vol.Optional("datetime"): GASelector(
            state=False, passive=False, valid_dpt="19.001"
        ),
    }
)


def validate_time_server_data(time_server_data: dict) -> KNXTimeServerStoreModel:
    """Validate time server data.

    Return validated data or raise EntityStoreValidationException.
    """

    return validate_config_store_data(TIME_SERVER_CONFIG_SCHEMA, time_server_data)  # type: ignore[return-value]


class TimeServerController:
    """Controller class for UI time exposures."""

    def __init__(self) -> None:
        """Initialize time server controller."""
        self.time_exposes: list[KnxExposeTime] = []

    def stop(self) -> None:
        """Shutdown time server controller."""
        for expose in self.time_exposes:
            expose.async_remove()
        self.time_exposes.clear()

    def start(self, xknx: XKNX, config: KNXTimeServerStoreModel) -> None:
        """Update time server configuration."""
        if self.time_exposes:
            self.stop()
        self.time_exposes = create_time_server_exposures(xknx, config)
