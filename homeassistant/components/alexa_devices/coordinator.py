"""Support for Alexa Devices."""

from datetime import timedelta

from aioamazondevices.api import AmazonEchoApi
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from aioamazondevices.structures import (
    AmazonDevice,
    AmazonMediaState,
    AmazonVocalRecord,
    AmazonVolumeState,
)
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import _LOGGER, CONF_LOGIN_DATA, DOMAIN

SCAN_INTERVAL = 300

type AmazonConfigEntry = ConfigEntry[AmazonDevicesCoordinator]


class AmazonDevicesCoordinator(DataUpdateCoordinator[dict[str, AmazonDevice]]):
    """Base coordinator for Alexa Devices."""

    config_entry: AmazonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AmazonConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            config_entry=entry,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=SCAN_INTERVAL, immediate=False
            ),
        )
        self.api = AmazonEchoApi(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_LOGIN_DATA],
        )
        device_registry = dr.async_get(hass)
        self.previous_devices: set[str] = {
            identifier
            for device in device_registry.devices.get_devices_for_config_entry_id(
                entry.entry_id
            )
            if device.entry_type != dr.DeviceEntryType.SERVICE
            for identifier_domain, identifier in device.identifiers
            if identifier_domain == DOMAIN
        }
        self.previous_routines: set[str] = {
            routine.unique_id
            for routine in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
            if routine.domain == Platform.BUTTON
        }

        self._vocal_records: dict[str, AmazonVocalRecord] = {}
        self.api.on_history_event.append(self.history_state_event_handler)
        self.api.on_history_event.freeze()

        self._volume_states: dict[str, AmazonVolumeState] = {}
        self.api.on_volume_state_event.append(self.volume_state_event_handler)
        self.api.on_volume_state_event.freeze()

        self._media_states: dict[str, AmazonMediaState] = {}
        self.api.on_media_state_event.append(self.media_state_event_handler)
        self.api.on_media_state_event.freeze()

    async def _async_update_data(self) -> dict[str, AmazonDevice]:
        """Update device data."""
        try:
            await self.api.login.login_mode_stored_data()
            data = await self.api.get_devices_data()
        except CannotConnect as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotRetrieveData as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotAuthenticate as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        else:
            current_devices = set(data.keys())
            if stale_devices := self.previous_devices - current_devices:
                await self._async_remove_device_stale(stale_devices)
            self.previous_devices = current_devices

            current_routines = {slugify(routine) for routine in self.api.routines}
            if stale_routines := self.previous_routines - current_routines:
                await self._async_remove_routine_stale(stale_routines)
            self.previous_routines = current_routines

            return data

    async def _async_remove_device_stale(
        self,
        stale_devices: set[str],
    ) -> None:
        """Remove stale device."""
        device_registry = dr.async_get(self.hass)

        for serial_num in stale_devices:
            _LOGGER.debug(
                "Detected change in devices: serial %s removed",
                serial_num,
            )
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, serial_num)}
            )
            if device:
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

    async def _async_remove_routine_stale(
        self,
        stale_routines: set[str],
    ) -> None:
        """Remove stale routine."""
        entity_registry = er.async_get(self.hass)

        for routine in stale_routines:
            _LOGGER.debug(
                "Detected change in routines: routine %s removed",
                routine,
            )
            entity_id = entity_registry.async_get_entity_id(
                Platform.BUTTON,
                DOMAIN,
                f"{slugify(self.config_entry.unique_id)}-{slugify(routine)}",
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

    async def sync_history_state(self) -> None:
        """Sync history state."""
        try:
            self._vocal_records = await self.api.sync_history_state()
        except CannotAuthenticate as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(e)},
            ) from e
        except CannotConnect as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(e)},
            ) from e
        except BaseException as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(e)},
            ) from e

    async def history_state_event_handler(
        self, vocal_records: dict[str, AmazonVocalRecord]
    ) -> None:
        """Handle pushed vocal record events."""
        self._vocal_records = {**self._vocal_records, **vocal_records}
        self.async_update_listeners()

    @property
    def vocal_records(self) -> dict[str, AmazonVocalRecord]:
        """Vocal records of devices."""
        return self._vocal_records

    async def sync_media_state(self) -> None:
        """Sync media state."""
        try:
            await self.api.sync_media_state()
        except CannotAuthenticate as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (CannotConnect, TimeoutError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (CannotRetrieveData, ValueError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def media_state_event_handler(
        self, media_state: dict[str, AmazonMediaState]
    ) -> None:
        """Handle pushed media state changed events."""
        self._media_states = media_state
        self.async_update_listeners()

    @property
    def media_states(self) -> dict[str, AmazonMediaState]:
        """Media state of devices."""
        return self._media_states

    async def volume_state_event_handler(
        self, volume_states: dict[str, AmazonVolumeState]
    ) -> None:
        """Handle pushed volume change events."""
        self._volume_states = volume_states
        self.async_update_listeners()

    @property
    def volume_states(self) -> dict[str, AmazonVolumeState]:
        """Volumes of devices."""
        return self._volume_states
