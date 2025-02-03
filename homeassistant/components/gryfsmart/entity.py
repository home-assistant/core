"""Define the base entity for the Gryf Smart integration."""

from __future__ import annotations

from pygryfsmart.api import GryfApi
from pygryfsmart.device import _GryfDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_DATA


class _GryfSmartEntityBase(Entity):
    """Base Entity for Gryf Smart."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    _api: GryfApi
    _device: _GryfDevice
    _attr_unique_id: str | None

    @property
    def name(self) -> str:
        return self._device.name


class GryfConfigFlowEntity(_GryfSmartEntityBase):
    """Gryf Config flow entity class."""

    _attr_has_entity_name = True
    _device: _GryfDevice
    _config_entry: ConfigEntry

    def __init__(
        self,
        config_entry: ConfigEntry,
        device: _GryfDevice,
    ) -> None:
        """Init Gryf config flow entity."""

        self._device = device
        self._config_entry = config_entry
        super().__init__()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        return self._config_entry.runtime_data[CONF_DEVICE_DATA]

    @property
    def unique_id(self) -> str | None:
        """Return unique_id."""
        return f"{self._device.name} {self._config_entry.unique_id}"


class GryfYamlEntity(_GryfSmartEntityBase):
    """Gryf yaml entity class."""

    _attr_has_entity_name = True
    _device: _GryfDevice

    def __init__(self, device: _GryfDevice) -> None:
        """Init Gryf yaml entity."""
        super().__init__()
        self._device = device

    @property
    def unique_id(self) -> str | None:
        """Return unique id."""
        return self._device.name
