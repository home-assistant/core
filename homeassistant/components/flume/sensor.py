"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
import logging
from numbers import Number

from pyflume import FlumeData

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(minutes=1)


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
        flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

        coordinator = _create_flume_device_coordinator(hass, flume_device)

        flume_entity_list.extend(
            [
                FlumeSensor(
                    coordinator,
                    flume_device,
                    device_friendly_name,
                    device_id,
                    description,
                )
                for description in FLUME_QUERIES_SENSOR
            ]
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeSensor(CoordinatorEntity, SensorEntity):
    """Representation of the Flume sensor."""

    def __init__(
        self,
        coordinator,
        flume_device,
        name,
        device_id,
        description: SensorEntityDescription,
    ):
        """Initialize the Flume sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._flume_device = flume_device

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{description.key}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Flume, Inc.",
            model="Flume Smart Water Monitor",
            name=self.name,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self._flume_device.values:
            return None

        return _format_state_value(self._flume_device.values[sensor_key])

    async def async_added_to_hass(self):
        """Request an update when added."""
        await super().async_added_to_hass()
        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities
        await self.coordinator.async_request_refresh()


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None


def _create_flume_device_coordinator(hass, flume_device):
    """Create a data coordinator for the flume device."""

    async def _async_update_data():
        """Get the latest data from the Flume."""
        _LOGGER.debug("Updating Flume data")
        try:
            await hass.async_add_executor_job(flume_device.update_force)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
        _LOGGER.debug(
            "Flume update details: %s",
            {
                "values": flume_device.values,
                "query_payload": flume_device.query_payload,
            },
        )

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=flume_device.device_id,
        update_method=_async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=SCAN_INTERVAL,
    )
