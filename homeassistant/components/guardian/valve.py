"""Valves for the Elexa Guardian integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aioguardian import Client

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GuardianConfigEntry, GuardianData
from .const import API_VALVE_STATUS
from .entity import ValveControllerEntity, ValveControllerEntityDescription
from .util import convert_exceptions_to_homeassistant_error

VALVE_KIND_VALVE = "valve"


class GuardianValveState(StrEnum):
    """States of a valve."""

    CLOSED = "closed"
    CLOSING = "closing"
    FINISH_CLOSING = "finish_closing"
    FINISH_OPENING = "finish_opening"
    OPEN = "open"
    OPENING = "opening"
    START_CLOSING = "start_closing"
    START_OPENING = "start_opening"


@dataclass(frozen=True, kw_only=True)
class ValveControllerValveDescription(
    ValveEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller valve."""

    is_closed_fn: Callable[[dict[str, Any]], bool]
    is_closing_fn: Callable[[dict[str, Any]], bool]
    is_opening_fn: Callable[[dict[str, Any]], bool]
    close_coro_fn: Callable[[Client], Coroutine[Any, Any, None]]
    halt_coro_fn: Callable[[Client], Coroutine[Any, Any, None]]
    open_coro_fn: Callable[[Client], Coroutine[Any, Any, None]]


async def async_close_valve(client: Client) -> None:
    """Close the valve."""
    async with client:
        await client.valve.close()


async def async_halt_valve(client: Client) -> None:
    """Halt the valve."""
    async with client:
        await client.valve.halt()


async def async_open_valve(client: Client) -> None:
    """Open the valve."""
    async with client:
        await client.valve.open()


@callback
def is_closing(data: dict[str, Any]) -> bool:
    """Return if the valve is closing."""
    return data["state"] in (
        GuardianValveState.CLOSING,
        GuardianValveState.FINISH_CLOSING,
        GuardianValveState.START_CLOSING,
    )


@callback
def is_opening(data: dict[str, Any]) -> bool:
    """Return if the valve is opening."""
    return data["state"] in (
        GuardianValveState.OPENING,
        GuardianValveState.FINISH_OPENING,
        GuardianValveState.START_OPENING,
    )


VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerValveDescription(
        key=VALVE_KIND_VALVE,
        translation_key="valve_controller",
        device_class=ValveDeviceClass.WATER,
        api_category=API_VALVE_STATUS,
        is_closed_fn=lambda data: data["state"] == GuardianValveState.CLOSED,
        is_closing_fn=is_closing,
        is_opening_fn=is_opening,
        close_coro_fn=async_close_valve,
        halt_coro_fn=async_halt_valve,
        open_coro_fn=async_open_valve,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuardianConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guardian switches based on a config entry."""
    data = entry.runtime_data

    async_add_entities(
        ValveControllerValve(entry, data, description)
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    )


class ValveControllerValve(ValveControllerEntity, ValveEntity):
    """Define a switch related to a Guardian valve controller."""

    _attr_supported_features = (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE | ValveEntityFeature.STOP
    )
    entity_description: ValveControllerValveDescription

    def __init__(
        self,
        entry: GuardianConfigEntry,
        data: GuardianData,
        description: ValveControllerValveDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data.valve_controller_coordinators, description)

        self._client = data.client

    @property
    def is_closing(self) -> bool:
        """Return if the valve is closing or not."""
        return self.entity_description.is_closing_fn(self.coordinator.data)

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed or not."""
        return self.entity_description.is_closed_fn(self.coordinator.data)

    @property
    def is_opening(self) -> bool:
        """Return if the valve is opening or not."""
        return self.entity_description.is_opening_fn(self.coordinator.data)

    @convert_exceptions_to_homeassistant_error
    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.entity_description.close_coro_fn(self._client)
        await self.coordinator.async_request_refresh()

    @convert_exceptions_to_homeassistant_error
    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.entity_description.open_coro_fn(self._client)
        await self.coordinator.async_request_refresh()

    @convert_exceptions_to_homeassistant_error
    async def async_stop_valve(self) -> None:
        """Stop the valve."""
        await self.entity_description.halt_coro_fn(self._client)
        await self.coordinator.async_request_refresh()
