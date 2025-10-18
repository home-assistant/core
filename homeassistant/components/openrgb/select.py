"""Select platform for OpenRGB integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONNECTION_ERRORS, DOMAIN, UID_SEPARATOR
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRGBConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenRGB select platform."""
    coordinator = config_entry.runtime_data
    async_add_entities([OpenRGBProfileSelect(coordinator, config_entry)])


class OpenRGBProfileSelect(CoordinatorEntity[OpenRGBCoordinator], SelectEntity):
    """Representation of an OpenRGB profile select entity."""

    _attr_translation_key = "profile"
    _attr_has_entity_name = True
    # https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/5178
    _attr_current_option: str | None = None

    def __init__(
        self, coordinator: OpenRGBCoordinator, entry: OpenRGBConfigEntry
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = UID_SEPARATOR.join([entry.entry_id, "profile"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            model="OpenRGB SDK Server",
            manufacturer="OpenRGB",
            sw_version=coordinator.get_client_protocol_version(),
            entry_type=DeviceEntryType.SERVICE,
        )
        self._update_attrs()

    @callback
    def _update_attrs(self) -> None:
        """Update the attributes based on the current profile list."""
        profiles = self.coordinator.client.profiles
        self._attr_options = [profile.name for profile in profiles]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if the select is available."""
        return (
            super().available
            and self._attr_options is not None
            and len(self._attr_options) > 0
        )

    async def async_select_option(self, option: str) -> None:
        """Load the selected profile."""
        async with self.coordinator.client_lock:
            try:
                await self.hass.async_add_executor_job(
                    self.coordinator.client.load_profile, option
                )
            except CONNECTION_ERRORS as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={
                        "server_address": self.coordinator.server_address,
                        "error": str(err),
                    },
                ) from err
            except ValueError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="openrgb_error",
                    translation_placeholders={
                        "error": str(err),
                    },
                ) from err

        # Refresh immediately to ensure profile changes are reflected
        await self.coordinator.async_refresh()
