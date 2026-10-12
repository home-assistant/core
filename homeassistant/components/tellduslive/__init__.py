"""Support for Telldus Live."""

import asyncio
from dataclasses import dataclass
from functools import partial
import logging

import probatio
from tellduslive import DIM, TURNON, UP, Session

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
    MIN_UPDATE_INTERVAL,
    NOT_SO_PRIVATE_KEY,
    PUBLIC_KEY,
    SCAN_INTERVAL,
    SIGNAL_UPDATE_ENTITY,
    TELLDUS_DISCOVERY_NEW,
)

APPLICATION_NAME = "Home Assistant"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_HOST, default=DOMAIN): cv.string,
                probatio.Optional(
                    CONF_SCAN_INTERVAL, default=SCAN_INTERVAL
                ): probatio.All(
                    cv.time_period, probatio.Clamp(min=MIN_UPDATE_INTERVAL)
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


@dataclass
class TelldusLiveData:
    """Runtime data for a Telldus Live config entry."""

    client: TelldusLiveClient
    setup_task: asyncio.Task[None]


type TelldusLiveConfigEntry = ConfigEntry[TelldusLiveData]


async def async_setup_entry(hass: HomeAssistant, entry: TelldusLiveConfigEntry) -> bool:
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
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        )

    interval = entry.data[KEY_SCAN_INTERVAL]
    _LOGGER.debug("Update interval %s seconds", interval)
    client = TelldusLiveClient(hass, entry, session, interval)
    entry.runtime_data = TelldusLiveData(
        client=client,
        setup_task=hass.loop.create_task(async_new_client(hass, client, entry)),
    )

    return True


async def async_new_client(
    hass: HomeAssistant, client: TelldusLiveClient, entry: TelldusLiveConfigEntry
) -> None:
    """Add the hubs associated with the current client to device_registry."""
    dev_reg = dr.async_get(hass)
    for hub in await client.async_get_hubs():
        _LOGGER.debug("Connected hub %s", hub["name"])
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, hub["id"])},
            manufacturer="Telldus",
            name=hub["name"],
            model=hub["type"],
            sw_version=hub["version"],
        )
    await client.update()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telldus Live component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: config[DOMAIN].get(CONF_HOST),
                KEY_SCAN_INTERVAL: config[DOMAIN][CONF_SCAN_INTERVAL],
            },
        )
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: TelldusLiveConfigEntry
) -> bool:
    """Unload a config entry."""
    data = config_entry.runtime_data
    if not data.setup_task.done():
        data.setup_task.cancel()
    data.client.async_cancel_update()
    return await hass.config_entries.async_unload_platforms(
        config_entry, data.client.platforms
    )


class TelldusLiveClient:
    """Get the latest data and update the states."""

    def __init__(self, hass, config_entry, session, interval):
        """Initialize the Tellus data object."""
        self._known_devices = set()
        self._device_infos = {}
        self._platforms_lock = asyncio.Lock()
        self.platforms: set[str] = set()
        self._cancel_update: CALLBACK_TYPE | None = None
        self._stopped = False

        self._hass = hass
        self._config_entry = config_entry
        self._client = session
        self._interval = interval

    async def async_get_hubs(self):
        """Return hubs registered for the user."""
        clients = await self._hass.async_add_executor_job(self._client.get_clients)
        return clients or []

    def device_info(self, device_id):
        """Return device info."""
        return self._device_infos.get(device_id)

    @staticmethod
    def identify_device(device):
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

    async def _discover(self, device_id):
        """Discover the component."""
        device = self._client.device(device_id)
        component = self.identify_device(device)
        self._device_infos.update(
            {device_id: await self._hass.async_add_executor_job(device.info)}
        )
        async with self._platforms_lock:
            if component not in self.platforms:
                await self._hass.config_entries.async_forward_entry_setups(
                    self._config_entry, [component]
                )
                self.platforms.add(component)
        device_ids = []
        if device.is_sensor:
            device_ids.extend(
                (device.device_id, item.name, item.scale) for item in device.items
            )
        else:
            device_ids.append(device_id)
        for _id in device_ids:
            async_dispatcher_send(
                self._hass, TELLDUS_DISCOVERY_NEW.format(component, DOMAIN), _id
            )

    async def update(self, *args):
        """Periodically poll the servers for current state."""
        try:
            if not await self._hass.async_add_executor_job(self._client.update):
                _LOGGER.warning("Failed request")
                return
            dev_ids = {dev.device_id for dev in self._client.devices}
            new_devices = dev_ids - self._known_devices
            # just await each discover as `gather` use up all HTTPAdapter pools
            for d_id in new_devices:
                await self._discover(d_id)
            self._known_devices |= new_devices
            async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY)
        finally:
            # An update still in flight at unload must not schedule another.
            if not self._stopped:
                self._cancel_update = async_call_later(
                    self._hass, self._interval, self.update
                )

    @callback
    def async_cancel_update(self) -> None:
        """Cancel the scheduled update and stop polling."""
        self._stopped = True
        if self._cancel_update is not None:
            self._cancel_update()
            self._cancel_update = None

    def device(self, device_id):
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id):
        """Return device availability."""
        return device_id in self._client.device_ids
