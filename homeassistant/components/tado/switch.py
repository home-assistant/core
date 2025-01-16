"""Module for Tado child lock switch entity."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TadoConfigEntry, TadoConnector
from .const import SIGNAL_TADO_UPDATE_RECEIVED
from .entity import TadoDeviceEntity

_LOGGER = logging.getLogger(__name__)


class TadoChildLockSwitchEntity(TadoDeviceEntity, SwitchEntity):
    """Representation of a Tado child lock switch entity."""

    _attr_has_entity_name = True

    # Implement one of these methods.
    def __init__(self, tado: TadoConnector, device_info) -> None:
        """Initialize the Tado child lock switch entity."""
        self._tado = tado
        super().__init__(device_info)
        self._device_info = device_info
        self._state: bool | None = None
        self._attr_unique_id = f"{self.device_id}_child_lock"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Child Lock"

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._tado.set_child_lock(self.device_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._tado.set_child_lock(self.device_id, False)

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "device", self.device_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_device_data()

    @callback
    def _async_update_callback(self) -> None:
        """Update and write state."""
        self._async_update_device_data()
        self.async_write_ha_state()

    @callback
    def _async_update_device_data(self) -> None:
        """Handle update callbacks."""
        try:
            self._device_info = self._tado.data["device"][self.device_id]
        except KeyError:
            return
        self._state = self._device_info.get("childLockEnabled", False) is True


async def async_setup_entry(
    hass: HomeAssistant, entry: TadoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado climate platform."""

    tado = entry.runtime_data
    entities: list[TadoChildLockSwitchEntity] = await hass.async_add_executor_job(
        _generate_entities, tado
    )

    async_add_entities(entities, True)


def _generate_entities(tado: TadoConnector) -> list[TadoChildLockSwitchEntity]:
    """Create all climate entities."""
    return [
        TadoChildLockSwitchEntity(tado, device)
        for device in tado.devices
        if "childLockEnabled" in device
    ]
