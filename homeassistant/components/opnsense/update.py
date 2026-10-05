"""Firmware update information for OPNsense routers."""

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any, cast, override

from aiopnsense import OPNsenseConnectionError, OPNsenseTimeoutError
from yarl import URL

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
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
    assert entry.unique_id is not None
    entity_registry = er.async_get(hass)
    if (
        (
            entity_id := entity_registry.async_get_entity_id(
                Platform.UPDATE, DOMAIN, entry.unique_id
            )
        )
        and (registry_entry := entity_registry.async_get(entity_id))
        and (registry_entry.disabled)
    ):
        return

    coordinator = OPNsenseFirmwareCoordinator(hass, entry, entry.runtime_data.client)
    entry.runtime_data.update_coordinator = coordinator
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
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title or "OPNsense",
            manufacturer="OPNsense",
            configuration_url=str(URL(entry.data[CONF_URL]).with_path("/")),
        )
        self._attr_release_url = str(
            URL(entry.data[CONF_URL])
            .with_path("/ui/core/firmware")
            .with_fragment("changelog")
        )
        self._upgrade_in_progress = False
        self._upgrade_started: datetime | None = None
        self._unsub_upgrade_status: Callable[[], None] | None = None
        self._unsub_post_upgrade_refresh: Callable[[], None] | None = None
        self._post_upgrade_refresh_retried = False
        self._upgrade_status_generation = 0
        self._upgrade_status_polling = False

    @override
    async def async_added_to_hass(self) -> None:
        """Cancel firmware polling when the entity is removed."""
        await super().async_added_to_hass()
        self.async_on_remove(self._stop_upgrade_tracking)

    def _stop_upgrade_tracking(self) -> None:
        """Stop polling firmware upgrade status."""
        self._upgrade_status_generation += 1
        if self._unsub_upgrade_status is not None:
            self._unsub_upgrade_status()
            self._unsub_upgrade_status = None
        if self._unsub_post_upgrade_refresh is not None:
            self._unsub_post_upgrade_refresh()
            self._unsub_post_upgrade_refresh = None

    async def _async_refresh_after_upgrade(
        self, now: datetime, *, generation: int
    ) -> None:
        """Refresh firmware information after OPNsense restarts."""
        if generation != self._upgrade_status_generation:
            return
        self._unsub_post_upgrade_refresh = None
        await self.coordinator.async_request_refresh()
        if generation != self._upgrade_status_generation:
            return
        if not self._post_upgrade_refresh_retried:
            self._post_upgrade_refresh_retried = True
            self._unsub_post_upgrade_refresh = async_call_later(
                self.hass,
                POST_UPGRADE_REFRESH_DELAY,
                partial(self._async_refresh_after_upgrade, generation=generation),
            )

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether the router is still upgrading."""
        return self._upgrade_in_progress

    async def _async_poll_upgrade_status(
        self, now: datetime, *, generation: int
    ) -> None:
        """Track the active firmware upgrade."""
        if (
            generation != self._upgrade_status_generation
            or self._upgrade_started is None
        ):
            return

        upgrade_started = self._upgrade_started
        if now - upgrade_started >= UPGRADE_TIMEOUT:
            status = None
        elif self._upgrade_status_polling:
            return
        else:
            self._upgrade_status_polling = True
            try:
                status = await self.coordinator.client.upgrade_status()
            except (OPNsenseConnectionError, OPNsenseTimeoutError) as err:
                if dt_util.utcnow() - upgrade_started < UPGRADE_TIMEOUT:
                    _LOGGER.debug("Unable to poll OPNsense upgrade status: %s", err)
                    return
                status = None
            finally:
                self._upgrade_status_polling = False

            if (
                generation != self._upgrade_status_generation
                or self._upgrade_started is None
            ):
                return

        if dt_util.utcnow() - upgrade_started < UPGRADE_TIMEOUT and (
            not status or status.get("status") in ("running", "error")
        ):
            return

        self._stop_upgrade_tracking()
        self._upgrade_in_progress = False
        self._upgrade_started = None
        self.async_write_ha_state()
        if status and status.get("status") in ("done", "reboot"):
            self._post_upgrade_refresh_retried = False
            generation = self._upgrade_status_generation
            await self.coordinator.async_request_refresh()
            if generation != self._upgrade_status_generation:
                return
            self._unsub_post_upgrade_refresh = async_call_later(
                self.hass,
                POST_UPGRADE_REFRESH_DELAY,
                partial(self._async_refresh_after_upgrade, generation=generation),
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
        status = self.coordinator.data.get("status")
        if status not in ("update", "upgrade"):
            return self.installed_version

        if status == "upgrade" and (
            major_version := self.coordinator.data.get("upgrade_major_version")
        ):
            return cast(str, major_version)

        product = self.coordinator.data.get("product", {})
        latest_version = product.get("product_latest")
        if (
            status == "update"
            and latest_version == product.get("product_version")
            and latest_version
        ):
            return f"{latest_version} (package updates available)"
        return cast(str | None, latest_version)

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the update status and reboot requirement."""
        return cast(str | None, self.coordinator.data.get("status_msg"))

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
            self._upgrade_in_progress = True
            self.async_write_ha_state()
            response = None
            try:
                response = await self.coordinator.client.upgrade_firmware(
                    type=update_type
                )
            finally:
                if not response or response.get("status") != "ok":
                    self._upgrade_in_progress = False
                    self.async_write_ha_state()
            if response and response.get("status") == "ok":
                self._upgrade_started = dt_util.utcnow()
                self._upgrade_status_generation += 1
                generation = self._upgrade_status_generation
                self._unsub_upgrade_status = async_track_time_interval(
                    self.hass,
                    partial(self._async_poll_upgrade_status, generation=generation),
                    UPGRADE_STATUS_INTERVAL,
                )
                self.async_write_ha_state()
                return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="firmware_update_failed",
        )
