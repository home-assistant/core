"""Demo platform that offers a fake infrared fan entity."""

from typing import Any

from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    INFRARED_CMD_POWER_OFF,
    INFRARED_CMD_POWER_ON,
    INFRARED_CMD_SPEED_HIGH,
    INFRARED_CMD_SPEED_LOW,
    INFRARED_CMD_SPEED_MEDIUM,
    INFRARED_FAN_ADDRESS,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared fan platform."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "infrared_fan":
            continue
        if subentry.data.get(CONF_INFRARED_ENTITY_ID) is None:
            continue
        async_add_entities(
            [
                DemoInfraredFan(
                    subentry_id=subentry_id,
                    device_name=subentry.title,
                    infrared_emitter_entity_id=subentry.data[CONF_INFRARED_ENTITY_ID],
                )
            ],
            config_subentry_id=subentry_id,
        )


class DemoInfraredFan(InfraredEmitterConsumerEntity, FanEntity):
    """Representation of a demo infrared fan entity."""

    _attr_has_entity_name = True
    _attr_name = None
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
        infrared_emitter_entity_id: str,
    ) -> None:
        """Initialize the demo infrared fan entity."""
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._attr_unique_id = subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=device_name,
        )
        self._attr_percentage = 0

    async def _send_fan_command(self, command_code: int) -> None:
        """Send an IR command using the NEC protocol."""
        await self._send_command(
            NECCommand(
                address=INFRARED_FAN_ADDRESS,
                command=command_code,
                modulation=38000,
            )
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
        await self._send_fan_command(INFRARED_CMD_POWER_ON)
        self._attr_percentage = 33
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._send_fan_command(INFRARED_CMD_POWER_OFF)
        self._attr_percentage = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        if percentage <= 33:
            await self._send_fan_command(INFRARED_CMD_SPEED_LOW)
        elif percentage <= 66:
            await self._send_fan_command(INFRARED_CMD_SPEED_MEDIUM)
        else:
            await self._send_fan_command(INFRARED_CMD_SPEED_HIGH)
        self._attr_percentage = percentage
        self.async_write_ha_state()
