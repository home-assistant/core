"""Support for Qwikswitch devices."""
from __future__ import annotations

import logging

from pyqwikswitch.async_ import QSUsb
from pyqwikswitch.qwikswitch import CMD_BUTTONS, QS_CMD, QS_ID, SENSORS, QSType
import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import (
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_URL,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "qwikswitch"

CONF_DIMMER_ADJUST = "dimmer_adjust"
CONF_BUTTON_EVENTS = "button_events"
CV_DIM_VALUE = vol.All(vol.Coerce(float), vol.Range(min=1, max=3))


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL, default="http://127.0.0.1:2020"): vol.Coerce(
                    str
                ),
                vol.Optional(CONF_DIMMER_ADJUST, default=1): CV_DIM_VALUE,
                vol.Optional(CONF_BUTTON_EVENTS, default=[]): cv.ensure_list_csv,
                vol.Optional(CONF_SENSORS, default=[]): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required("id"): str,
                                vol.Optional("channel", default=1): int,
                                vol.Required("name"): str,
                                vol.Required("type"): str,
                                vol.Optional("class"): DEVICE_CLASSES_SCHEMA,
                                vol.Optional("invert"): bool,
                            }
                        )
                    ],
                ),
                vol.Optional(CONF_SWITCHES, default=[]): vol.All(cv.ensure_list, [str]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class QSEntity(Entity):
    """Qwikswitch Entity base."""

    def __init__(self, qsid, name):
        """Initialize the QSEntity."""
        self._name = name
        self.qsid = qsid

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """QS sensors gets packets in update_packet."""
        return False

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"qs{self.qsid}"

    @callback
    def update_packet(self, packet):
        """Receive update packet from QSUSB. Match dispather_send signature."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Listen for updates from QSUSb via dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.qsid, self.update_packet)
        )


class QSToggleEntity(QSEntity):
    """Representation of a Qwikswitch Toggle Entity.

    Implemented:
     - QSLight extends QSToggleEntity and Light[2] (ToggleEntity[1])
     - QSSwitch extends QSToggleEntity and SwitchEntity[3] (ToggleEntity[1])

    [1] /helpers/entity.py
    [2] /components/light/__init__.py
    [3] /components/switch/__init__.py
    """

    def __init__(self, qsid, qsusb):
        """Initialize the ToggleEntity."""
        self.device = qsusb.devices[qsid]
        super().__init__(qsid, self.device.name)

    @property
    def is_on(self):
        """Check if device is on (non-zero)."""
        return self.device.value > 0

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        new = kwargs.get(ATTR_BRIGHTNESS, 255)
        self.hass.data[DOMAIN].devices.set_value(self.qsid, new)

    async def async_turn_off(self, **_):
        """Turn the device off."""
        self.hass.data[DOMAIN].devices.set_value(self.qsid, 0)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Qwiskswitch component setup."""

    # Add cmd's to in /&listen packets will fire events
    # By default only buttons of type [TOGGLE,SCENE EXE,LEVEL]
    cmd_buttons = set(CMD_BUTTONS)
    for btn in config[DOMAIN][CONF_BUTTON_EVENTS]:
        cmd_buttons.add(btn)

    url = config[DOMAIN][CONF_URL]
    dimmer_adjust = config[DOMAIN][CONF_DIMMER_ADJUST]
    sensors = config[DOMAIN][CONF_SENSORS]
    switches = config[DOMAIN][CONF_SWITCHES]

    def callback_value_changed(_qsd, qsid, _val):
        """Update entity values based on device change."""
        _LOGGER.debug("Dispatch %s (update from devices)", qsid)
        async_dispatcher_send(hass, qsid, None)

    session = async_get_clientsession(hass)
    qsusb = QSUsb(
        url=url,
        dim_adj=dimmer_adjust,
        session=session,
        callback_value_changed=callback_value_changed,
    )

    # Discover all devices in QSUSB
    if not await qsusb.update_from_devices():
        return False

    hass.data[DOMAIN] = qsusb

    comps: dict[Platform, list] = {
        Platform.SWITCH: [],
        Platform.LIGHT: [],
        Platform.SENSOR: [],
        Platform.BINARY_SENSOR: [],
    }

    sensor_ids = []
    for sens in sensors:
        try:
            _, _type = SENSORS[sens["type"]]
            sensor_ids.append(sens["id"])
            if _type is bool:
                comps[Platform.BINARY_SENSOR].append(sens)
                continue
            comps[Platform.SENSOR].append(sens)
            for _key in ("invert", "class"):
                if _key in sens:
                    _LOGGER.warning(
                        "%s should only be used for binary_sensors: %s", _key, sens
                    )
        except KeyError:
            _LOGGER.warning(
                "Sensor validation failed for sensor id=%s type=%s",
                sens["id"],
                sens["type"],
            )

    for qsid, dev in qsusb.devices.items():
        if qsid in switches:
            if dev.qstype != QSType.relay:
                _LOGGER.warning("You specified a switch that is not a relay %s", qsid)
                continue
            comps[Platform.SWITCH].append(qsid)
        elif dev.qstype in (QSType.relay, QSType.dimmer):
            comps[Platform.LIGHT].append(qsid)
        else:
            _LOGGER.warning("Ignored unknown QSUSB device: %s", dev)
            continue

    # Load platforms
    for comp_name, comp_conf in comps.items():
        if comp_conf:
            load_platform(hass, comp_name, DOMAIN, {DOMAIN: comp_conf}, config)

    def callback_qs_listen(qspacket):
        """Typically a button press or update signal."""
        # If button pressed, fire a hass event
        if QS_ID in qspacket:
            if qspacket.get(QS_CMD, "") in cmd_buttons:
                hass.bus.async_fire(f"qwikswitch.button.{qspacket[QS_ID]}", qspacket)
                return

            if qspacket[QS_ID] in sensor_ids:
                _LOGGER.debug("Dispatch %s ((%s))", qspacket[QS_ID], qspacket)
                async_dispatcher_send(hass, qspacket[QS_ID], qspacket)

        # Update all ha_objects
        hass.async_add_job(qsusb.update_from_devices)

    @callback
    def async_start(_):
        """Start listening."""
        qsusb.listen(callback_qs_listen)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start)

    @callback
    def async_stop(_):
        """Stop the listener."""
        hass.data[DOMAIN].stop()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_stop)

    return True
