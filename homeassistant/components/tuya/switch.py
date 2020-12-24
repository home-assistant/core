"""Support for Tuya switches."""
from datetime import timedelta

from homeassistant.components.switch import (
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    SwitchEntity,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import TuyaDevice
from .const import DOMAIN, TUYA_DATA, TUYA_DISCOVERY_NEW

SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_sensor(dev_ids):
        """Discover and add a discovered tuya sensor."""
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities,
            hass,
            dev_ids,
            platform,
        )
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(SENSOR_DOMAIN), async_discover_sensor
    )

    devices_ids = hass.data[DOMAIN]["pending"].pop(SENSOR_DOMAIN)
    await async_discover_sensor(devices_ids)


def _setup_entities(hass, dev_ids, platform):
    """Set up Tuya Switch device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        entities.append(TuyaSwitch(device, platform))
    return entities


class TuyaSwitch(TuyaDevice, SwitchEntity):
    """Tuya Switch Device."""

    def __init__(self, tuya, platform):
        """Init Tuya switch device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._tuya.state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._tuya.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._tuya.turn_off()
