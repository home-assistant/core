"""The sia integration."""
import asyncio
from datetime import timedelta
import logging

from pysiaalarm.sia_account import SIAAccount
from pysiaalarm.sia_client import SIAClient
from pysiaalarm.sia_event import SIAEvent
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SMOKE,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_ZONE,
    DEVICE_CLASS_TIMESTAMP,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from .alarm_control_panel import SIAAlarmControlPanel
from .binary_sensor import SIABinarySensor
from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
    PREVIOUS_STATE,
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
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up sia from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = SIAHub(
        hass, entry.data, entry.entry_id, entry.title
    )

    # await hass.data[DOMAIN][entry.entry_id]._create_device_registry()
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
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

    sensor_types_classes = {
        DEVICE_CLASS_ALARM: "SIAAlarmControlPanel",
        DEVICE_CLASS_MOISTURE: "SIABinarySensor",
        DEVICE_CLASS_SMOKE: "SIABinarySensor",
        DEVICE_CLASS_TIMESTAMP: "SIASensor",
    }

    reactions = {
        "BA": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_TRIGGERED},
        "BR": {"type": DEVICE_CLASS_ALARM, "new_state": PREVIOUS_STATE},
        "CA": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_AWAY},
        "CF": {
            "type": DEVICE_CLASS_ALARM,
            "new_state": STATE_ALARM_ARMED_CUSTOM_BYPASS,
        },
        "CG": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_AWAY},
        "CL": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_AWAY},
        "CP": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_AWAY},
        "CQ": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_AWAY},
        "GA": {"type": DEVICE_CLASS_SMOKE, "new_state": STATE_ON},
        "GH": {"type": DEVICE_CLASS_SMOKE, "new_state": STATE_OFF},
        "NL": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_ARMED_NIGHT},
        "OA": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_DISARMED},
        "OG": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_DISARMED},
        "OP": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_DISARMED},
        "OQ": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_DISARMED},
        "OR": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_DISARMED},
        "RP": {"type": DEVICE_CLASS_TIMESTAMP, "new_state_eval": "utcnow()"},
        "TA": {"type": DEVICE_CLASS_ALARM, "new_state": STATE_ALARM_TRIGGERED},
        "WA": {"type": DEVICE_CLASS_MOISTURE, "new_state": STATE_ON},
        "WH": {"type": DEVICE_CLASS_MOISTURE, "new_state": STATE_OFF},
        "YG": {"type": DEVICE_CLASS_TIMESTAMP, "attr": True},
    }

    def __init__(self, hass, hub_config, entry_id, title):
        """Create the SIAHub."""
        self._hass = hass
        self.states = {}
        self._port = int(hub_config[CONF_PORT])
        self.entry_id = entry_id
        self._title = title
        self._accounts = hub_config[CONF_ACCOUNTS]

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

    async def _create_device_registry(self):
        """Add a device to the device_registry."""
        device_registry = await dr.async_get_registry(self._hass)

        for acc in self._accounts:
            device_registry.async_get_or_create(
                config_entry_id=self.entry_id,
                identifiers={(DOMAIN, acc[CONF_ACCOUNT])},
                name=acc[CONF_ACCOUNT],
            )

    def _create_sensor(self, account, zone, sensor_type):
        """Check if the entity exists, and creates otherwise."""
        sensor_id = self._get_id(account, zone, sensor_type)
        sensor_name = self._get_sensor_name(account, zone, sensor_type)
        ping = self._get_ping_interval(account)

        sensor_type_constructor = self.sensor_types_classes.get(sensor_type)
        if sensor_type_constructor and sensor_name:
            if sensor_type_constructor == "SIAAlarmControlPanel":
                new_sensor = SIAAlarmControlPanel(
                    sensor_id, sensor_name, zone, ping, self._hass, account,
                )
            elif sensor_type_constructor == "SIABinarySensor":
                new_sensor = SIABinarySensor(
                    sensor_id,
                    sensor_name,
                    sensor_type,
                    zone,
                    ping,
                    self._hass,
                    account,
                )
            elif sensor_type_constructor == "SIASensor":
                new_sensor = SIASensor(
                    sensor_id,
                    sensor_name,
                    sensor_type,
                    zone,
                    ping,
                    self._hass,
                    account,
                )
            self.states[sensor_id] = new_sensor
        else:
            _LOGGER.warning("Hub: Upsert Sensor: Unknown device type: %s", sensor_type)

    def _get_id(self, account, zone=0, sensor_type=None):
        """Give back a entity_id according to the variables, defaults to the hub sensor entity_id."""
        zone = int(zone)
        if zone == 0:
            return f"{self._port}_{account}_{HUB_SENSOR_NAME}"
        else:
            if sensor_type:
                return f"{self._port}_{account}_{zone}_{sensor_type}"
            else:
                return None

    def _get_sensor_name(self, account, zone=0, sensor_type=None):
        """Give back a entity_id according to the variables, defaults to the hub sensor entity_id."""
        zone = int(zone)
        if zone == 0:
            return f"{self._port} - {account} - Last Heartbeat"
        else:
            if sensor_type:
                return f"{self._port} - {account} - zone {zone} - {sensor_type}"
            else:
                return None

    def _get_ping_interval(self, account):
        """Return the ping interval for specified account."""
        for acc in self._accounts:
            if acc[CONF_ACCOUNT] == account:
                return timedelta(minutes=acc[CONF_PING_INTERVAL])
        return None

    def _update_states(self, event: SIAEvent):
        """Update the sensors."""
        # find the reactions for that code (if any)
        reaction = self.reactions.get(event.code)
        if reaction:
            sensor_id = self._get_id(event.account, event.zone, reaction["type"])
            # find out which action to take, update attribute, new state or eval for new state
            attr = reaction.get("attr")
            new_state = reaction.get("new_state")
            new_state_eval = reaction.get("new_state_eval")

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
