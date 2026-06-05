"""Update platform for Supervisor."""

import logging
import re
from typing import Any

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Job, RaspberryPiFirmwareInfo
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ADDONS_COORDINATOR,
    ATTR_VERSION_LATEST,
    BOARDS_WITH_RASPBERRYPI_FIRMWARE,
    DOMAIN,
    MAIN_COORDINATOR,
)
from .coordinator import AddonData, async_register_rpi_firmware_in_dev_reg
from .entity import (
    HassioAddonEntity,
    HassioCoreEntity,
    HassioOSEntity,
    HassioSupervisorEntity,
)
from .handler import get_supervisor_client
from .jobs import JobSubscription
from .update_helper import update_addon, update_core, update_os, update_rpi_firmware

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTION = UpdateEntityDescription(
    translation_key="update",
    key=ATTR_VERSION_LATEST,
)

RPI_FIRMWARE_RELEASE_URL = (
    "https://github.com/raspberrypi/rpi-eeprom/blob/master/releases.md"
)


def _humanize_rpi_firmware_version(version: str | None) -> str | None:
    """Turn a raw firmware version into a human-readable string.

    The Supervisor reports the bootloader EEPROM build as a Unix timestamp,
    optionally suffixed with the VL805 EEPROM revision (`timestamp-hexstring`).
    Render the timestamp as a UTC `YYYY-MM-DD` date, appending
    `(VL805 hexstring)` when a VL805 revision is present.
    """
    if version is None:
        return None
    timestamp, _, vl805 = version.partition("-")
    try:
        date = dt_util.utc_from_timestamp(int(timestamp)).strftime("%Y-%m-%d")
    except ValueError:
        return version
    if vl805:
        return f"{date} (VL805 {vl805})"
    return date


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Supervisor update based on a config entry."""
    coordinator = hass.data[MAIN_COORDINATOR]

    entities: list[UpdateEntity] = [
        SupervisorSupervisorUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
        SupervisorCoreUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
    ]

    if coordinator.is_hass_os:
        entities.append(
            SupervisorOSUpdateEntity(
                coordinator=coordinator,
                entity_description=ENTITY_DESCRIPTION,
            )
        )

        # Firmware state only changes after a reboot (which restarts Core) or
        # as a result of the install action. Fetch the data here and create
        # the device with the RPi firmware update entity (unless the update
        # is blocked).
        os_info = coordinator.data.os
        if os_info is not None and os_info.board in BOARDS_WITH_RASPBERRYPI_FIRMWARE:
            client = get_supervisor_client(hass)
            try:
                rpi_firmware = await client.os.raspberry_pi_firmware_info()
            except SupervisorError as err:
                # Older supervisors (pre OS 18) don't expose the endpoint.
                rpi_firmware = None
                _LOGGER.debug("Raspberry Pi firmware info unavailable: %s", err)
            if rpi_firmware is not None and not rpi_firmware.update_blocked:
                async_register_rpi_firmware_in_dev_reg(
                    config_entry.entry_id, dr.async_get(hass)
                )
                entities.append(SupervisorRPiFirmwareUpdateEntity(rpi_firmware))

    addons_coordinator = hass.data[ADDONS_COORDINATOR]
    entities.extend(
        SupervisorAddonUpdateEntity(
            addon=addon,
            coordinator=addons_coordinator,
            entity_description=ENTITY_DESCRIPTION,
        )
        for addon in addons_coordinator.data.addons.values()
    )

    async_add_entities(entities)


class SupervisorAddonUpdateEntity(HassioAddonEntity, UpdateEntity):
    """Update entity to handle updates for the Supervisor add-ons.

    The ``addon_manager_update`` job emits a ``done=True`` WS event as soon as
    Supervisor finishes the container work, a few milliseconds before the
    ``/store/addons/<slug>/update`` HTTP call returns. If we clear
    ``_attr_in_progress`` on that event while the coordinator data still
    carries the pre-update version, the UI briefly flips back to
    "Update available" before ``async_install`` can refresh. ``_update_ongoing``
    survives both the WS done event and the base ``UpdateEntity`` reset, so
    the installing state remains until the coordinator confirms a new
    ``installed_version``.
    """

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.BACKUP
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )
    _update_ongoing: bool = False
    _version_before_update: str | None = None

    @property
    def _addon_data(self) -> AddonData:
        """Return the add-on data."""
        return self.coordinator.data.addons[self._addon_slug]

    @property
    def auto_update(self) -> bool:
        """Return true if auto-update is enabled for the add-on."""
        return self._addon_data.auto_update

    @property
    def title(self) -> str | None:
        """Return the title of the update."""
        return self._addon_data.addon.name

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._addon_data.addon.version_latest

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._addon_data.addon.version

    @property
    def in_progress(self) -> bool | None:
        """Return combined progress from the update job and refresh phase."""
        if self._update_ongoing:
            return True
        return self._attr_in_progress

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the add-on if any."""
        if not self.available:
            return None
        if self._addon_data.addon.icon:
            return f"/api/hassio/addons/{self._addon_slug}/icon"
        return None

    async def async_release_notes(self) -> str | None:
        """Return the release notes for the update."""
        if (
            changelog := await self.coordinator.get_changelog(self._addon_slug)
        ) is None:
            return None

        if self.latest_version is None or self.installed_version is None:
            return changelog

        regex_pattern = re.compile(
            rf"^#* {re.escape(self.latest_version)}\n"
            rf"(?:^(?!#* {re.escape(self.installed_version)}).*\n)*",
            re.MULTILINE,
        )
        match = regex_pattern.search(changelog)
        return match.group(0) if match else changelog

    async def async_install(
        self,
        version: str | None = None,
        backup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Install an update."""
        self._version_before_update = self.installed_version
        self._update_ongoing = True
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await update_addon(
                self.hass, self._addon_slug, backup, self.title, self.installed_version
            )
        except HomeAssistantError:
            self._update_ongoing = False
            self._version_before_update = None
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear the ongoing flag once the installed version has changed."""
        if (
            self._update_ongoing
            and self.installed_version != self._version_before_update
        ):
            self._update_ongoing = False
            self._version_before_update = None
        super()._handle_coordinator_update()

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(
                    self._update_job_changed,
                    name="addon_manager_update",
                    reference=self._addon_slug,
                )
            )
        )


