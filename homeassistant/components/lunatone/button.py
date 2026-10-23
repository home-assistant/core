"""Support for lunatone buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from lunatone_rest_api_client import DALIScan
from lunatone_rest_api_client.models import StartScanData

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneScanDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LunatoneDALIScanButtonEntityDescription(ButtonEntityDescription):
    """Describes DALI scan button entity."""

    press_not_allowed_error_key: str
    press_allowed_fn: Callable[[DALIScan], bool]
    press_fn: Callable[[DALIScan], Awaitable[None]]


BUTTON_DESCRIPTIONS: tuple[LunatoneDALIScanButtonEntityDescription, ...] = (
    LunatoneDALIScanButtonEntityDescription(
        key="scan-cancel",
        translation_key="scan_cancel",
        entity_category=EntityCategory.CONFIG,
        press_not_allowed_error_key="cannot_cancel_scan",
        press_allowed_fn=lambda client: client.data.busy,
        press_fn=lambda client: client.async_cancel(),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan",
        translation_key="scan_start",
        entity_category=EntityCategory.CONFIG,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=lambda client: not client.data.busy,
        press_fn=lambda client: client.async_start(
            StartScanData(newInstallation=False, noAddressing=False)
        ),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan-new",
        translation_key="scan_start_new",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=lambda client: not client.data.busy,
        press_fn=lambda client: client.async_start(
            StartScanData(newInstallation=True, noAddressing=False)
        ),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan-current",
        translation_key="scan_start_current",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=lambda client: not client.data.busy,
        press_fn=lambda client: client.async_start(
            StartScanData(newInstallation=False, noAddressing=True)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Button platform."""
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    async_add_entities(
        [
            DALIScanButtonEntity(coordinator_scan, button_description)
            for button_description in BUTTON_DESCRIPTIONS
        ]
    )


class DALIScanButtonEntity(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], ButtonEntity
):
    """Representation of a DALI scan button."""

    entity_description: LunatoneDALIScanButtonEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        description: LunatoneDALIScanButtonEntityDescription,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator)
        self.entity_description = description

        config_entry_unique_id = coordinator.config_entry.unique_id
        assert config_entry_unique_id

        device_unique_id = f"{config_entry_unique_id}"

        self._attr_unique_id = f"{device_unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_unique_id)})

    @override
    async def async_press(self) -> None:
        """Press the button."""
        if not self.entity_description.press_allowed_fn(self.coordinator.dali_scan_api):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=self.entity_description.press_not_allowed_error_key,
            )
        await self.entity_description.press_fn(self.coordinator.dali_scan_api)
        await self.coordinator.async_request_refresh()
