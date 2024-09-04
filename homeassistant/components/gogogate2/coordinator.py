"""Coordinator for GogoGate2 component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging

from ismartgate import AbstractGateApi, GogoGate2InfoResponse, ISmartGateInfoResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class DeviceDataUpdateCoordinator(
    DataUpdateCoordinator[GogoGate2InfoResponse | ISmartGateInfoResponse]
):
    """Manages polling for state changes from the device."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api: AbstractGateApi,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Callable[
            [], Awaitable[GogoGate2InfoResponse | ISmartGateInfoResponse]
        ]
        | None = None,
        request_refresh_debouncer: Debouncer | None = None,
    ) -> None:
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.api = api
