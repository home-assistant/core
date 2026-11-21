"""Update entity for Tasmota."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import re
from typing import Any, override

import aiohttp
from awesomeversion import AwesomeVersion
from hatasmota.const import CONF_TOPIC
from hatasmota.update import (
    TasmotaFirmware,
    TasmotaUpdate,
    TasmotaUpdateConfig,
    UpgradeResult,
    UpgradeState,
    get_install_blocker,
    is_official_ota_url,
)
from hatasmota.utils import get_topic_command

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import Event, HassJobType, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_device_registry_updated_event,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_REMOVE_DISCOVER_COMPONENT, DOMAIN
from .coordinator import TasmotaConfigEntry, TasmotaLatestReleaseUpdateCoordinator
from .discovery import DISCOVERY_DATA, TASMOTA_DISCOVERY_DEVICE_DISCOVERED

_LOGGER = logging.getLogger(__name__)

# Time the device has to answer an OtaUrl command
COMMAND_TIMEOUT = 10
# Time to check that the firmware image can be downloaded
DOWNLOAD_CHECK_TIMEOUT = 10
# Time the device has to download the image, restart and report a new version
INSTALL_TIMEOUT = timedelta(minutes=10)
# Default GroupTopic of Tasmota (MQTT_GRPTOPIC in tasmota/my_user_config.h)
DEFAULT_GROUP_TOPIC = "tasmotas"


def _error(
    translation_key: str, placeholders: dict[str, str] | None = None
) -> HomeAssistantError:
    """Return a translated install error."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TasmotaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota update entities."""
    runtime_data = config_entry.runtime_data

    device_registry = dr.async_get(hass)
    entities: dict[str, TasmotaUpdateEntity] = {}

    @callback
    def async_device_discovered(mac: str, update_config: TasmotaUpdateConfig) -> None:
        """Create or update the update entity of a discovered Tasmota device."""
        if (entity := entities.get(mac)) is not None:
            entity.async_discovery_update(update_config)
            return
        if device := device_registry.async_get_device_by_connection(
            (CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
        ):
            entity = TasmotaUpdateEntity(
                runtime_data.coordinator,
                device,
                TasmotaUpdate(
                    config=update_config, mqtt_client=runtime_data.mqtt_client
                ),
            )
            entities[mac] = entity

            @callback
            def _async_forget_entity() -> None:
                entities.pop(mac, None)

            entity.async_on_remove(_async_forget_entity)
            async_add_entities([entity])

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(Platform.UPDATE)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_DEVICE_DISCOVERED,
            async_device_discovered,
        )
    )


@dataclass
class _Install:
    """State of a running firmware install."""

    previous_version: str
    ota_url: str
    done: asyncio.Future[None]


