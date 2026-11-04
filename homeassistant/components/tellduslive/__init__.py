"""Support for Telldus Live."""

import asyncio
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .api import Device, Session, TelldusLiveError, TelldusLiveRateLimitError
from .const import (
    DEFAULT_REQUEST_DELAY,
    DEFAULT_RETRY_INITIAL_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    DIM,
    DOMAIN,
    ERROR_AFTER_FAILURES,
    KEY_REQUEST_DELAY,
    KEY_RETRY_INITIAL_DELAY,
    KEY_RETRY_MAX_DELAY,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
    NOT_SO_PRIVATE_KEY,
    PUBLIC_KEY,
    RETRY_RESET_AFTER_OK,
    SIGNAL_UPDATE_ENTITY,
    SNAPSHOT_SAVE_DELAY,
    STORAGE_VERSION,
    TELLDUS_DISCOVERY_NEW,
    TURNON,
    UP,
    TelldusLiveStatus,
)

APPLICATION_NAME = "Home Assistant"

_LOGGER = logging.getLogger(__name__)


@dataclass
class TelldusLiveData:
    """Runtime data for a Telldus Live config entry."""

    client: TelldusLiveClient
    setup_task: asyncio.Task[None]


type TelldusLiveConfigEntry = ConfigEntry[TelldusLiveData]


