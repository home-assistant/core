"""Firmware updates for the Fibaro Home Center 3."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, override

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientTimeout, ClientConnectorCertificateError

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .firmware import FirmwareConnectionError, FirmwareError, FirmwarePermissionError, FirmwareState, FirmwareWorkflow, FirmwareUpdateGuard, FirmwareReleaseNotes, changelog_url

VERIFY_SSL = True  # Set False only for a trusted local hub with a self-signed certificate.

SCAN_INTERVAL = timedelta(seconds=30)
PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Add independent stable and beta firmware entities for the HC3."""
    if entry.runtime_data.read_fibaro_info().platform == "HC3":
        guard = FirmwareUpdateGuard()
        async_add_entities(
            [FibaroFirmware(hass, entry, channel, guard) for channel in ("stable", "beta")], True
        )


class FibaroFirmware(UpdateEntity):
    """Report and install stable or beta firmware updates."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_in_progress = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, channel: str, guard: FirmwareUpdateGuard) -> None:
        serial = entry.runtime_data.hub_serial
        self._channel = channel
        self._attr_entity_registry_enabled_default = channel == "stable"
        self._guard = guard
        self._attr_translation_key = f"firmware_{channel}"
        # Keep the original registry ID for stable, create a new one for beta.
        self._attr_unique_id = f"{serial}_firmware" + ("_beta" if channel == "beta" else "")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, serial)})
        self._session = async_get_clientsession(hass)
        self._url = entry.data[CONF_URL].rstrip("/")
        if not self._url.endswith("/api"):
            self._url += "/api"
        self._url += "/"
        self._auth = BasicAuth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self._workflow = FirmwareWorkflow(self._request, channel=channel, guard=guard)
        self._release_notes = FirmwareReleaseNotes(self._request)
        self._running = False
        self._firmware_available = False
        self._last_error = None
        self._action_error = None
        self._attr_installed_version = entry.runtime_data.read_fibaro_info().current_version
        self._attr_available = False

    @property
    @override
    def has_update(self) -> bool:
        return self._firmware_available

    async def _request(self, method: str, endpoint: str, *, anonymous: bool = False, **kwargs: Any) -> Any:
        try:
            async with self._session.request(
                method, self._url + endpoint, auth=None if anonymous else self._auth,
                timeout=ClientTimeout(total=15), allow_redirects=False, ssl=VERIFY_SSL,
                headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "pyfibaro", "Accept": "application/json"}, **kwargs,
            ) as response:
                if response.status == 404 and endpoint.startswith("service/actions/"):
                    return None
                response.raise_for_status()
                if response.status not in (200, 201):
                    raise FirmwareError(f"{method} /api/{endpoint}: unexpected HTTP {response.status}")
                return await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise FirmwarePermissionError(f"{method} /api/{endpoint}: HTTP {err.status}") from err
            if err.status in (502, 503, 504):
                raise FirmwareConnectionError(f"{method} /api/{endpoint}: HTTP {err.status} (temporarily unavailable)") from err
            raise FirmwareError(f"{method} /api/{endpoint}: HTTP {err.status}") from err
        except ClientConnectorCertificateError as err:
            raise FirmwareConnectionError(f"{method} /api/{endpoint}: TLS certificate verification failed") from err
        except (ClientError, TimeoutError) as err:
            raise FirmwareConnectionError(f"{method} /api/{endpoint}: {type(err).__name__}") from err
        except ValueError as err:
            raise FirmwareError(f"{method} /api/{endpoint}: invalid JSON") from err

    def _apply(self, state: FirmwareState | None, phase: str = "idle") -> None:
        self._attr_in_progress = self._running or self._guard.channel is not None or bool(state and state.active)
        self._attr_update_percentage = None
        if state is None:
            return
        self._attr_available = True
        self._attr_installed_version = state.installed
        self._attr_latest_version = state.latest
        self._attr_release_url = changelog_url(state.latest)
        self._firmware_available = state.available
        self._action_error = state.action_error
        self._attr_supported_features = (
            UpdateEntityFeature.RELEASE_NOTES
            | (UpdateEntityFeature(0) if state.status_source == "settings/info"
               else UpdateEntityFeature.PROGRESS | (UpdateEntityFeature.INSTALL if not state.action_error else UpdateEntityFeature(0)))
        )
        self._attr_extra_state_attributes = {
            "firmware_channel": self._channel,
            "local_update_status": state.local_status,
            "local_update_type": state.local_type,
            "local_update_version": state.local_version,
            "action_api_error": state.action_error,
            "update_conditions_met": state.conditions_met if state.status_source == "update" else None,
            "firmware_status_source": state.status_source,
            "firmware_status_error": state.action_error if state.status_source == "settings/info" else None,
            "installation_allowed": not bool(state.action_error) and state.conditions_met and not self._attr_in_progress,
        }
        self._attr_release_summary = (
            "Beta firmware: pre-release software, may be unstable."
            if self._channel == "beta" and state.available else None
        )
        if (
            phase != "install" and state.local_status == "Downloading"
            and state.available and state.local_version == state.latest
            and self._guard.channel in (None, self._channel)
        ):
            self._attr_update_percentage = state.progress

    def _publish(self, state: FirmwareState | None, phase: str) -> None:
        self._apply(state, phase)
        self.async_write_ha_state()

    @override
    async def async_update(self) -> None:
        if self._running:
            return
        try:
            state = await self._workflow.read(require_actions=False)
        except (FirmwareError, ValueError, TypeError, AttributeError) as err:
            if self._last_error != str(err):
                _LOGGER.warning("Could not read Fibaro firmware status: %s", err)
                self._last_error = str(err)
            self._attr_extra_state_attributes = {"firmware_error": str(err), "firmware_channel": self._channel}
            if not self._running:
                self._attr_available = False
                self._attr_release_url = None
            return
        if not self._running:
            self._last_error = None
            if state.action_error and self._action_error != state.action_error:
                _LOGGER.warning("Firmware detection works, installation blocked: %s", state.action_error)
            self._apply(state)

    @override
    async def async_release_notes(self) -> str | None:
        """Return the latest firmware's changelog using the HC3 API."""
        if not self.available or not (version := self.latest_version):
            return None
        try:
            notes = await self._release_notes.get(version)
        except FirmwareError as err:
            _LOGGER.debug("Could not fetch Fibaro release notes: %s", err)
            return None  # The vendor release_url remains available.
        if self.latest_version != version or not self.available:
            return None
        return notes

    @override
    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        if self._running or self._guard.channel is not None:
            raise HomeAssistantError("Firmware update already running on this Home Center")
        if self._action_error:
            raise HomeAssistantError(f"Installation blocked: {self._action_error}")
        target = self.latest_version
        channel = self._channel
        if not target or not channel or not self.has_update or (version is not None and version != target):
            raise HomeAssistantError("No matching firmware available")
        self._running = True
        self._publish(None, "download")
        try:
            await self._workflow.install(target, self._publish, channel)
        except (FirmwareError, ValueError, TypeError, AttributeError) as err:
            raise HomeAssistantError(f"Fibaro firmware update: {err}") from err
        finally:
            self._running = False
            self._attr_in_progress = False
            self._attr_update_percentage = None
            await self.async_update()
            self.async_write_ha_state()