class SupervisorOSUpdateEntity(HassioOSEntity, UpdateEntity):
    """Update entity to handle updates for the Home Assistant Operating System."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.BACKUP
    )
    _attr_title = "Home Assistant Operating System"

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        assert self.coordinator.data.os is not None
        return self.coordinator.data.os.version_latest

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        assert self.coordinator.data.os is not None
        return self.coordinator.data.os.version

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev or version.strategy is AwesomeVersionStrategy.UNKNOWN:
            return "https://github.com/home-assistant/operating-system/commits/dev"
        return (
            f"https://github.com/home-assistant/operating-system/releases/tag/{version}"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await update_os(self.hass, version, backup)


class SupervisorRPiFirmwareUpdateEntity(UpdateEntity):
    """Update entity for the Raspberry Pi firmware (bootloader EEPROM and VL805).

    Available on RPi4/RPi5/Yellow and uses `rpi-eeprom-update` via OS Agent.
    To apply the update, a reboot is required - the issue is raised by
    Supervisor after a successful update action.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_title = "Raspberry Pi Firmware"
    _attr_translation_key = "rpi_firmware_update"

    def __init__(self, firmware: RaspberryPiFirmwareInfo) -> None:
        """Initialize entity.

        No coordinator is used. The firmware state only changes after a reboot
        (which restarts Core and re-fetches at setup) or as a direct result of
        the install action (re-fetched in `async_install`), so periodic polling
        would never show anything new.
        """
        self._firmware = firmware
        self._attr_unique_id = "home_assistant_os_rpi_firmware"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "rpi_firmware")})

    @property
    def installed_version(self) -> str | None:
        """Composite installed firmware version.

        Once an update is applied (`update_pending`) the new version is
        reported as installed so the entity reads "up to date".
        REBOOT_REQUIRED is indicated after the update and actual switch to the
        new version applies after the reboot.
        """
        if self._firmware.update_pending:
            return _humanize_rpi_firmware_version(self._firmware.latest_version)
        return _humanize_rpi_firmware_version(self._firmware.current_version)

    @property
    def latest_version(self) -> str | None:
        """Composite available firmware version."""
        return _humanize_rpi_firmware_version(self._firmware.latest_version)

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity (the HA OS device icon)."""
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

    @property
    def release_url(self) -> str | None:
        """Return a link to the official Raspberry Pi bootloader docs."""
        return RPI_FIRMWARE_RELEASE_URL

    async def async_release_notes(self) -> str | None:
        """Return the pre-install warning and reboot notice as ha-alert boxes."""
        return (
            "<ha-alert alert-type='warning'>"
            "Do not interrupt the firmware flash. "
            "Power loss during the EEPROM update can brick your device."
            "</ha-alert>\n\n"
            "<ha-alert alert-type='info'>"
            "A reboot is required after install for the new firmware to "
            "take effect."
            "</ha-alert>\n"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        # The flash is a single blocking host call with no progress output, so
        # only a boolean in-progress state is available for the duration.
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await update_rpi_firmware(self.hass)
        except HomeAssistantError:
            self._attr_in_progress = False
            self.async_write_ha_state()
            raise
        self._attr_in_progress = False
        # The install staged/flashed the new firmware: re-fetch so the entity
        # reflects `update_pending` (reads "up to date") without a coordinator.
        client = get_supervisor_client(self.hass)
        try:
            self._firmware = await client.os.raspberry_pi_firmware_info()
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Error fetching Raspberry Pi firmware info: {err}"
            ) from err
        self.async_write_ha_state()


class SupervisorSupervisorUpdateEntity(HassioSupervisorEntity, UpdateEntity):
    """Update entity to handle updates for the Home Assistant Supervisor.

    The Supervisor update API blocks for the entire container download, then
    Supervisor restarts itself. The base UpdateEntity always resets
    ``_attr_in_progress`` after ``async_install`` returns, but at that point the
    restart is still ongoing. ``_update_ongoing`` survives that reset so the UI
    keeps showing the installing state until the coordinator refreshes with the
    new version after Supervisor comes back.
    """

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "Home Assistant Supervisor"
    _update_ongoing: bool = False
    _version_before_update: str | None = None

    @property
    def in_progress(self) -> bool | None:
        """Return combined progress from the update job and restart phase."""
        if self._update_ongoing:
            return True
        return self._attr_in_progress

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self.coordinator.data.supervisor.version_latest

    @property
    def installed_version(self) -> str:
        """Return the installed version."""
        return self.coordinator.data.supervisor.version

    @property
    def auto_update(self) -> bool:
        """Return true if auto-update is enabled for supervisor."""
        return self.coordinator.data.supervisor.auto_update

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev or version.strategy is AwesomeVersionStrategy.UNKNOWN:
            return "https://github.com/home-assistant/supervisor/commits/main"
        return f"https://github.com/home-assistant/supervisor/releases/tag/{version}"

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "/api/brands/integration/hassio/icon.png?placeholder=no"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._version_before_update = self.installed_version
        self._update_ongoing = True
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await self.coordinator.supervisor_client.supervisor.update()
        except SupervisorError as err:
            self._update_ongoing = False
            self._version_before_update = None
            self._attr_in_progress = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Error updating Home Assistant Supervisor: {err}"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear the ongoing flag once the installed version has changed."""
        if (
            self._update_ongoing
            and self.installed_version != self._version_before_update
        ):
            self._update_ongoing = False
            self._version_before_update = None
        super()._handle_coordinator_update()

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            # Also covers updates not initiated via async_install (CLI,
            # Supervisor self-update): capture the baseline so the installing
            # state survives the Supervisor restart phase.
            if not self._update_ongoing:
                self._version_before_update = self.installed_version
                self._update_ongoing = True
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(self._update_job_changed, name="supervisor_update")
            )
        )


class SupervisorCoreUpdateEntity(HassioCoreEntity, UpdateEntity):
    """Update entity to handle updates for Home Assistant Core."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.BACKUP
        | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "Home Assistant Core"

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        return self.coordinator.data.core.version_latest

    @property
    def installed_version(self) -> str | None:
        """Return the installed version."""
        return self.coordinator.data.core.version

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev:
            return "https://github.com/home-assistant/core/commits/dev"
        subdomain = "rc" if version.beta else "www"
        return f"https://{subdomain}.home-assistant.io/latest-release-notes/"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        self.async_write_ha_state()
        await update_core(self.hass, version, backup)

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(
                    self._update_job_changed, name="home_assistant_core_update"
                )
            )
        )
