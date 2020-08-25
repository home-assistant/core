"""The sia integration."""
import asyncio
from datetime import timedelta
import logging

from pysiaalarm.sia_account import SIAAccount
from pysiaalarm.sia_client import SIAClient
from pysiaalarm.sia_event import SIAEvent
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_ZONE,
    DEVICE_CLASS_TIMESTAMP,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow
from homeassistant.util.json import load_json

from .alarm_control_panel import SIAAlarmControlPanel
from .binary_sensor import SIABinarySensor
from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DEVICE_CLASS_ALARM,
    DOMAIN,
    HUB_SENSOR_NAME,
    HUB_ZONE,
    LAST_MESSAGE,
    PLATFORMS,
    UTCNOW,
)
from .sensor import SIASensor

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN, ALARM_CONTROL_PANEL_DOMAIN]
DEVICE_CLASS_ALARM = "alarm"
TYPES = [DEVICE_CLASS_ALARM, DEVICE_CLASS_MOISTURE, DEVICE_CLASS_SMOKE]

HUB_SENSOR_NAME = "last_heartbeat"
HUB_ZONE = 0

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the sia component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up sia from a config entry."""
    hub = SIAHub(hass, entry.data, entry.entry_id, entry.title)
    await hub.async_setup_hub()
    hass.data[DOMAIN][entry.entry_id] = hub
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    hub.sia_client.start(reuse_port=True)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN][entry.entry_id].sia_client.stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SIAHub:
    """Class for SIA Hubs."""

    def __init__(
        self, hass: HomeAssistant, hub_config: dict, entry_id: str, title: str
    ):
        """Create the SIAHub."""
        self._hass = hass
        self.states = {}
        self._port = int(hub_config[CONF_PORT])
        self.entry_id = entry_id
        self._title = title
        self._accounts = hub_config[CONF_ACCOUNTS]
        self.shutdown_remove_listener = None
        self._reactions = None

        self._zones = [
            {
                CONF_ACCOUNT: a[CONF_ACCOUNT],
                CONF_ZONE: HUB_ZONE,
                CONF_SENSORS: [DEVICE_CLASS_TIMESTAMP],
            }
            for a in self._accounts
        ]
        other_zones = [
            {
                CONF_ACCOUNT: a[CONF_ACCOUNT],
                CONF_ZONE: z,
                CONF_SENSORS: [
                    DEVICE_CLASS_ALARM,
                    DEVICE_CLASS_MOISTURE,
                    DEVICE_CLASS_SMOKE,
                ],
            }
            for a in self._accounts
            for z in range(1, int(a[CONF_ZONES]) + 1)
        ]
        self._zones.extend(other_zones)

        def process(event):
            self._update_states(event)

        sia_accounts = [
            SIAAccount(a[CONF_ACCOUNT], a.get(CONF_ENCRYPTION_KEY, None))
            for a in self._accounts
        ]
        self.sia_client = SIAClient("", self._port, sia_accounts, process)

        for zone in self._zones:
            for sensor in zone.get(CONF_SENSORS):
                self._create_sensor(zone[CONF_ACCOUNT], zone[CONF_ZONE], sensor)

        self.sia_client.start()

    async def async_setup_hub(self):
        """Add a device to the device_registry, register shutdown listener, load reactions."""
        device_registry = await dr.async_get_registry(self._hass)

        for acc in self._accounts:
            device_registry.async_get_or_create(
                config_entry_id=self.entry_id,
                identifiers={(DOMAIN, acc[CONF_ACCOUNT])},
                name=acc[CONF_ACCOUNT],
            )
        self.shutdown_remove_listener = self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_shutdown
        )
        self._reactions = load_json("homeassistant/components/sia/reactions.json")

    async def async_shutdown(self, _: Event):
        """Shutdown the SIA server."""
        await self.sia_client.stop()

    def _create_sensor(
        self, port: int, account: str, zone: int, entity_type: str, ping: int
    ):
        """Check if the entity exists, and creates otherwise."""
        sensor_id = self._get_id(account, zone, sensor_type)
        sensor_name = self._get_sensor_name(account, zone, sensor_type)
        ping = self._get_ping_interval(account)

    def _get_entity_id_and_name(
        self, account: str, zone: int = 0, entity_type: str = None
    ):
        """Give back a entity_id and name according to the variables."""
        if zone == 0:
            return (
                self._get_entity_id(account, zone, entity_type),
                f"{self._port} - {account} - Last Heartbeat",
            )
        if entity_type:
            return (
                self._get_entity_id(account, zone, entity_type),
                f"{self._port} - {account} - zone {zone} - {entity_type}",
            )
        return None

    def _get_entity_id(self, account: str, zone: int = 0, entity_type: str = None):
        """Give back a entity_id according to the variables, defaults to the hub sensor entity_id."""
        zone = int(zone)
        if zone == 0:
            return f"{self._port}_{account}_{HUB_SENSOR_NAME}"
        if entity_type:
            return f"{self._port}_{account}_{zone}_{entity_type}"
        return None

    def _get_ping_interval(self, account: str):
        """Return the ping interval for specified account."""
        for acc in self._accounts:
            if acc[CONF_ACCOUNT] == account:
                return timedelta(minutes=acc[CONF_PING_INTERVAL])
        return None

    def _update_states(self, event: SIAEvent):
        """Update the sensors."""
        # find the reactions for that code (if any)
        reaction = self._reactions.get(event.code)
        if not reaction:
            _LOGGER.warning(
                "Unhandled event code: %s, Message: %s, Full event: %s",
                event.code,
                event.message,
                event.sia_string,
            )
            return
        attr = reaction.get("attr")
        new_state = reaction.get("new_state")
        new_state_eval = reaction.get("new_state_eval")
        entity_id = self._get_entity_id(
            event.account, int(event.zone), reaction["type"]
        )

            # do the work (can be both a state and attribute)
            if new_state or new_state_eval:
                self.states[sensor_id].state = (
                    new_state
                    if new_state
                    else eval(new_state_eval)  # pylint: disable=eval-used
                )
            if attr:
                self.states[sensor_id].add_attribute(
                    {
                        "Last message": f"{utcnow().isoformat()}: SIA: {event.sia_string}, Message: {event.message}"
                    }
                )
        else:
            _LOGGER.warning(
                "Unhandled event type: %s, Message: %s", event.sia_string, event.message
            )

        # whenever a message comes in, the connection is good, so reset the availability timer for all devices of that account, excluding the last heartbeat (=zone==0).
        for sensor in self.states.values():
            if sensor.account == event.account and not isinstance(sensor, SIASensor):
                sensor.assume_available()
