"""Time server controller for KNX integration."""

from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

import probatio
from xknx import XKNX

from ..expose import KnxExposeTime, create_time_server_exposures
from .entity_store_validation import validate_config_store_data
from .knx_selector import GroupAddressConfig, ga


class KNXTimeServerStoreModel(TypedDict, total=False):
    """Represent KNX time server configuration store data."""

    time: dict[str, Any] | None
    date: dict[str, Any] | None
    datetime: dict[str, Any] | None


@dataclass(kw_only=True, slots=True)
class TimeServerConfig:
    """Group addresses the time server sends the current time, date and datetime to."""

    time: Annotated[
        GroupAddressConfig | None, ga(state=False, passive=False, valid_dpt="10.001")
    ] = None
    date: Annotated[
        GroupAddressConfig | None, ga(state=False, passive=False, valid_dpt="11.001")
    ] = None
    datetime: Annotated[
        GroupAddressConfig | None, ga(state=False, passive=False, valid_dpt="19.001")
    ] = None


TIME_SERVER_CONFIG_SCHEMA = probatio.DataclassSchema(TimeServerConfig)


def validate_time_server_data(time_server_data: dict) -> TimeServerConfig:
    """Validate time server data.

    Return validated data or raise EntityStoreValidationException.
    """

    return validate_config_store_data(TIME_SERVER_CONFIG_SCHEMA, time_server_data)


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

    def start(self, xknx: XKNX, config: TimeServerConfig) -> None:
        """Update time server configuration."""
        if self.time_exposes:
            self.stop()
        self.time_exposes = create_time_server_exposures(xknx, config)
