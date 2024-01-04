"""Valves for the Elexa Guardian integration."""
from __future__ import annotations

from enum import StrEnum

from aioguardian.errors import GuardianError

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GuardianData, ValveControllerEntity
from .const import DOMAIN

ATTR_AVG_CURRENT = "average_current"
ATTR_CONNECTED_CLIENTS = "connected_clients"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_STATION_CONNECTED = "station_connected"
ATTR_TRAVEL_COUNT = "travel_count"

SWITCH_KIND_ONBOARD_AP = "onboard_ap"


# async def _async_close_valve(client: Client) -> None:
#     """Close the valve."""
#     await client.valve.close()


# async def _async_open_valve(client: Client) -> None:
#     """Open the valve."""
#     await client.valve.open()


# VALVE_CONTROLLER_DESCRIPTIONS = (
#     ValveControllerSwitchDescription(
#         key=SWITCH_KIND_VALVE,
#         translation_key="valve_controller",
#         icon="mdi:water",
#         api_category=API_VALVE_STATUS,
#         off_action=_async_close_valve,
#         on_action=_async_open_valve,
#     ),
# )


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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""
    data: GuardianData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ValveControllerValve(
            entry,
            data,
            ValveEntityDescription(
                key="valve",
                translation_key="valve_controller",
                icon="mdi:water",
                device_class=ValveDeviceClass.WATER,
                reports_position=True,
            ),
        )
    )


class ValveControllerValve(ValveControllerEntity, ValveEntity):
    """Define a switch related to a Guardian valve controller."""

    def __init__(
        self,
        entry: ConfigEntry,
        data: GuardianData,
        description: ValveEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data.valve_controller_coordinators, description)

        self._client = data.client

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        current_state = self.coordinator.data["state"]

        self._attr_is_closed = current_state == GuardianValveState.CLOSED

        self._attr_is_closing = current_state in (
            GuardianValveState.FINISH_CLOSING,
            GuardianValveState.CLOSING,
            GuardianValveState.START_CLOSING,
        )

        self._attr_is_opening = current_state in (
            GuardianValveState.FINISH_OPENING,
            GuardianValveState.OPENING,
            GuardianValveState.START_OPENING,
        )

        self._attr_extra_state_attributes.update(
            {
                ATTR_AVG_CURRENT: self.coordinator.data["average_current"],
                ATTR_INST_CURRENT: self.coordinator.data["instantaneous_current"],
                ATTR_INST_CURRENT_DDT: self.coordinator.data[
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self.coordinator.data["travel_count"],
            }
        )

    async def async_close_valve(self) -> None:
        """Close the valve."""
        if self._attr_is_closed or self._attr_is_closing:
            return

        try:
            async with self._client:
                await self._client.valve.close()
        except GuardianError as err:
            raise HomeAssistantError(
                f"Error while closing {self.entity_id}: {err}"
            ) from err

        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_open_valve(self) -> None:
        """Open the valve."""
        if self._attr_is_open or self._attr_is_opening:
            return

        try:
            async with self._client:
                await self._client.valve.open()
        except GuardianError as err:
            raise HomeAssistantError(
                f"Error while opening {self.entity_id}: {err}"
            ) from err

        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_valve(self) -> None:
        """Stop the valve."""
        await self._client.valve.halt()

    # async def async_turn_off(self, **kwargs: Any) -> None:
    #     """Turn the switch off."""
    #     if not self._attr_is_on:
    #         return

    #     try:
    #         async with self._client:
    #             await self.entity_description.off_action(self._client)
    #     except GuardianError as err:
    #         raise HomeAssistantError(
    #             f'Error while turning "{self.entity_id}" off: {err}'
    #         ) from err

    #     self._attr_is_on = False
    #     self.async_write_ha_state()

    # async def async_turn_on(self, **kwargs: Any) -> None:
    #     """Turn the switch on."""
    #     if self._attr_is_on:
    #         return

    #     try:
    #         async with self._client:
    #             await self.entity_description.on_action(self._client)
    #     except GuardianError as err:
    #         raise HomeAssistantError(
    #             f'Error while turning "{self.entity_id}" on: {err}'
    #         ) from err

    #     self._attr_is_on = True
    #     self.async_write_ha_state()
