"""Switch platform for Watts Vision integration."""

from __future__ import annotations

import logging
from typing import Any

from visionpluspython.models import SwitchDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WattsVisionConfigEntry
from .const import DOMAIN
from .coordinator import WattsVisionDeviceCoordinator
from .entity import WattsVisionEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Watts Vision switch entities from a config entry."""
    device_coordinators = entry.runtime_data.device_coordinators
    known_device_ids: set[str] = set()

    @callback
    def _check_new_switches() -> None:
        """Check for new switch devices."""
        switch_coords = {
            did: coord
            for did, coord in device_coordinators.items()
            if isinstance(coord.data.device, SwitchDevice)
        }
        current_device_ids = set(switch_coords.keys())
        new_device_ids = current_device_ids - known_device_ids

        if not new_device_ids:
            return

        _LOGGER.debug(
            "Adding switch entities for %d new switch(es)",
            len(new_device_ids),
        )

        new_entities = []
        for device_id in new_device_ids:
            coord = switch_coords[device_id]
            device = coord.data.device
            assert isinstance(device, SwitchDevice)
            new_entities.append(WattsVisionSwitch(coord, device))

        known_device_ids.update(new_device_ids)
        async_add_entities(new_entities)

    _check_new_switches()

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_new_device",
            _check_new_switches,
        )
    )


class WattsVisionSwitch(WattsVisionEntity[SwitchDevice], SwitchEntity):
    """Representation of a Watts Vision switch."""

    _attr_name = None

    def __init__(
        self,
        coordinator: WattsVisionDeviceCoordinator,
        switch: SwitchDevice,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, switch.device_id)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.is_turned_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.client.set_switch_state(self.device_id, True)
        except RuntimeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_state_error",
            ) from err

        _LOGGER.debug(
            "Successfully turned on switch %s",
            self.device_id,
        )

        self.coordinator.trigger_fast_polling()

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.client.set_switch_state(self.device_id, False)
        except RuntimeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_state_error",
            ) from err

        _LOGGER.debug(
            "Successfully turned off switch %s",
            self.device_id,
        )

        self.coordinator.trigger_fast_polling()

        await self.coordinator.async_refresh()
