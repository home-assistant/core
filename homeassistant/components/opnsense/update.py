"""Firmware update information for OPNsense routers."""

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override
from urllib.parse import urljoin

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import OPNsenseFirmwareCoordinator
from .types import OPNsenseConfigEntry

_LOGGER = logging.getLogger(__name__)
UPGRADE_STATUS_INTERVAL = timedelta(seconds=10)
UPGRADE_TIMEOUT = timedelta(hours=2)
POST_UPGRADE_REFRESH_DELAY = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the router firmware update entity."""
    coordinator = OPNsenseFirmwareCoordinator(hass, entry, entry.runtime_data.client)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([OPNsenseFirmwareUpdate(coordinator, entry)])


class OPNsenseFirmwareUpdate(
    CoordinatorEntity[OPNsenseFirmwareCoordinator], UpdateEntity
):
    """Represent the router firmware update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_translation_key = "firmware"

    def __init__(
        self, coordinator: OPNsenseFirmwareCoordinator, entry: OPNsenseConfigEntry
    ) -> None:
        """Initialize the firmware entity."""
        super().__init__(coordinator)
        assert entry.unique_id is not None
        self._attr_unique_id = f"{entry.unique_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title or "OPNsense",
            manufacturer="OPNsense",
            configuration_url=entry.data[CONF_URL],
        )
        self._attr_release_url = urljoin(
            entry.data[CONF_URL], "/ui/core/firmware#changelog"
        )
        self._upgrade_in_progress = False
        self._upgrade_started: datetime | None = None
        self._unsub_upgrade_status: Callable[[], None] | None = None
        self._unsub_post_upgrade_refresh: Callable[[], None] | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Cancel firmware polling when the entity is removed."""
        await super().async_added_to_hass()
        self.async_on_remove(self._stop_upgrade_tracking)

    def _stop_upgrade_tracking(self) -> None:
        """Stop polling firmware upgrade status."""
        if self._unsub_upgrade_status is not None:
            self._unsub_upgrade_status()
            self._unsub_upgrade_status = None
        if self._unsub_post_upgrade_refresh is not None:
            self._unsub_post_upgrade_refresh()
            self._unsub_post_upgrade_refresh = None

    async def _async_refresh_after_upgrade(self, now: datetime) -> None:
        """Refresh firmware information after OPNsense restarts."""
        self._unsub_post_upgrade_refresh = None
        await self.coordinator.async_request_refresh()

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether the router is still upgrading."""
        return self._upgrade_in_progress

    async def _async_poll_upgrade_status(self, now: datetime) -> None:
        """Track the active firmware upgrade."""
        status = await self.coordinator.client.upgrade_status()
        if (
            status
            and status.get("status") == "running"
            and (
                self._upgrade_started is not None
                and now - self._upgrade_started < UPGRADE_TIMEOUT
            )
        ):
            return
        if (
            not status
            and self._upgrade_started is not None
            and (now - self._upgrade_started < UPGRADE_TIMEOUT)
        ):
            return

        self._stop_upgrade_tracking()
        self._upgrade_in_progress = False
        self._upgrade_started = None
        self.async_write_ha_state()
        if status and status.get("status") in ("done", "reboot"):
            await self.coordinator.async_request_refresh()
            self._unsub_post_upgrade_refresh = async_call_later(
                self.hass,
                POST_UPGRADE_REFRESH_DELAY,
                self._async_refresh_after_upgrade,
            )
        else:
            _LOGGER.error("OPNsense firmware upgrade failed or timed out: %s", status)

    @property
    @override
    def available(self) -> bool:
        """Return whether firmware versions are available."""
        return (
            super().available
            and bool(self.installed_version)
            and bool(self.latest_version)
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return cast(
            str | None, self.coordinator.data.get("product", {}).get("product_version")
        )

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        if self.coordinator.data.get("status") == "upgrade" and (
            major_version := self.coordinator.data.get("upgrade_major_version")
        ):
            return cast(str, major_version)

        product = self.coordinator.data.get("product", {})
        latest_version = product.get("product_latest")
        if (
            self.coordinator.data.get("status") == "update"
            and latest_version == product.get("product_version")
            and latest_version
        ):
            return f"{latest_version} (package updates available)"
        return cast(str | None, latest_version)

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the update status and reboot requirement."""
        status_msg = self.coordinator.data.get("status_msg")
        if self.coordinator.data.get("status_reboot") == "1":
            return (
                f"Reboot required. {status_msg}" if status_msg else "Reboot required."
            )
        return cast(str | None, status_msg)

    @override
    async def async_release_notes(self) -> str | None:
        """Return the firmware status and pending package changes."""
        summary = self.release_summary
        sections = [summary] if summary else []
        for heading, key in (
            ("Upgrades", "upgrade_packages"),
            ("Downgrades", "downgrade_packages"),
            ("New packages", "new_packages"),
            ("Removed packages", "remove_packages"),
            ("Reinstalls", "reinstall_packages"),
        ):
            packages = self.coordinator.data.get(key, [])
            if not packages:
                continue
            lines = [f"### {heading}"]
            for package in packages:
                name = package["name"]
                if key in ("upgrade_packages", "downgrade_packages"):
                    lines.append(
                        f"- {name}: {package['current_version']} -> {package['new_version']}"
                    )
                else:
                    version = (
                        package.get("version")
                        or package.get("new_version")
                        or package.get("old_version")
                    )
                    lines.append(f"- {name}: {version}" if version else f"- {name}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections) or None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Start the firmware update available on OPNsense."""
        update_type = self.coordinator.data.get("status")
        if update_type in ("update", "upgrade"):
            response = await self.coordinator.client.upgrade_firmware(type=update_type)
            if response and response.get("status") == "ok":
                self._upgrade_in_progress = True
                self._upgrade_started = dt_util.utcnow()
                self._unsub_upgrade_status = async_track_time_interval(
                    self.hass, self._async_poll_upgrade_status, UPGRADE_STATUS_INTERVAL
                )
                self.async_write_ha_state()
                return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="firmware_update_failed",
        )
