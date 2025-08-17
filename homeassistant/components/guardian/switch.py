"""Switches for the Elexa Guardian integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aioguardian import Client

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GuardianConfigEntry, GuardianData
from .const import API_VALVE_STATUS, API_WIFI_STATUS
from .entity import ValveControllerEntity, ValveControllerEntityDescription
from .util import convert_exceptions_to_homeassistant_error
from .valve import GuardianValveState

ATTR_AVG_CURRENT = "average_current"
ATTR_CONNECTED_CLIENTS = "connected_clients"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_STATION_CONNECTED = "station_connected"
ATTR_TRAVEL_COUNT = "travel_count"

SWITCH_KIND_ONBOARD_AP = "onboard_ap"
SWITCH_KIND_VALVE = "valve"


@dataclass(frozen=True, kw_only=True)
class ValveControllerSwitchDescription(
    SwitchEntityDescription, ValveControllerEntityDescription
):
    """Describe a Guardian valve controller switch."""

    extra_state_attributes_fn: Callable[[dict[str, Any]], Mapping[str, Any]]
    is_on_fn: Callable[[dict[str, Any]], bool]
    off_fn: Callable[[Client], Awaitable]
    on_fn: Callable[[Client], Awaitable]


async def _async_disable_ap(client: Client) -> None:
    """Disable the onboard AP."""
    async with client:
        await client.wifi.disable_ap()


async def _async_enable_ap(client: Client) -> None:
    """Enable the onboard AP."""
    async with client:
        await client.wifi.enable_ap()


async def _async_close_valve(client: Client) -> None:
    """Close the valve."""
    async with client:
        await client.valve.close()


async def _async_open_valve(client: Client) -> None:
    """Open the valve."""
    async with client:
        await client.valve.open()


@callback
def is_open(data: dict[str, Any]) -> bool:
    """Return if the valve is opening."""
    return data["state"] in (
        GuardianValveState.FINISH_OPENING,
        GuardianValveState.OPEN,
        GuardianValveState.OPENING,
        GuardianValveState.START_OPENING,
    )


VALVE_CONTROLLER_DESCRIPTIONS = (
    ValveControllerSwitchDescription(
        key=SWITCH_KIND_ONBOARD_AP,
        translation_key="onboard_access_point",
        entity_category=EntityCategory.CONFIG,
        extra_state_attributes_fn=lambda data: {
            ATTR_CONNECTED_CLIENTS: data.get("ap_clients"),
            ATTR_STATION_CONNECTED: data["station_connected"],
        },
        api_category=API_WIFI_STATUS,
        is_on_fn=lambda data: data["ap_enabled"],
        off_fn=_async_disable_ap,
        on_fn=_async_enable_ap,
    ),
    ValveControllerSwitchDescription(
        key=SWITCH_KIND_VALVE,
        translation_key="valve_controller",
        api_category=API_VALVE_STATUS,
        extra_state_attributes_fn=lambda data: {
            ATTR_AVG_CURRENT: data["average_current"],
            ATTR_INST_CURRENT: data["instantaneous_current"],
            ATTR_INST_CURRENT_DDT: data["instantaneous_current_ddt"],
            ATTR_TRAVEL_COUNT: data["travel_count"],
        },
        is_on_fn=is_open,
        off_fn=_async_close_valve,
        on_fn=_async_open_valve,
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
        ValveControllerSwitch(entry, data, description)
        for description in VALVE_CONTROLLER_DESCRIPTIONS
    )


class ValveControllerSwitch(ValveControllerEntity, SwitchEntity):
    """Define a switch related to a Guardian valve controller."""

    entity_description: ValveControllerSwitchDescription

    def __init__(
        self,
        entry: GuardianConfigEntry,
        data: GuardianData,
        description: ValveControllerSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data.valve_controller_coordinators, description)

        self._client = data.client

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        return self.entity_description.extra_state_attributes_fn(self.coordinator.data)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @convert_exceptions_to_homeassistant_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.off_fn(self._client)
        await self.coordinator.async_request_refresh()

    @convert_exceptions_to_homeassistant_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.on_fn(self._client)
        await self.coordinator.async_request_refresh()
