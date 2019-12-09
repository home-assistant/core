"""Support for EDL21 Smart Meters."""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import Optional
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "edl21"
CONF_SERIAL_PORT = "serial_port"
ICON_POWER = "mdi:flash"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_SERIAL_PORT): cv.string})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the EDL21 sensor."""
    hass.data[DOMAIN] = EDL21(hass, config, async_add_entities)
    await hass.data[DOMAIN].connect()


class EDL21:
    """EDL21 handles telegrams sent by a compatible smart meter."""

    def __init__(self, hass, config, async_add_entities) -> None:
        """Initialize an EDL21 object."""
        from sml.asyncio import SmlProtocol

        self._cache = {}
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._proto = SmlProtocol(config[CONF_SERIAL_PORT])
        self._proto.add_listener(self.event, ["SmlGetListResponse"])

    async def connect(self):
        """Connect to an EDL21 reader."""
        await self._proto.connect(self._hass.loop)

    def event(self, message_body) -> None:
        """Handle events from pysml."""
        from sml import SmlGetListResponse

        assert isinstance(message_body, SmlGetListResponse)

        new_devices = []
        for telegram in message_body.get("valList", []):
            obis = telegram.get("objName")
            if not obis:
                continue

            device = self._cache.get(obis)
            if not device:
                device = self._cache[obis] = EDL21Entity(obis, telegram)
                new_devices.append(device)
            elif device.update_telegram(telegram):
                self._hass.async_create_task(device.async_update_ha_state())

        if new_devices:
            self._hass.async_add_job(
                self._async_add_entities(new_devices, update_before_add=True)
            )


class EDL21Entity(Entity):
    """Entity reading values from EDL21 telegram."""

    # OBIS format: A-B:C.D.E*F
    _OBIS_NAMES = {
        # A=1: Electricity
        # C=0: General purpose objects
        "1-0:0.0.9*255": "Electricity ID",
        # C=1: Active power +
        # D=8: Time integral 1
        # E=0: Total
        "1-0:1.8.0*255": "Positive active energy total",
        # E=1: Rate 1
        "1-0:1.8.1*255": "Positive active energy in tariff T1",
        # E=2: Rate 2
        "1-0:1.8.2*255": "Positive active energy in tariff T2",
        # D=17: Time integral 7
        # E=0: Total
        "1-0:1.17.0*255": "Last signed positive active energy total",
        # C=15: Active power absolute
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:15.7.0*255": "Absolute active instantaneous power",
        # C=16: Active power sum
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:16.7.0*255": "Sum active instantaneous power",
        # A=129: Manufacturer specific
        "129-129:199.130.3*255": "Manufacturer",
        "129-129:199.130.5*255": "Public Key",
    }

    def __init__(self, obis, telegram):
        """Initialize an EDL21Entity."""
        self._obis = obis
        self._telegram = telegram

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._obis

    @property
    def name(self) -> Optional[str]:
        """Return a name."""
        return self._OBIS_NAMES.get(self._obis)

    @property
    def state(self) -> str:
        """Return the value of the last received telegram."""
        value = self._telegram.get("value")
        if value is None:
            return STATE_UNKNOWN
        return value

    @property
    def device_state_attributes(self):
        """Enumerate supported attributes."""
        attr = self._telegram.copy()
        for key in ("objName", "unit", "value"):
            if key in attr:
                del attr[key]
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._telegram.get("unit")

    @property
    def icon(self):
        """Return an icon."""
        return ICON_POWER

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update_telegram(self, telegram: dict) -> bool:
        """Update attributes from last received telegram for this object."""
        if self._telegram == telegram:
            return False
        self._telegram = telegram
        return True
