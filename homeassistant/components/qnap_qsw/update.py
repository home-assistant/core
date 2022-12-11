"""Support for the QNAP QSW update."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

from aioqsw.const import (
    QSD_DESCRIPTION,
    QSD_FIRMWARE,
    QSD_FIRMWARE_CHECK,
    QSD_FIRMWARE_INFO,
    QSD_MAC,
    QSD_PRODUCT,
    QSD_SERIAL,
    QSD_SYSTEM_BOARD,
    QSD_VERSION,
)
from securetar import SecureTarFile

from homeassistant.components.backup.manager import _generate_slug
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt, json as json_util

from .const import DOMAIN, QSW_COORD_FW, QSW_UPDATE
from .coordinator import QswFirmwareCoordinator
from .entity import QswFirmwareEntity

UPDATE_TYPES: Final[tuple[UpdateEntityDescription, ...]] = (
    UpdateEntityDescription(
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        key=QSW_UPDATE,
        name="Firmware Update",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW updates from a config_entry."""
    coordinator: QswFirmwareCoordinator = hass.data[DOMAIN][entry.entry_id][
        QSW_COORD_FW
    ]
    async_add_entities(
        QswUpdate(coordinator, description, entry) for description in UPDATE_TYPES
    )


class QswUpdate(QswFirmwareEntity, UpdateEntity):
    """Define a QNAP QSW update."""

    _attr_supported_features = UpdateEntityFeature.BACKUP | UpdateEntityFeature.INSTALL
    entity_description: UpdateEntityDescription

    def __init__(
        self,
        coordinator: QswFirmwareCoordinator,
        description: UpdateEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = (
            f"{self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT)} {description.name}"
        )
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self.backup_dir = Path(self.coordinator.hass.config.path("backups"))
        self.entity_description = description

        self._attr_installed_version = self.get_device_value(
            QSD_FIRMWARE_INFO, QSD_VERSION
        )
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attributes."""
        self._attr_latest_version = self.get_device_value(
            QSD_FIRMWARE_CHECK, QSD_VERSION
        )
        self._attr_release_summary = self.get_device_value(
            QSD_FIRMWARE_CHECK, QSD_DESCRIPTION
        )

    def _generate_backup_contents(
        self,
        tar_file_path: Path,
        backup_data: dict[str, Any],
        backup_bytes: bytes,
    ) -> None:
        """Generate backup contents."""
        with TemporaryDirectory() as tmp_dir, SecureTarFile(
            tar_file_path, "w", gzip=False
        ) as tar_file:
            tmp_dir_path = Path(tmp_dir)
            json_util.save_json(
                tmp_dir_path.joinpath("backup.json").as_posix(),
                backup_data,
            )
            with open(
                tmp_dir_path.joinpath("qnap-qsw.conf").as_posix(),
                "wb",
            ) as conf:
                conf.write(backup_bytes)
                conf.close()
            tar_file.add(tmp_dir_path, arcname=".")

    async def _async_backup(self) -> None:
        """Create backup file."""
        backup_bytes = await self.coordinator.qsw.config_backup()
        if backup_bytes is None:
            raise HomeAssistantError("Backup failed")

        _firmware = self.get_device_value(QSD_FIRMWARE_INFO, QSD_FIRMWARE)
        _mac = self.get_device_value(QSD_SYSTEM_BOARD, QSD_MAC)
        _product = self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT)

        backup_name = f"{_product} {_mac} v{_firmware}"
        date_str = dt.now().isoformat()
        slug = _generate_slug(date_str, backup_name)

        backup_data = {
            "slug": slug,
            "name": backup_name,
            "date": date_str,
            "homeassistant": {"version": HAVERSION},
            "qnap_qsw": {
                QSD_FIRMWARE: _firmware,
                QSD_MAC: _mac,
                QSD_PRODUCT: _product,
                QSD_SERIAL: self.get_device_value(QSD_SYSTEM_BOARD, QSD_SERIAL),
            },
            "compressed": False,
        }
        tar_file_path = Path(self.backup_dir, f"{backup_data['slug']}.tar")

        if not self.backup_dir.exists():
            self.hass.async_add_executor_job(self.backup_dir.mkdir)

        await self.hass.async_add_executor_job(
            self._generate_backup_contents,
            tar_file_path,
            backup_data,
            backup_bytes,
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if backup:
            await self._async_backup()

        await self.coordinator.async_refresh()
        await self.coordinator.qsw.live_update()

        self._attr_installed_version = self.latest_version
        self.async_write_ha_state()