async def async_setup_entry(hass: HomeAssistant, entry: TelldusLiveConfigEntry) -> None:
    """Create a tellduslive session."""
    conf = entry.data[KEY_SESSION]

    if CONF_HOST in conf:
        # Session(**conf) does blocking IO when
        # communicating with local devices.
        session = await hass.async_add_executor_job(partial(Session, **conf))
    else:
        session = Session(
            PUBLIC_KEY, NOT_SO_PRIVATE_KEY, application=APPLICATION_NAME, **conf
        )

    if not session.is_authorized:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        )

    client = TelldusLiveClient(hass, entry, session)
    entry.runtime_data = TelldusLiveData(
        client=client,
        setup_task=entry.async_create_background_task(
            hass, client.async_start(), "tellduslive_start"
        ),
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await client.async_restore()


async def _async_options_updated(
    hass: HomeAssistant, entry: TelldusLiveConfigEntry
) -> None:
    """Apply changed options without reloading the entry."""
    entry.runtime_data.client.async_options_updated()


async def async_unload_entry(
    hass: HomeAssistant, config_entry: TelldusLiveConfigEntry
) -> None:
    """Unload a config entry."""
    data = config_entry.runtime_data
    if not data.setup_task.done():
        data.setup_task.cancel()
    data.client.async_cancel_update()
    await hass.config_entries.async_unload_platforms_or_raise(
        config_entry, data.client.platforms
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: TelldusLiveConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing only devices that are no longer served by the account."""
    return not config_entry.runtime_data.client.is_in_use(
        {
            identifier
            for domain, identifier in device_entry.identifiers
            if domain == DOMAIN
        }
    )


async def async_remove_entry(
    hass: HomeAssistant, config_entry: TelldusLiveConfigEntry
) -> None:
    """Remove the stored snapshot of a removed config entry."""
    await Store(
        hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry.entry_id}"
    ).async_remove()


class TelldusLiveClient:
    """Get the latest data and update the states."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TelldusLiveConfigEntry,
        session: Session,
    ) -> None:
        """Initialize the Tellus data object."""
        self._known_devices: set[str] = set()
        self._device_infos: dict[str, dict[str, Any]] = {}
        self._platforms_lock = asyncio.Lock()
        self.platforms: set[str] = set()
        self._cancel_update: CALLBACK_TYPE | None = None
        self._stopped = False
        self._failures = 0
        self._backoff = 0
        self._ok_streak = 0
        self._updating = False
        self._first_refresh_done = False
        self._hubs_registered = False
        self._hub_ids: set[str] = set()
        self._restored = asyncio.Event()

        self._hass = hass
        self._config_entry = config_entry
        self._client = session
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry.entry_id}"
        )
        self._load_options()

    def _load_options(self) -> None:
        """Read the polling and retry settings from the config entry."""
        options = self._config_entry.options
        self._interval: float = options.get(
            KEY_SCAN_INTERVAL, self._config_entry.data[KEY_SCAN_INTERVAL]
        )
        self._retry_initial: float = options.get(
            KEY_RETRY_INITIAL_DELAY, DEFAULT_RETRY_INITIAL_DELAY
        )
        self._retry_max: float = options.get(
            KEY_RETRY_MAX_DELAY, DEFAULT_RETRY_MAX_DELAY
        )
        self._request_delay: float = options.get(
            KEY_REQUEST_DELAY, DEFAULT_REQUEST_DELAY
        )
        _LOGGER.debug("Update interval %s seconds", self._interval)

    @callback
    def async_options_updated(self) -> None:
        """Use changed options and re-arm the pending update timer."""
        self._load_options()
        if self._stopped or self._updating or self._cancel_update is None:
            return
        self._cancel_update()
        self._cancel_update = async_call_later(
            self._hass, self._next_delay(), self.update
        )

    async def async_start(self) -> None:
        """Start refreshing from the API once the snapshot is restored."""
        await self._restored.wait()
        await self.update()

    async def async_restore(self) -> None:
        """Create entities from the last stored snapshot without using the API."""
        try:
            await self._async_forward("sensor")
            snapshot = await self._store.async_load()
            if not snapshot:
                return
            self._client.load_state(snapshot["state"])
            self._device_infos = snapshot["device_infos"]
            for device_id in list(self._client.device_ids):
                if device_id in self._device_infos:
                    await self._discover(device_id)
                    self._known_devices.add(device_id)
        finally:
            self._restored.set()

    @property
    def signal_update(self) -> str:
        """Return the dispatcher signal sent after each refresh."""
        return SIGNAL_UPDATE_ENTITY.format(self._config_entry.entry_id)

    @property
    def status(self) -> TelldusLiveStatus:
        """Return the connection status."""
        if not self._first_refresh_done:
            return TelldusLiveStatus.STARTING
        if self._failures == 0:
            return TelldusLiveStatus.OK
        if self._failures < ERROR_AFTER_FAILURES:
            return TelldusLiveStatus.RETRYING
        return TelldusLiveStatus.ERROR

    @property
    def requests_last_hour(self) -> int:
        """Return the number of OK API responses during the last hour."""
        return self._client.ok_responses_last_hour()

    async def _async_forward(self, component: str) -> None:
        """Set up a platform once."""
        async with self._platforms_lock:
            if component not in self.platforms:
                await self._hass.config_entries.async_forward_entry_setups(
                    self._config_entry, [component]
                )
                self.platforms.add(component)

    def _snapshot(self) -> dict[str, Any]:
        """Return the data to persist."""
        return {
            "state": self._client.dump_state(),
            "device_infos": self._device_infos,
        }

    def _async_register_hubs(self, hubs: list[dict[str, Any]]) -> None:
        """Add the hubs associated with the current client to device_registry."""
        dev_reg = dr.async_get(self._hass)
        self._hub_ids.update(hub["id"] for hub in hubs)
        for hub in hubs:
            _LOGGER.debug("Connected hub %s", hub["name"])
            dev_reg.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                identifiers={(DOMAIN, hub["id"])},
                manufacturer="Telldus",
                name=hub["name"],
                model=hub["type"],
                sw_version=hub["version"],
            )

    def is_in_use(self, identifiers: set[str]) -> bool:
        """Return true if any identifier is a known device, hub or this service."""
        return bool(
            identifiers
            & {
                self._config_entry.entry_id,
                *self._hub_ids,
                *map(str, self._client.device_ids),
            }
        )

    def device_info(self, device_id: str) -> dict[str, Any] | None:
        """Return device info."""
        return self._device_infos.get(device_id)

    @staticmethod
    def identify_device(device: Device) -> str:
        """Find out what type of HA component to create."""
        if device.is_sensor:
            return "sensor"

        if device.methods & DIM:
            return "light"
        if device.methods & UP:
            return "cover"
        if device.methods & TURNON:
            return "switch"
        if device.methods == 0:
            return "binary_sensor"
        _LOGGER.warning("Unidentified device type (methods: %d)", device.methods)
        return "switch"

    async def _discover(self, device_id: str) -> None:
        """Discover the component."""
        device = self._client.device(device_id)
        component = self.identify_device(device)
        if device_id not in self._device_infos:
            # Sequential and spaced out to stay below the API rate limit.
            info = await self._hass.async_add_executor_job(device.info)
            if not device.is_sensor:
                await asyncio.sleep(self._request_delay)
            self._device_infos[device_id] = info or {}
        await self._async_forward(component)
        device_ids: list[Any] = []
        if device.is_sensor:
            device_ids.extend(
                (device.device_id, item.name, item.scale) for item in device.items
            )
        else:
            device_ids.append(device_id)
        for _id in device_ids:
            async_dispatcher_send(
                self._hass,
                TELLDUS_DISCOVERY_NEW.format(component, self._config_entry.entry_id),
                _id,
            )

    async def _async_fetch(self) -> None:
        """Fetch hubs, devices and sensors from the API."""
        if not self._hubs_registered:
            hubs = await self._hass.async_add_executor_job(self._client.get_clients)
            self._async_register_hubs(hubs)
            self._hubs_registered = True
        try:
            await self._hass.async_add_executor_job(self._client.update)
        finally:
            async_dispatcher_send(self._hass, self.signal_update)
        new_devices = {
            dev.device_id for dev in self._client.devices
        } - self._known_devices
        for device_id in new_devices:
            await self._discover(device_id)
            self._known_devices.add(device_id)
        self._store.async_delay_save(self._snapshot, SNAPSHOT_SAVE_DELAY)

    def _retry_delay(self, err: TelldusLiveError) -> float:
        """Return the backoff delay after a failed refresh."""
        delay = min(self._retry_initial * 2 ** (self._backoff - 1), self._retry_max)
        if isinstance(err, TelldusLiveRateLimitError) and err.retry_after:
            delay = max(delay, err.retry_after)
        return delay

    def _next_delay(self) -> float:
        """Return the wait until the next refresh."""
        if self._failures:
            return min(self._retry_initial * 2 ** (self._backoff - 1), self._retry_max)
        return self._interval

    async def update(self, *args: Any) -> None:
        """Poll the API, retrying with backoff when it fails."""
        delay = self._interval
        self._updating = True
        try:
            await self._async_fetch()
        except TelldusLiveError as err:
            self._failures += 1
            self._backoff += 1
            self._ok_streak = 0
            delay = self._retry_delay(err)
            _LOGGER.warning(
                "Telldus Live request failed (%s), retrying in %s seconds", err, delay
            )
        else:
            self._failures = 0
            self._ok_streak += 1
            if self._ok_streak >= RETRY_RESET_AFTER_OK:
                self._backoff = 0
        finally:
            self._updating = False
            self._first_refresh_done = True
            async_dispatcher_send(self._hass, self.signal_update)
            # An update still in flight at unload must not schedule another.
            if not self._stopped:
                self._cancel_update = async_call_later(self._hass, delay, self.update)

    @callback
    def async_cancel_update(self) -> None:
        """Cancel the scheduled update and stop polling."""
        self._stopped = True
        if self._cancel_update is not None:
            self._cancel_update()
            self._cancel_update = None

    def device(self, device_id: str) -> Device:
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id: str) -> bool:
        """Return device availability."""
        return device_id in self._client.device_ids
