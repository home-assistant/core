"""Support for lunatone buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import override

import aiohttp
from lunatone_rest_api_client import DALIScan
from lunatone_rest_api_client.models import StartScanData

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneInfoDataUpdateCoordinator,
    LunatoneScanDataUpdateCoordinator,
)
from .helpers import add_entities_from_builder, format_device_identifier

PARALLEL_UPDATES = 0


def _scan_allowed(client: DALIScan, line_id: int | None = None) -> bool:
    """Return whether a scan is allowed for the given line."""
    return not (
        client.data.busy
        if line_id is None
        else any(
            line_data.busy
            for line_data in client.data.lines
            if line_data.line == line_id
        )
    )


@dataclass(frozen=True, kw_only=True)
class LunatoneDALIScanButtonEntityDescription(ButtonEntityDescription):
    """Describes DALI scan button entity."""

    press_not_allowed_error_key: str
    press_allowed_fn: Callable[[DALIScan, int | None], bool]
    press_fn: Callable[[DALIScan, int | None], Awaitable[None]]
    line_id: int | None = None


BUTTON_DESCRIPTIONS: tuple[LunatoneDALIScanButtonEntityDescription, ...] = (
    LunatoneDALIScanButtonEntityDescription(
        key="scan-cancel",
        translation_key="scan_cancel",
        entity_category=EntityCategory.CONFIG,
        press_not_allowed_error_key="cannot_cancel_scan",
        press_allowed_fn=lambda client, _: not _scan_allowed(client),
        press_fn=lambda client, _: client.async_cancel(),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan",
        translation_key="scan_start",
        entity_category=EntityCategory.CONFIG,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=_scan_allowed,
        press_fn=lambda client, line_id: client.async_start(
            StartScanData(
                newInstallation=False,
                noAddressing=False,
                useLines=[line_id] if line_id is not None else [],
            )
        ),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan-new",
        translation_key="scan_start_new",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=_scan_allowed,
        press_fn=lambda client, line_id: client.async_start(
            StartScanData(
                newInstallation=True,
                noAddressing=False,
                useLines=[line_id] if line_id is not None else [],
            )
        ),
    ),
    LunatoneDALIScanButtonEntityDescription(
        key="scan-current",
        translation_key="scan_start_current",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_not_allowed_error_key="cannot_start_scan",
        press_allowed_fn=_scan_allowed,
        press_fn=lambda client, line_id: client.async_start(
            StartScanData(
                newInstallation=False,
                noAddressing=True,
                useLines=[line_id] if line_id is not None else [],
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Button platform."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    config_entry_unique_id = config_entry.unique_id
    assert config_entry_unique_id is not None

    async_add_entities(
        [
            DALIScanButtonEntity(coordinator_scan, coordinator_info, button_description)
            for button_description in BUTTON_DESCRIPTIONS
        ]
    )

    known_entities: set[str] = set()

    @callback
    def _check_entities() -> None:
        entity_builder: dict[str, Callable[[], ButtonEntity]] = {}
        for line_id in map(int, coordinator_info.data.lines):
            for description in BUTTON_DESCRIPTIONS[1:]:
                unique_id = DALIScanButtonEntity.construct_unique_id(
                    config_entry_unique_id, description.key, line_id
                )
                entity_builder[unique_id] = partial(
                    DALIScanButtonEntity,
                    coordinator_scan,
                    coordinator_info,
                    description,
                    line_id,
                )
        add_entities_from_builder(entity_builder, known_entities, async_add_entities)

    _check_entities()
    config_entry.async_on_unload(coordinator_info.async_add_listener(_check_entities))


class DALIScanButtonEntity(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], ButtonEntity
):
    """Representation of a DALI scan button."""

    entity_description: LunatoneDALIScanButtonEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator_scan: LunatoneScanDataUpdateCoordinator,
        coordinator_info: LunatoneInfoDataUpdateCoordinator,
        description: LunatoneDALIScanButtonEntityDescription,
        line_id: int | None = None,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator_scan)
        self.entity_description = description
        self._coordinator_info = coordinator_info
        self._line_id = line_id

        config_entry_unique_id = coordinator_scan.config_entry.unique_id
        assert config_entry_unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    format_device_identifier(config_entry_unique_id, line_id),
                )
            }
        )
        self._attr_unique_id = self.construct_unique_id(
            config_entry_unique_id, description.key, line_id
        )

    @staticmethod
    def construct_unique_id(
        config_entry_unique_id: str, suffix: str, line_id: int | None = None
    ) -> str:
        """Returns the unique_id for a device ID."""
        return f"{format_device_identifier(config_entry_unique_id, line_id)}-{suffix}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator_info.async_add_listener(self._handle_info_update)
        )

    @callback
    def _handle_info_update(self) -> None:
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        info_data = self._coordinator_info.data
        line_id = self._line_id
        return (
            super().available
            and self._coordinator_info.last_update_success
            and (line_id is None or info_data.is_line_status_ok(line_id))
        )

    @override
    async def async_press(self) -> None:
        """Press the button."""
        async with self.coordinator.scan_lock:
            client = self.coordinator.dali_scan_api
            description = self.entity_description
            press_allowed = description.press_allowed_fn(client, self._line_id)
            if not press_allowed:
                await self.coordinator.async_refresh()
                if not self.coordinator.last_update_success:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="cannot_retrieve_scan_data",
                    )
                press_allowed = description.press_allowed_fn(client, self._line_id)

            if not press_allowed:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=description.press_not_allowed_error_key,
                )

            try:
                await description.press_fn(client, self._line_id)
            except aiohttp.ClientConnectionError as ex:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="cannot_control_scan",
                    translation_placeholders={"entity": self.entity_id},
                ) from ex

            await self.coordinator.async_refresh()
