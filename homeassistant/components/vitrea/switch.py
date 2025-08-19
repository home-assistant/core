"""Switch platform for Vitrea integration."""

from __future__ import annotations

import logging
from typing import Any

from vitreaclient.client import VitreaClient
from vitreaclient.constants import DeviceStatus, VitreaResponse
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .number import VitreaTimerControl

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,  # pylint: disable=hass-argument-type
) -> None:
    """Set up switch entities from a config entry."""
    # Register the set_timer service only for timer switches
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_timer",
        {vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=120))},
        "async_set_timer",
    )

    _LOGGER.debug("async_setup_entry called for Vitrea switches with entry: %s", entry)
    if len(entry.runtime_data.switches) > 0:
        _LOGGER.debug("Adding %d new switch entities", len(entry.runtime_data.switches))
        async_add_entities(entry.runtime_data.switches)

    entry.runtime_data.client.on(
        VitreaResponse.STATUS, lambda data: _handle_switch_event(entry, data)
    )


def _handle_switch_event(entry: ConfigEntry, event: Any) -> None:
    """Handle switch events from Vitrea client."""
    if event.status not in (
        DeviceStatus.SWITCH_ON,
        DeviceStatus.SWITCH_OFF,
        DeviceStatus.BOILER_ON,
        DeviceStatus.BOILER_OFF,
    ):
        return
    _LOGGER.debug("Handling switch status: %s", event)
    state = event.status in (DeviceStatus.SWITCH_ON, DeviceStatus.BOILER_ON)
    entity_id = f"{event.node}_{event.key}"
    entity: VitreaSwitch | None = None

    for switch in entry.runtime_data.switches:
        if switch.unique_id == entity_id:
            entity = switch
            break

    if entity:
        _LOGGER.debug("Updating state for %s to %s", entity_id, state)
        entity.set_switch_state(state)
        entity.async_write_ha_state()
        if hasattr(entity, "timer") and entity.timer:
            _LOGGER.debug("Updating timer for %s to %s minutes", entity_id, event.data)
            entity.timer.set_timer_value(int(event.data))
            if entity.timer.native_value > 0:
                entity.timer.default_value = int(event.data)
            entity.timer.async_write_ha_state()

    else:
        _LOGGER.warning("Received status for switch entity %s not found", entity_id)


class VitreaSwitch(SwitchEntity):
    """Representation of a Vitrea switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        node: str,
        key: str,
        is_on: bool,
        monitor: VitreaClient,
        timer: Any | None = None,
    ) -> None:
        """Initialize the switch."""
        self.monitor = monitor
        self._node = node
        self._key = key
        self._attr_unique_id = f"{node}_{key}"
        self._attr_is_on = is_on
        self.timer = timer

        # Modern naming pattern with device info - always apply

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node)},
            name=f"Node {node}",
            manufacturer="Vitrea",
        )

        # Set appropriate name and icon based on switch type
        if timer:
            self._attr_name = (
                f"Boiler {key}"  # e.g., "Boiler kitchen", "Boiler bedroom"
            )
            self._attr_icon = "mdi:water-boiler"
            # Share device info with timer for proper grouping
            if hasattr(timer, "_attr_device_info"):
                # Use setattr to avoid direct private member access warning
                setattr(timer, "_attr_device_info", self._attr_device_info)
        else:
            self._attr_name = f"Switch {key}"  # e.g., "Switch 1", "Switch living_room"
            self._attr_icon = "mdi:light-switch"

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        return False

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self._attr_is_on)

    @property
    def assumed_state(self) -> bool:
        """Return if the state is assumed."""
        return True

    def set_switch_state(self, state: bool) -> None:
        """Set the switch state."""
        self._attr_is_on = state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        _LOGGER.debug("turn_on %s/%s", self._node, self._key)

        try:
            if self.timer:
                timer = int(self.timer.default_value)
                _LOGGER.debug(
                    "Setting timer for %s/%s to %d", self._node, self._key, timer
                )
                await self.monitor.set_timer(self._node, self._key, timer)
            else:
                await self.monitor.key_on(self._node, self._key)

            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(
                "Failed to turn on switch %s/%s: %s", self._node, self._key, err
            )
            raise HomeAssistantError(
                f"Failed to turn on switch {self._node}/{self._key}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        _LOGGER.debug("turn_off %s/%s", self._node, self._key)

        try:
            await self.monitor.key_off(self._node, self._key)
            self._attr_is_on = False
            if self.timer:
                _LOGGER.debug(
                    "Resetting timer for switch %s/%s to 0 minutes",
                    self._node,
                    self._key,
                )
                self.timer.set_timer_value(0)
                self.timer.async_write_ha_state()

            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(
                "Failed to turn off switch %s/%s: %s", self._node, self._key, err
            )
            raise HomeAssistantError(
                f"Failed to turn off switch {self._node}/{self._key}"
            ) from err

    async def async_set_timer(self, minutes: int) -> None:
        """Set timer service for switches with timer functionality."""
        if self.timer:
            if isinstance(self.timer, VitreaTimerControl):
                await self.timer.async_set_native_value(float(minutes))
            else:
                _LOGGER.error(
                    "Timer object for switch %s/%s does not implement async_set_native_value",
                    self._node,
                    self._key,
                )
                raise HomeAssistantError(
                    f"Timer object for switch {self._node}/{self._key} does not implement async_set_native_value"
                )
        else:
            _LOGGER.warning(
                "Timer not available for switch %s/%s", self._node, self._key
            )
