"""Support for Tuya fans."""
from datetime import timedelta
from typing import Optional

from homeassistant.components.fan import (
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import CONF_PLATFORM, STATE_OFF
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

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
    """Set up Tuya Fan device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        entities.append(TuyaFanDevice(device, platform))
    return entities


class TuyaFanDevice(TuyaDevice, FanEntity):
    """Tuya fan devices."""

    def __init__(self, tuya, platform):
        """Init Tuya fan device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self.speeds = []

    async def async_added_to_hass(self):
        """Create fan list when add to hass."""
        await super().async_added_to_hass()
        self.speeds.extend(self._tuya.speed_list())

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            self.turn_off()
        else:
            tuya_speed = percentage_to_ordered_list_item(self.speeds, percentage)
            self._tuya.set_speed(tuya_speed)

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            self.set_percentage(percentage)
        else:
            self._tuya.turn_on()

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self._tuya.turn_off()

    def oscillate(self, oscillating) -> None:
        """Oscillate the fan."""
        self._tuya.oscillate(oscillating)

    @property
    def speed_count(self) -> Optional[int]:
        """Return the number of speeds the fan supports."""
        if self.speeds is None:
            return super().speed_count
        return len(self.speeds)

    @property
    def oscillating(self):
        """Return current oscillating status."""
        if self.supported_features & SUPPORT_OSCILLATE == 0:
            return None
        if self.speed == STATE_OFF:
            return False
        return self._tuya.oscillating()

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self._tuya.state()

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed."""
        if not self.is_on:
            return 0
        if self.speeds is None:
            return None
        return ordered_list_item_to_percentage(self.speeds, self._tuya.speed())

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        if self._tuya.support_oscillate():
            return SUPPORT_SET_SPEED | SUPPORT_OSCILLATE
        return SUPPORT_SET_SPEED