class TasmotaUpdateEntity(
    CoordinatorEntity[TasmotaLatestReleaseUpdateCoordinator], UpdateEntity
):
    """Representation of a Tasmota update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_title = "Tasmota firmware"
    # in_progress is reported by the entity itself, see async_install
    _attr_supported_features = (
        UpdateEntityFeature.RELEASE_NOTES | UpdateEntityFeature.PROGRESS
    )

    _unsub_tasmota_device_updates: Callable[[], None] | None = None
    _install_task: asyncio.Task[None] | None = None

    def __init__(
        self,
        coordinator: TasmotaLatestReleaseUpdateCoordinator,
        device_entry: DeviceEntry,
        tasmota_update: TasmotaUpdate,
    ) -> None:
        """Initialize the Tasmota update entity."""
        super().__init__(coordinator=coordinator)
        self._config_entry_id = device_entry.config_entry_id
        self._attr_device_info = dr.DeviceInfo(connections=device_entry.connections)
        for connection_type, connection_value in device_entry.connections:
            if connection_type == dr.CONNECTION_NETWORK_MAC:
                self._connection = (connection_type, connection_value)
                self._attr_unique_id = connection_value
                break
        self._tasmota_update = tasmota_update
        self._device_id: str | None = None
        self._device_online = False
        self._removed = False
        self._install_caller_cancelled = False
        self._install: _Install | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to device-registry updates and to the device's MQTT topics."""
        await super().async_added_to_hass()
        self._tasmota_update.set_on_state_callback(self._firmware_updated)
        self._tasmota_update.set_on_restart_callback(self._device_restarted)
        self._tasmota_update.set_on_availability_callback(self._availability_updated)
        self._tasmota_update.set_on_upgrade_callback(self._upgrade_updated)
        await self._tasmota_update.subscribe_topics()
        device = dr.async_get(self.hass).async_get_device_by_connection(
            self._connection, self._config_entry_id
        )
        if device is None:
            return
        self._device_id = device.id
        self._unsub_tasmota_device_updates = async_track_device_registry_updated_event(
            self.hass,
            device.id,
            self._handle_device_registry_update,
            job_type=HassJobType.Callback,
        )
        self.async_on_remove(self._unsubscribe_device_updates)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT and abort a running install."""
        self._removed = True
        self._async_finish_install(_error("install_interrupted"))
        await self._tasmota_update.unsubscribe_topics()
        await super().async_will_remove_from_hass()

    @callback
    def async_discovery_update(self, update_config: TasmotaUpdateConfig) -> None:
        """Handle an updated discovery message of the device."""
        if self._tasmota_update.config_same(update_config):
            return
        self._tasmota_update.config_update(update_config)
        if (firmware := self._tasmota_update.firmware) is not None:
            # Deep sleep may have been switched on or off
            self._update_install_feature(firmware)
        if self.hass is not None and not self._removed:
            self.async_write_ha_state()
            self.hass.async_create_task(self._async_resubscribe(), eager_start=True)

    async def _async_resubscribe(self) -> None:
        """Subscribe to the topics of an updated discovery message."""
        await self._tasmota_update.subscribe_topics()
        if self._removed:
            # Removed while subscribing
            await self._tasmota_update.unsubscribe_topics()

    @callback
    def _handle_device_registry_update(
        self, event: Event[dr.EventDeviceRegistryUpdatedData]
    ) -> None:
        """Refresh state when the device's firmware version changes."""
        data: dict[str, Any] = event.data  # type: ignore[assignment]
        if data.get("action") != "update":
            return
        changes = data.get("changes", {})
        if not isinstance(changes, dict) or "sw_version" not in changes:
            return
        # Discovery is only sent by complete firmware images, never by the
        # minimal or safeboot image a device runs during its upgrade
        if (installed_version := self.installed_version) is not None:
            self._async_check_version(installed_version, restarted=False)
        self.async_write_ha_state()

    @callback
    def _unsubscribe_device_updates(self) -> None:
        """Unsubscribe from device-registry updates."""
        if self._unsub_tasmota_device_updates is not None:
            self._unsub_tasmota_device_updates()
            self._unsub_tasmota_device_updates = None

    @callback
    def _firmware_updated(self, firmware: TasmotaFirmware) -> None:
        """Handle firmware details reported in STATUS2 or INFO1."""
        install = self._install
        if install is None or not firmware.is_intermediate:
            # Keep the features while the device runs an intermediate image
            self._update_install_feature(firmware)
        if install is not None and not firmware.is_intermediate:
            self._async_check_version(firmware.version, restarted=False, sync=True)
        self.async_write_ha_state()

    def _update_install_feature(self, firmware: TasmotaFirmware) -> None:
        """Offer install only for official release builds."""
        blocker = get_install_blocker(firmware)
        if blocker is None and not self._tasmota_update.deep_sleep_enabled:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL
            return
        _LOGGER.debug(
            "%s: no firmware install for %s(%s): %s",
            self.entity_id,
            firmware.version,
            firmware.image,
            blocker or "deep sleep",
        )
        self._attr_supported_features &= ~UpdateEntityFeature.INSTALL

    @callback
    def _device_restarted(self, firmware: TasmotaFirmware) -> None:
        """Handle a device which has booted, as told by INFO1.

        A minimal or safeboot image is a step of the device's own upgrade.
        """
        if not firmware.is_intermediate:
            self._async_check_version(firmware.version, restarted=True, sync=True)

    @callback
    def _async_check_version(
        self, version: str, *, restarted: bool, sync: bool = False
    ) -> None:
        """Finish a running install if the device reports another version.

        The image on ota.tasmota.com is the latest release, which can briefly differ
        from the release reported by GitHub. Any newer version is a success.
        """
        if (install := self._install) is None:
            return
        new, previous = (
            AwesomeVersion(version),
            AwesomeVersion(install.previous_version),
        )
        if new > previous:
            if sync and self._device_id and self.installed_version != version:
                # Show the new version right away, discovery confirms it later
                dr.async_get(self.hass).async_update_device(
                    self._device_id, sw_version=version
                )
            self._async_finish_install()
        elif new < previous:
            self._async_finish_install(
                _error(
                    "unexpected_version",
                    {"version": version, "previous": install.previous_version},
                )
            )
        elif restarted:
            self._async_finish_install(_error("same_version", {"version": version}))

    async def _availability_updated(self, available: bool) -> None:
        """Track whether the device is online."""
        self._device_online = available

    @callback
    def _upgrade_updated(self, result: UpgradeResult) -> None:
        """Handle an upgrade state reported by the device."""
        if (install := self._install) is None:
            return
        if result.state in (UpgradeState.FAILED, UpgradeState.REJECTED):
            self._async_finish_install(
                _error("upgrade_failed", {"message": result.message})
            )
        elif result.state is UpgradeState.STARTED and result.url != install.ota_url:
            # The OtaUrl was changed after it was checked
            self._async_finish_install(
                _error("upgrade_url_mismatch", {"url": str(result.url)})
            )

    @callback
    def _async_install_timeout(self, _now: datetime) -> None:
        """Fail the install if the device did not report a new version in time."""
        self._async_finish_install(
            _error(
                "install_timeout",
                {"minutes": str(int(INSTALL_TIMEOUT.total_seconds() // 60))},
            )
        )

    @callback
    def _async_finish_install(self, error: HomeAssistantError | None = None) -> None:
        """Finish a running install, with an error if it failed."""
        if self._install is None or self._install.done.done():
            return
        if error is None:
            self._install.done.set_result(None)
        else:
            self._install.done.set_exception(error)

    @property
    @override
    def in_progress(self) -> bool:
        """Return True while a firmware install runs."""
        return self._install_task is not None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Let the device download the latest release from ota.tasmota.com."""
        if self._install_task is not None:
            raise _error("install_in_progress")
        self._install_caller_cancelled = False
        task = self.hass.async_create_background_task(
            self._async_install(),
            f"Tasmota firmware install {self.entity_id}",
            eager_start=False,
        )
        self._install_task = task
        task.add_done_callback(self._async_install_done)
        self.async_write_ha_state()
        try:
            # Once Upgrade 1 is sent, the device flashes on its own. The install
            # is followed until it ends, also if the calling action is cancelled.
            await asyncio.shield(task)
        except asyncio.CancelledError:
            self._install_caller_cancelled = True
            raise

    @callback
    def _async_install_done(self, task: asyncio.Task[None]) -> None:
        """Handle the end of an install."""
        self._install_task = None
        if (
            self._install_caller_cancelled
            and not task.cancelled()
            and (err := task.exception()) is not None
        ):
            _LOGGER.warning("%s: firmware install failed: %s", self.entity_id, err)
        if not self._removed:
            self.async_write_ha_state()

    def _check_firmware(self) -> TasmotaFirmware:
        """Return the firmware if it may be upgraded and the device is online."""
        firmware = self._tasmota_update.firmware
        if (
            firmware is None
            or get_install_blocker(firmware) is not None
            or self._tasmota_update.deep_sleep_enabled
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="install_not_supported",
                translation_placeholders={
                    "version": firmware.version if firmware else "unknown"
                },
            )
        if not self._device_online:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_offline"
            )
        return firmware

    async def _async_install(self) -> None:
        """Check the device and its firmware, then upgrade it."""
        firmware = self._check_firmware()
        installed_version = self.installed_version
        self._check_topic()
        try:
            previous_ota_url = await self._tasmota_update.get_ota_url(COMMAND_TIMEOUT)
        except TimeoutError as err:
            raise _error("no_response") from err
        ota_url: str | None = None
        try:
            ota_url = await self._async_reset_ota_url()
            await self._async_verify_ota_url(ota_url, firmware)
            await self._async_upgrade(firmware, installed_version, ota_url)
        except HomeAssistantError:
            if not self._removed and previous_ota_url not in ("", ota_url):
                await self._async_restore_ota_url(previous_ota_url)
            raise

    def _check_topic(self) -> None:
        """Make sure commands to the device's topic only reach this device.

        Checked before every command which changes the device, because the topic
        can change or become shared while an install runs.
        """
        tasmota_update = self._tasmota_update
        command_topic = tasmota_update.command_topic
        discovery_data: dict[str, dict] = self.hass.data.get(DISCOVERY_DATA, {})
        payload = discovery_data.get(tasmota_update.mac)
        issue_registry = ir.async_get(self.hass)
        if (
            not payload
            or get_topic_command(payload) != command_topic
            or issue_registry.async_get_issue(
                DOMAIN, f"topic_no_prefix_{tasmota_update.mac}"
            )
        ):
            # The device announced another topic, which discovery did not accept
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="topic_changed"
            )
        placeholders = {"topic": command_topic}
        if issue_registry.async_get_issue(DOMAIN, f"topic_duplicated_{command_topic}"):
            # Every device on the topic would act on OtaUrl and Upgrade
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="topic_duplicated",
                translation_placeholders=placeholders,
            )
        # Tasmota subscribes to <command topic>#, also for the default group
        # topic, so a device whose command topic or group command topic is a
        # prefix of this command topic receives these commands as well
        for mac, other_payload in discovery_data.items():
            if not other_payload:
                continue
            if command_topic.startswith(
                get_topic_command({**other_payload, CONF_TOPIC: DEFAULT_GROUP_TOPIC})
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="topic_group",
                    translation_placeholders=placeholders,
                )
            if mac != tasmota_update.mac and command_topic.startswith(
                other_topic := get_topic_command(other_payload)
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="topic_overlap",
                    translation_placeholders={**placeholders, "other": other_topic},
                )

    async def _async_reset_ota_url(self) -> str:
        """Let the device report the OtaUrl its firmware was built with.

        For official builds this is the image of the device's own variant.
        """
        if self._removed:
            raise _error("install_interrupted")
        self._check_topic()
        try:
            return await self._tasmota_update.reset_ota_url(COMMAND_TIMEOUT)
        except TimeoutError as err:
            raise _error("no_response") from err

    async def _async_verify_ota_url(self, url: str, firmware: TasmotaFirmware) -> None:
        """Check that url is the official image for the device and available."""
        if not is_official_ota_url(url, firmware):
            raise _error("unexpected_ota_url", {"url": url})
        session = async_get_clientsession(self.hass)
        try:
            # ota.tasmota.com serves the images directly. A redirect is not
            # followed by the ESP8266 HTTP client, so it counts as unavailable.
            async with session.head(
                url,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=DOWNLOAD_CHECK_TIMEOUT),
            ) as response:
                status = response.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise _error(
                "download_check_failed",
                {"url": url, "error": str(err) or type(err).__name__},
            ) from err
        if status != HTTPStatus.OK:
            raise _error("firmware_not_available", {"url": url, "status": str(status)})

    async def _async_upgrade(
        self, firmware: TasmotaFirmware, installed_version: str | None, ota_url: str
    ) -> None:
        """Send Upgrade 1 and wait until the device reports the result."""
        if self._removed:
            raise _error("install_interrupted")
        # STATUS2, INFO1, LWT or discovery may have changed things during the checks
        self._check_topic()
        if (
            self._check_firmware() != firmware
            or self.installed_version != installed_version
        ):
            raise _error("firmware_changed")
        self._install = _Install(
            previous_version=firmware.version,
            ota_url=ota_url,
            done=self.hass.loop.create_future(),
        )
        cancel_timeout = async_call_later(
            self.hass, INSTALL_TIMEOUT, self._async_install_timeout
        )
        try:
            await self._tasmota_update.start_upgrade()
            await self._install.done
        finally:
            cancel_timeout()
            self._install = None

    async def _async_restore_ota_url(self, previous_url: str) -> None:
        """Restore the OtaUrl the device had before a failed install."""
        try:
            self._check_topic()
            await self._tasmota_update.set_ota_url(previous_url, COMMAND_TIMEOUT)
        except TimeoutError, ValueError, HomeAssistantError:
            _LOGGER.warning(
                "%s: could not restore OtaUrl %s", self.entity_id, previous_url
            )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed version."""
        if self.hass and (
            device := dr.async_get(self.hass).async_get_device_by_connection(
                self._connection, self._config_entry_id
            )
        ):
            return device.sw_version
        return None

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest version."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.tag_name.removeprefix("v")

    @property
    @override
    def release_url(self) -> str | None:
        """Return the release URL."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.html_url

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the release summary."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.name

    @override
    async def async_release_notes(self) -> str | None:
        """Return full release notes."""
        if not self.coordinator.data or not self.coordinator.data.body:
            return None
        # Remove the picture tag, it uses relative URLs that won't work in the UI
        return re.sub(
            r"^<picture>.*?</picture>", "", self.coordinator.data.body, flags=re.DOTALL
        )
