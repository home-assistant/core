import logging
from homeassistant.components.number import NumberEntity
from .const import DOMAIN
from .sensor import TranslatableSensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up IoTMeter number entities from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    coordinator.async_add_number_entities = async_add_entities  # Store the function in the coordinator
    hass.data[DOMAIN]["platform"] = async_add_entities
    _LOGGER.debug("async_add_entities set in coordinator")
    await coordinator.async_request_refresh()


class ChargingCurrentNumber(TranslatableSensorEntity, NumberEntity):
    """Representation of a current slider."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement, min_value, max_value, step, fw_version='Unknown', smartmodule: bool = False):
        """Initialize the current slider."""
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = min_value
        self._coordinator = coordinator
        self._evse_current = 0
        self._fw_version: str = fw_version
        self._smartmodule: bool = smartmodule

    @property
    def state(self):
        evse_current = self.coordinator.data.get("EVSE_CURRENT")
        if evse_current is not None:
            self._evse_current = evse_current
        return self._evse_current

    async def async_set_native_value(self, value):
        """Set the current value."""
        self._attr_native_value = value
        self._evse_current = value
        await self.hass.async_add_executor_job(self.update_evse_current, value)

    def update_evse_current(self, value):
        """Update the EVSE current via HTTP request."""
        try:
            import requests
            self._evse_current = value

            response = requests.post(
                f"http://{self._coordinator.ip_address}:{self._coordinator.port}/updateRamSetting",
                json={"variable": "EVSE_CURRENT",
                      "value": self._evse_current}
            )
            response.raise_for_status()

        except requests.RequestException as err:
            _LOGGER.error(f"Error setting EVSE current: {err}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device: str = "Smartmodule" if self._smartmodule else "IoTMeter"
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name="iotmeter",
            manufacturer="Vilmio",
            model=device,
            sw_version=self._fw_version,
            via_device=(DOMAIN, "iotmeter")
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:power-plug"