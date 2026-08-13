"""TrueNAS switch platform."""

from __future__ import annotations

from logging import getLogger
from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TrueNASConfigEntry
from .entity import TrueNASEntity
from .entity import async_add_entities as setup_entities
from .switch_types import (  # noqa: F401
    SENSOR_SERVICES,
    SENSOR_TYPES,
    TrueNASSwitchEntityDescription,
)

_LOGGER = getLogger(__name__)

# Updates are centralized in the coordinator; entity actions may run unlimited.
PARALLEL_UPDATES = 0


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TrueNASConfigEntry,
    _async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for TrueNAS component."""
    dispatcher = {
        "TrueNASServiceSwitch": TrueNASServiceSwitch,
        "TrueNASCloudsyncSwitch": TrueNASCloudsyncSwitch,
        "TrueNASCronjobSwitch": TrueNASCronjobSwitch,
    }
    await setup_entities(hass, config_entry, dispatcher)


# ---------------------------
#   _TrueNASSwitch (base)
# ---------------------------
class _TrueNASSwitch(TrueNASEntity, SwitchEntity):
    """Shared base for all TrueNAS switch entities."""

    entity_description: TrueNASSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._data.get(self.entity_description.data_is_on, False))


# ---------------------------
#   _TrueNASEnableSwitch (base)
# ---------------------------
class _TrueNASEnableSwitch(_TrueNASSwitch):
    """Base for switches that toggle a domain object via <domain>.update."""

    _update_method: str

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.query(
            self._update_method, [self._data["id"], {"enabled": True}]
        )
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.query(
            self._update_method, [self._data["id"], {"enabled": False}]
        )
        await self.coordinator.async_request_refresh()


# ---------------------------
#   TrueNASServiceSwitch
# ---------------------------
class TrueNASServiceSwitch(_TrueNASSwitch):
    """Define a TrueNAS Service Switch."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.query("service.start", [self._data["service"]])
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.query("service.stop", [self._data["service"]])
        await self.coordinator.async_request_refresh()


# ---------------------------
#   TrueNASCloudsyncSwitch
# ---------------------------
class TrueNASCloudsyncSwitch(_TrueNASEnableSwitch):
    """Define a TrueNAS Cloudsync Switch."""

    _update_method = "cloudsync.update"


# ---------------------------
#   TrueNASCronjobSwitch
# ---------------------------
class TrueNASCronjobSwitch(_TrueNASEnableSwitch):
    """Define a TrueNAS Cronjob Switch."""

    _update_method = "cronjob.update"
