"""Firmware update entity for reCamera Pro."""

from typing import Any

from recamera_protocol import (
    RecameraAuthenticationError,
    RecameraConnectionError,
    RecameraError,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import OTA_RELEASE_PAGE_URL
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity, recamera_service_error

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the reCamera firmware update entity."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    async_add_entities([RecameraFirmwareUpdate(coordinator)])


class RecameraFirmwareUpdate(RecameraEntity, UpdateEntity):
    """Represent online and local firmware access in one standard entity."""

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_should_poll = False
    _attr_icon = "mdi:cloud-download-outline"

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_firmware"

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        if self.coordinator.data is not None:
            return self.coordinator.data.info.firmware_version
        return self.coordinator.firmware_update.installed_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest confirmed OTA version, never the installed one."""
        state = self.coordinator.firmware_update
        return state.latest_version

    @property
    def in_progress(self) -> bool:
        """Return whether any confirmed firmware operation is active."""
        return self.coordinator.firmware_update.in_progress

    @property
    def update_percentage(self) -> int | None:
        """Return online OTA download progress."""
        state = self.coordinator.firmware_update
        return state.update_percentage if state.in_progress else None

    @property
    def release_url(self) -> str | None:
        """Return the vendor firmware release page."""
        return OTA_RELEASE_PAGE_URL

    @property
    def entity_picture(self) -> None:
        """Use the firmware icon instead of the integration brand image."""
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the observable firmware operation state."""
        state = self.coordinator.firmware_update
        return {
            "firmware_status": state.status,
            "operation": state.operation,
            "published_version": state.published_version,
            "target_version": state.target_version,
            "last_checked": (
                state.last_checked.isoformat() if state.last_checked else None
            ),
        }

    async def async_update(self) -> None:
        """Check for updates using the coordinator cache."""
        try:
            await self.coordinator.async_check_firmware_update(force=True)
        except RecameraAuthenticationError as err:
            raise ConfigEntryAuthFailed("invalid_auth") from err
        except (RecameraConnectionError, RecameraError) as err:
            raise UpdateFailed(f"Unable to check reCamera firmware: {err}") from err

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Download and apply the selected online firmware update."""
        try:
            await self.coordinator.async_install_firmware_update(
                self._async_set_progress
            )
        except RecameraAuthenticationError as err:
            if getattr(self, "hass", None) is not None:
                self.coordinator.config_entry.async_start_reauth(self.hass)
            raise recamera_service_error(err) from err
        except RecameraError as err:
            raise recamera_service_error(err) from err

    @callback
    def _async_set_progress(self, percentage: int | None) -> None:
        """Publish OTA progress without waiting for a coordinator poll."""
        self.async_write_ha_state()
