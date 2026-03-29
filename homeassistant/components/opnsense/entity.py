"""Define the base entities for OPNsense."""

import logging
from typing import Any

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_DEVICE_UNIQUE_ID, DOMAIN, OPNSENSE_CLIENT
from .coordinator import OPNsenseDataUpdateCoordinator
from .helpers import dict_get

_LOGGER: logging.Logger = logging.getLogger(__name__)


class OPNsenseBaseEntity(CoordinatorEntity[OPNsenseDataUpdateCoordinator]):
    """Base entity for OPNsense."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: OPNsenseDataUpdateCoordinator,
        unique_id_suffix: str,
        name_suffix: str | None = None,
    ) -> None:
        """Initialize OPNsense Entity."""
        self.config_entry: ConfigEntry = config_entry
        self.coordinator: OPNsenseDataUpdateCoordinator = coordinator
        self._device_unique_id: str = config_entry.data[CONF_DEVICE_UNIQUE_ID]
        if not unique_id_suffix:
            raise ValueError("unique_id_suffix must be a non-empty string")
        self._attr_unique_id: str = slugify(
            f"{self._device_unique_id}_{unique_id_suffix}"
        )
        if name_suffix:
            self._attr_name: str | None = name_suffix
        self._client: OPNsenseClient | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._available: bool = False
        super().__init__(self.coordinator, self._attr_unique_id)

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return (
            getattr(self.coordinator, "last_update_success", True) and self._available
        )

    @property
    def opnsense_device_name(self) -> str | None:
        """Return the OPNsense device name."""
        if self.config_entry.title and len(self.config_entry.title) > 0:
            return self.config_entry.title
        return self._get_opnsense_state_value("system_info.name")

    def _get_opnsense_state_value(self, path: str) -> Any | None:
        state = self.coordinator.data
        return dict_get(state, path)

    async def async_added_to_hass(self) -> None:
        """Run once integration has been added to HA."""
        await super().async_added_to_hass()
        if self._client is None:
            self._client = getattr(
                self.config_entry.runtime_data, OPNSENSE_CLIENT, None
            )
        if self._client is None:
            msg = "OPNsense runtime client is missing in async_added_to_hass"
            _LOGGER.error(msg)
            raise RuntimeError(msg)
        self._handle_coordinator_update()


class OPNsenseEntity(OPNsenseBaseEntity):
    """Primary OPNsense Entity including device info."""

    @property
    def device_info(self) -> DeviceInfo | None:
        """Device info for the firewall."""
        raw_state: object = self.coordinator.data
        model: str = "OPNsense"
        manufacturer: str = "Deciso B.V."
        if not isinstance(raw_state, dict):
            firmware: str | None = None
        else:
            state = raw_state
            firmware_value = state.get("host_firmware_version")
            firmware = firmware_value if isinstance(firmware_value, str) else None

        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device_unique_id)},
            "name": self.opnsense_device_name,
            "configuration_url": self.config_entry.data.get("url", None),
        }

        device_info["model"] = model
        device_info["manufacturer"] = manufacturer
        device_info["sw_version"] = firmware

        return device_info
