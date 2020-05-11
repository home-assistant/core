"""Support for Tuya covers."""
from homeassistant.components.cover import (
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import TuyaDevice
from .const import DOMAIN, TUYA_DATA, TUYA_DISCOVERY_NEW

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_sensor(dev_ids):
        """Discover and add a discovered tuya sensor."""
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities, hass, dev_ids, platform,
        )
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(SENSOR_DOMAIN), async_discover_sensor
    )

    devices_ids = hass.data[DOMAIN]["pending"].pop(SENSOR_DOMAIN)
    await async_discover_sensor(devices_ids)


def _setup_entities(hass, dev_ids, platform):
    """Set up Tuya Cover device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        entity = tuya.get_device_by_id(dev_id)
        if entity is None:
            continue
        entities.append(TuyaCover(entity, platform))
    return entities


class TuyaCover(TuyaDevice, CoverEntity):
    """Tuya cover devices."""

    def __init__(self, tuya, platform):
        """Init tuya cover device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
        if self._tuya.support_stop():
            supported_features |= SUPPORT_STOP
        return supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        state = self._tuya.state()
        if state == 1:
            return False
        if state == 2:
            return True
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._tuya.open_cover()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._tuya.close_cover()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._tuya.stop_cover()
