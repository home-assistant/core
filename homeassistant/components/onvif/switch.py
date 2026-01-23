"""ONVIF switches for controlling cameras."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .device import ONVIFDevice
from .entity import ONVIFBaseEntity
from .models import Profile


@dataclass(frozen=True, kw_only=True)
class ONVIFSwitchEntityDescription(SwitchEntityDescription):
    """Describes ONVIF switch entity."""

    turn_on_fn: Callable[
        [ONVIFDevice], Callable[[Profile, Any], Coroutine[Any, Any, None]]
    ]
    turn_off_fn: Callable[
        [ONVIFDevice], Callable[[Profile, Any], Coroutine[Any, Any, None]]
    ]
    turn_on_data: Any
    turn_off_data: Any
    supported_fn: Callable[[ONVIFDevice], bool]


SWITCHES: tuple[ONVIFSwitchEntityDescription, ...] = (
    ONVIFSwitchEntityDescription(
        key="autofocus",
        translation_key="autofocus",
        turn_on_data={"Focus": {"AutoFocusMode": "AUTO"}},
        turn_off_data={"Focus": {"AutoFocusMode": "MANUAL"}},
        turn_on_fn=lambda device: device.async_set_imaging_settings,
        turn_off_fn=lambda device: device.async_set_imaging_settings,
        supported_fn=lambda device: device.capabilities.imaging,
    ),
    ONVIFSwitchEntityDescription(
        key="ir_lamp",
        translation_key="ir_lamp",
        turn_on_data={"IrCutFilter": "OFF"},
        turn_off_data={"IrCutFilter": "ON"},
        turn_on_fn=lambda device: device.async_set_imaging_settings,
        turn_off_fn=lambda device: device.async_set_imaging_settings,
        supported_fn=lambda device: device.capabilities.imaging,
    ),
    ONVIFSwitchEntityDescription(
        key="wiper",
        translation_key="wiper",
        turn_on_data="tt:Wiper|On",
        turn_off_data="tt:Wiper|Off",
        turn_on_fn=lambda device: device.async_run_aux_command,
        turn_off_fn=lambda device: device.async_run_aux_command,
        supported_fn=lambda device: device.capabilities.ptz,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a ONVIF switch platform."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    # Add predefined switches
    entities = [
        ONVIFSwitch(device, description)
        for description in SWITCHES
        if description.supported_fn(device)
    ]

    # Add relay output switches
    if device.capabilities.deviceio and device.capabilities.relay_outputs > 0:
        relays = await device.async_get_relay_outputs()
        for relay in relays:
            entities.append(ONVIFRelaySwitch(device, relay))

    async_add_entities(entities)


class ONVIFSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch."""

    entity_description: ONVIFSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: ONVIFDevice, description: ONVIFSwitchEntityDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(device)
        self._attr_unique_id = f"{self.mac_or_serial}_{description.key}"
        self.entity_description = description

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        profile = self.device.profiles[0]
        await self.entity_description.turn_on_fn(self.device)(
            profile, self.entity_description.turn_on_data
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        self._attr_is_on = False
        profile = self.device.profiles[0]
        await self.entity_description.turn_off_fn(self.device)(
            profile, self.entity_description.turn_off_data
        )


class ONVIFRelaySwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF relay output switch."""

    _attr_has_entity_name = True

    def __init__(self, device: ONVIFDevice, relay: Any) -> None:
        """Initialize the relay switch."""
        super().__init__(device)
        self._relay_token = relay.token
        # Extract relay properties if available
        if hasattr(relay, "Properties") and hasattr(relay.Properties, "Name"):
            self._attr_name = relay.Properties.Name
        else:
            self._attr_name = f"Relay {relay.token}"

        # The initial relay state is unknown until explicitly set
        self._attr_is_on = None

        self._attr_unique_id = f"{self.mac_or_serial}_relay_{self._relay_token}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        try:
            await self.device.async_set_relay_output_state(
                self._relay_token, "active"
            )
            self._attr_is_on = True
            self.async_write_ha_state()
        except ONVIFError:
            # Revert optimistic state update on error
            self._attr_is_on = False
            self.async_write_ha_state()
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        try:
            await self.device.async_set_relay_output_state(
                self._relay_token, "inactive"
            )
            self._attr_is_on = False
            self.async_write_ha_state()
        except ONVIFError:
            # Revert optimistic state update on error
            self._attr_is_on = True
            self.async_write_ha_state()
            raise

