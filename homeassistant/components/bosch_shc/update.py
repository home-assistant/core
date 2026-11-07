"""Platform for update integration."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

from boschshcpy import SHCInformation
from boschshcpy.exceptions import SHCException

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(minutes=15)

IN_PROGRESS_STATES = {
    SHCInformation.UpdateState.DOWNLOADING,
    SHCInformation.UpdateState.INSTALLING,
    SHCInformation.UpdateState.UPDATE_IN_PROGRESS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC update platform."""
    information = config_entry.runtime_data.information
    if TYPE_CHECKING:
        assert information is not None and information.unique_id is not None

    async_add_entities(
        [ControllerUpdate(information, information.unique_id, config_entry.title)],
        update_before_add=True,
    )


class ControllerUpdate(UpdateEntity):
    """Firmware update of the Bosch Smart Home Controller."""

    _attr_has_entity_name = True
    _attr_translation_key = "controller_update"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, information: SHCInformation, unique_id: str, title: str) -> None:
        """Initialize the controller update entity."""
        self._information = information
        self._title = title
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return self._information.version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest firmware version, or the installed one if none is offered."""
        return self._information.available_version or self._information.version

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether an installation is running."""
        return self._information.updateState in IN_PROGRESS_STATES

    def update(self) -> None:
        """Refresh the software update state of the controller."""
        self._information.refresh()

    @override
    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Start the firmware update of the controller."""
        state = self._information.updateState
        if state is not SHCInformation.UpdateState.UPDATE_AVAILABLE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_not_ready",
                translation_placeholders={"name": self._title, "state": state.name},
            )
        try:
            self._information.start_software_update()
        except SHCException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_install_failed",
                translation_placeholders={"name": self._title, "error": str(err)},
            ) from err
        self.update()
