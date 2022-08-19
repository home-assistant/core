"""Sensor for displaying the number of result from Flume."""
from numbers import Number

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_QUERIES_SENSOR,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
)
from .coordinator import FlumeDeviceDataUpdateCoordinator
from .entity import FlumeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""
    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]

    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    config = config_entry.data
    name = config.get(CONF_NAME, DEFAULT_NAME)

    flume_entity_list = []
    for device in flume_devices.device_list:
        if device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR:
            continue

        device_id = device[KEY_DEVICE_ID]
        device_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]
        device_friendly_name = f"{name} {device_name}"

        # flume_device = FlumeData(
        #     flume_auth,
        #     device_id,
        #     device_timezone,
        #     SCAN_INTERVAL,
        #     update_on_init=False,
        #     http_session=http_session,
        # )

        coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass,
            flume_auth=flume_auth,
            device_id=device_id,
            device_timezone=device_timezone,
            http_session=http_session,
        )

        flume_entity_list.extend(
            [
                FlumeSensor(
                    coordinator=coordinator,
                    description=description,
                    name=device_friendly_name,
                    device_id=device_id
                    # flume_device,
                    # device_friendly_name,
                    # device_id,
                    # description,
                )
                for description in FLUME_QUERIES_SENSOR
            ]
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeSensor(FlumeEntity, SensorEntity):
    """Representation of the Flume sensor."""

    entity_description: SensorEntityDescription  # FlumeBinarySensorEntityDescription
    coordinator: FlumeDeviceDataUpdateCoordinator
    # def __init__(
    #     self,
    #     name: str,
    #     device_id: str,
    # ) -> None:
    #     super().__init__(coordinator, description, name, device_id)

    # def __init__(
    #     self,
    #     coordinator,
    #     flume_device,
    #     name,
    #     device_id,
    #     description: SensorEntityDescription,
    # ):
    #     """Initialize the Flume sensor."""
    #     super().__init__(coordinator)
    #     self.entity_description = description
    #     self._flume_device = flume_device
    #     self._attr_name = f"{name} {description.name}"
    #     self._attr_unique_id = f"{description.key}_{device_id}"
    #     self._attr_device_info = DeviceInfo(
    #         identifiers={(DOMAIN, device_id)},
    #         manufacturer="Flume, Inc.",
    #         model="Flume Smart Water Monitor",
    #         name=self.name,
    #     )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return _format_state_value(self.coordinator.flume_device.values[sensor_key])


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None
