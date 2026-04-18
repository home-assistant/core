"""Demo platform that offers a fake infrared fan entity."""

from __future__ import annotations

from typing import Any

import infrared_protocols

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN

PARALLEL_UPDATES = 0

DUMMY_FAN_ADDRESS = 0x1234
DUMMY_CMD_POWER_ON = 0x01
DUMMY_CMD_POWER_OFF = 0x02
DUMMY_CMD_SPEED_LOW = 0x03
DUMMY_CMD_SPEED_MEDIUM = 0x04
DUMMY_CMD_SPEED_HIGH = 0x05


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared fan platform."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "infrared_fan":
            continue
        async_add_entities(
            [
                DemoInfraredFan(
                    subentry_id=subentry_id,
                    device_name=subentry.title,
                    infrared_entity_id=subentry.data[CONF_INFRARED_ENTITY_ID],
                )
            ],
            config_subentry_id=subentry_id,
        )


class DemoInfraredFan(FanEntity):
    """Representation of a demo infrared fan entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_speed_count = 3
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(
        self,
        subentry_id: str,
        device_name: str,
        infrared_entity_id: str,
    ) -> None:
        """Initialize the demo infrared fan entity."""
        self._infrared_entity_id = infrared_entity_id
        self._attr_unique_id = subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
        )
        self._attr_percentage = 0

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared entity state changes."""
        await super().async_added_to_hass()

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle infrared entity state changes."""
            new_state = event.data["new_state"]
            self._attr_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._infrared_entity_id], _async_ir_state_changed
            )
        )

        # Set initial availability based on current infrared entity state
        ir_state = self.hass.states.get(self._infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

    async def _send_command(self, command_code: int) -> None:
        """Send an IR command using the NEC protocol."""
        command = infrared_protocols.NECCommand(
            address=DUMMY_FAN_ADDRESS,
            command=command_code,
            modulation=38000,
        )
        await async_send_command(
            self.hass, self._infrared_entity_id, command, context=self._context
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._send_command(DUMMY_CMD_POWER_ON)
        self._attr_percentage = 33
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._send_command(DUMMY_CMD_POWER_OFF)
        self._attr_percentage = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        if percentage <= 33:
            await self._send_command(DUMMY_CMD_SPEED_LOW)
        elif percentage <= 66:
            await self._send_command(DUMMY_CMD_SPEED_MEDIUM)
        else:
            await self._send_command(DUMMY_CMD_SPEED_HIGH)

        self._attr_percentage = percentage
        self.async_write_ha_state()
