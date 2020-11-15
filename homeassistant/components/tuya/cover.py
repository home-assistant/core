"""Support for Tuya covers."""
from datetime import timedelta

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
    """Set up Tuya Cover device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        entities.append(TuyaCover(device, platform))
    return entities


class TuyaCover(TuyaDevice, CoverEntity):
    """Tuya cover devices."""

    def __init__(self, tuya, platform):
        """Init tuya cover device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self._was_closing = False
        self._was_opening = False

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._tuya.support_stop():
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        state = self._tuya.state()
        if state == 1:
            self._was_opening = True
            self._was_closing = False
            return True
        return False

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        state = self._tuya.state()
        if state == 2:
            self._was_opening = False
            self._was_closing = True
            return True
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        state = self._tuya.state()
        if state != 2 and self._was_closing:
            return True
        if state != 1 and self._was_opening:
            return False
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._tuya.open_cover()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._tuya.close_cover()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        if self.is_closed is None:
            self._was_opening = False
            self._was_closing = False
        self._tuya.stop_cover()
