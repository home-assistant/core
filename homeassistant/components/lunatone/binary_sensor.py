"""Platform for Lunatone binary sensor integration."""

from collections.abc import Callable
import contextlib
from functools import partial
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneScanDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone binary sensors from the config entry."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    config_entry_unique_id = config_entry.unique_id
    assert config_entry_unique_id is not None

    async_add_entities(
        [LunatoneDALIScanStatus(coordinator_scan, config_entry_unique_id)]
    )

    def _add_entities(
        entity_builder: dict[str, Callable[[], BinarySensorEntity]],
        known_entities: set[str],
    ) -> None:
        current_entities = set(entity_builder)
        new_entities = current_entities - known_entities

        if new_entities:
            with contextlib.suppress(ValueError):
                async_add_entities(
                    [
                        entity_builder[entity_unique_id]()
                        for entity_unique_id in new_entities
                    ]
                )
                known_entities.update(new_entities)

    known_entities: set[str] = set()

    @callback
    def _check_entities() -> None:
        entity_builder: dict[str, Callable[[], BinarySensorEntity]] = {}
        for line_id in map(int, coordinator_info.data.lines):
            unique_id = LunatoneDALIScanStatus.construct_unique_id(
                config_entry_unique_id, line_id
            )
            entity_builder[unique_id] = partial(
                LunatoneDALIScanStatus,
                coordinator_scan,
                config_entry_unique_id,
                line_id,
            )
        _add_entities(entity_builder, known_entities)

    _check_entities()
    config_entry.async_on_unload(coordinator_info.async_add_listener(_check_entities))


class LunatoneDALIScanStatus(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Lunatone DALI scan status."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "scan_status"

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        config_entry_unique_id: str,
        line: int | None = None,
    ) -> None:
        """Initialize a Lunatone DALI scan status."""
        super().__init__(coordinator)

        self._line = line

        device_unique_id = config_entry_unique_id
        if line is not None:
            device_unique_id += f"-line{line}"

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.construct_device_unique_id(config_entry_unique_id, line))
            },
        )
        self._attr_unique_id = self.construct_unique_id(config_entry_unique_id, line)

    @staticmethod
    def construct_device_unique_id(
        config_entry_unique_id: str, line_id: int | None = None
    ) -> str:
        """Returns the unique_id of the parent device."""
        suffix = f"-line{line_id}" if line_id is not None else ""
        return f"{config_entry_unique_id}{suffix}"

    @staticmethod
    def construct_unique_id(
        config_entry_unique_id: str, line_id: int | None = None
    ) -> str:
        """Returns the unique_id for a device ID."""
        return f"{
            LunatoneDALIScanStatus.construct_device_unique_id(
                config_entry_unique_id, line_id
            )
        }-scan-progress"

    @property
    @override
    def available(self) -> bool:
        return super().available and (
            self._line is None or self._line in self.coordinator.line_scan_status
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the DALI scan is on."""
        if self._line is None:
            return self.coordinator.data.busy
        line_scan_status = self.coordinator.line_scan_status.get(self._line)
        return line_scan_status.busy if line_scan_status is not None else False
