"""Support for Minut Point."""
import asyncio
import logging

from httpx import ConnectTimeout
from pypoint import PointSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import as_local, parse_datetime, utc_from_timestamp

from . import config_flow
from .const import (
    CONF_WEBHOOK_URL,
    DOMAIN,
    EVENT_RECEIVED,
    POINT_DISCOVERY_NEW,
    SCAN_INTERVAL,
    SIGNAL_UPDATE_ENTITY,
    SIGNAL_WEBHOOK,
)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIG_ENTRY_LOCK = "point_config_entry_lock"
CONFIG_ENTRY_IS_SETUP = "point_config_entry_is_setup"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Minut Point component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass, DOMAIN, conf[CONF_CLIENT_ID], conf[CONF_CLIENT_SECRET]
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Point from a config entry."""

    async def token_saver(token, **kwargs):
        _LOGGER.debug("Saving updated token %s", token)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: token}
        )

    session = PointSession(
        async_get_clientsession(hass),
        entry.data["refresh_args"][CONF_CLIENT_ID],
        entry.data["refresh_args"][CONF_CLIENT_SECRET],
        token=entry.data[CONF_TOKEN],
        token_saver=token_saver,
    )
    try:
        # pylint: disable-next=fixme
        # TODO Remove authlib constraint when refactoring this code
        await session.ensure_active_token()
    except ConnectTimeout as err:
        _LOGGER.debug("Connection Timeout")
        raise ConfigEntryNotReady from err
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Authentication Error")
        return False

    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    await async_setup_webhook(hass, entry, session)
    client = MinutPointClient(hass, entry, session)
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: client})
    hass.async_create_task(client.update())

    return True


async def async_setup_webhook(hass: HomeAssistant, entry: ConfigEntry, session):
    """Set up a webhook to handle binary sensor events."""
    if CONF_WEBHOOK_ID not in entry.data:
        webhook_id = webhook.async_generate_id()
        webhook_url = webhook.async_generate_url(hass, webhook_id)
        _LOGGER.info("Registering new webhook at: %s", webhook_url)

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_WEBHOOK_ID: webhook_id,
                CONF_WEBHOOK_URL: webhook_url,
            },
        )
    await session.update_webhook(
        entry.data[CONF_WEBHOOK_URL],
        entry.data[CONF_WEBHOOK_ID],
        ["*"],
    )

    webhook.async_register(
        hass, DOMAIN, "Point", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    session = hass.data[DOMAIN].pop(entry.entry_id)
    await session.remove_webhook()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
        _LOGGER.debug("Webhook %s: %s", webhook_id, data)
    except ValueError:
        return None

    if isinstance(data, dict):
        data["webhook_id"] = webhook_id
        async_dispatcher_send(hass, SIGNAL_WEBHOOK, data, data.get("hook_id"))
    hass.bus.async_fire(EVENT_RECEIVED, data)


class MinutPointClient:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, session: PointSession
    ) -> None:
        """Initialize the Minut data object."""
        self._known_devices: set[str] = set()
        self._known_homes: set[str] = set()
        self._hass = hass
        self._config_entry = config_entry
        self._is_available = True
        self._client = session

        async_track_time_interval(self._hass, self.update, SCAN_INTERVAL)

    async def update(self, *args):
        """Periodically poll the cloud for current state."""
        await self._sync()

    async def _sync(self):
        """Update local list of devices."""
        if not await self._client.update():
            self._is_available = False
            _LOGGER.warning("Device is unavailable")
            async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY)
            return

        async def new_device(device_id, platform):
            """Load new device."""
            config_entries_key = f"{platform}.{DOMAIN}"
            async with self._hass.data[DATA_CONFIG_ENTRY_LOCK]:
                if config_entries_key not in self._hass.data[CONFIG_ENTRY_IS_SETUP]:
                    await self._hass.config_entries.async_forward_entry_setup(
                        self._config_entry, platform
                    )
                    self._hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

            async_dispatcher_send(
                self._hass, POINT_DISCOVERY_NEW.format(platform, DOMAIN), device_id
            )

        self._is_available = True
        for home_id in self._client.homes:
            if home_id not in self._known_homes:
                await new_device(home_id, "alarm_control_panel")
                self._known_homes.add(home_id)
        for device in self._client.devices:
            if device.device_id not in self._known_devices:
                for platform in PLATFORMS:
                    await new_device(device.device_id, platform)
                self._known_devices.add(device.device_id)
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY)

    def device(self, device_id):
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id):
        """Return device availability."""
        if not self._is_available:
            return False
        return device_id in self._client.device_ids

    async def remove_webhook(self):
        """Remove the session webhook."""
        return await self._client.remove_webhook()

    @property
    def homes(self):
        """Return known homes."""
        return self._client.homes

    async def async_alarm_disarm(self, home_id):
        """Send alarm disarm command."""
        return await self._client.alarm_disarm(home_id)

    async def async_alarm_arm(self, home_id):
        """Send alarm arm command."""
        return await self._client.alarm_arm(home_id)


class MinutPointEntity(Entity):
    """Base Entity used by the sensors."""

    def __init__(self, point_client, device_id, device_class):
        """Initialize the entity."""
        self._async_unsub_dispatcher_connect = None
        self._client = point_client
        self._id = device_id
        self._name = self.device.name
        self._device_class = device_class
        self._updated = utc_from_timestamp(0)
        self._value = None

    def __str__(self):
        """Return string representation of device."""
        return f"MinutPoint {self.name}"

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.debug("Created device %s", self)
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback
        )
        await self._update_callback()

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def _update_callback(self):
        """Update the value of the sensor."""

    @property
    def available(self):
        """Return true if device is not offline."""
        return self._client.is_available(self.device_id)

    @property
    def device(self):
        """Return the representation of the device."""
        return self._client.device(self.device_id)

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_id(self):
        """Return the id of the device."""
        return self._id

    @property
    def extra_state_attributes(self):
        """Return status of device."""
        attrs = self.device.device_status
        attrs["last_heard_from"] = as_local(self.last_update).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        device = self.device.device
        return DeviceInfo(
            connections={
                (device_registry.CONNECTION_NETWORK_MAC, device["device_mac"])
            },
            identifiers={(DOMAIN, device["device_id"])},
            manufacturer="Minut",
            model=f"Point v{device['hardware_version']}",
            name=device["description"],
            sw_version=device["firmware"]["installed"],
            via_device=(DOMAIN, device["home"]),
        )

    @property
    def name(self):
        """Return the display name of this device."""
        return f"{self._name} {self.device_class.capitalize()}"

    @property
    def is_updated(self):
        """Return true if sensor have been updated."""
        return self.last_update > self._updated

    @property
    def last_update(self):
        """Return the last_update time for the device."""
        last_update = parse_datetime(self.device.last_update)
        return last_update

    @property
    def should_poll(self):
        """No polling needed for point."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"point.{self._id}-{self.device_class}"

    @property
    def value(self):
        """Return the sensor value."""
        return self._value
