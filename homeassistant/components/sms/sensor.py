"""Support for SMS dongle sensor."""
import logging

import gammu  # pylint: disable=import-error

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import DEVICE_CLASS_SIGNAL_STRENGTH, SIGNAL_STRENGTH_DECIBELS

from .const import DOMAIN, SMS_GATEWAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GSM Signal Sensor sensor."""
    gateway = hass.data[DOMAIN][SMS_GATEWAY]
    imei = await gateway.get_imei_async()
    async_add_entities(
        [
            GSMSignalSensor(
                hass,
                gateway,
                imei,
                SensorEntityDescription(
                    key="signal",
                    name=f"gsm_signal_imei_{imei}",
                    device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
                    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
                    entity_registry_enabled_default=False,
                ),
            )
        ],
        True,
    )


class GSMSignalSensor(SensorEntity):
    """Implementation of a GSM Signal sensor."""

    def __init__(self, hass, gateway, imei, description):
        """Initialize the GSM Signal sensor."""
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(imei))},
            "name": "SMS Gateway",
        }
        self._attr_unique_id = str(imei)
        self._hass = hass
        self._gateway = gateway
        self._state = None
        self.entity_description = description

    @property
    def available(self):
        """Return if the sensor data are available."""
        return self._state is not None

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state["SignalStrength"]

    async def async_update(self):
        """Get the latest data from the modem."""
        try:
            self._state = await self._gateway.get_signal_quality_async()
        except gammu.GSMError as exc:
            _LOGGER.error("Failed to read signal quality: %s", exc)

    @property
    def extra_state_attributes(self):
        """Return the sensor attributes."""
        return self._state
