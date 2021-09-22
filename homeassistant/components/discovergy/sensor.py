"""Discovergy sensor entity."""
import logging

from pydiscovergy import Discovergy
from pydiscovergy.error import AccessTokenExpired, HTTPError
from pydiscovergy.models import Meter

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, ELECTRICITY_SENSORS, MANUFACTURER, MIN_TIME_BETWEEN_UPDATES

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


def get_coordinator_for_meter(
    hass: HomeAssistant, meter: Meter, discovergy_instance: Discovergy
) -> DataUpdateCoordinator:
    """Create a new DataUpdateCoordinator for given meter."""

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await discovergy_instance.get_last_reading(meter.get_meter_id())
        except AccessTokenExpired as err:
            raise ConfigEntryAuthFailed(
                "Got token expired while communicating with API"
            ) from err
        except HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Unexpected error while communicating with API: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    return coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Discovergy sensors."""
    try:
        discovergy_instance = hass.data[DOMAIN][entry.entry_id]
        meters = await discovergy_instance.get_meters()
    except AccessTokenExpired as err:
        _LOGGER.debug("Token expired while communicating with API: %s", err)
        entry.async_start_reauth(hass)
    except HTTPError as err:
        raise ConfigEntryNotReady(f"Error communicating with API: {err}") from err
    except Exception as err:  # pylint: disable=broad-except
        raise ConfigEntryNotReady(
            f"Unexpected error while communicating with API: {err}"
        ) from err
    else:
        entities = []
        for meter in meters:
            if meter.measurement_type == "ELECTRICITY":
                # Get coordinator for meter, set config entry and fetch initial data
                # so we have data when entities are added
                coordinator = get_coordinator_for_meter(
                    hass, meter, discovergy_instance
                )
                coordinator.config_entry = entry
                await coordinator.async_config_entry_first_refresh()

                for description in ELECTRICITY_SENSORS:
                    # check if this meter has this data, then add this sensor
                    if description.key in coordinator.data.values:
                        entities.append(
                            DiscovergyElectricitySensor(description, meter, coordinator)
                        )

        async_add_entities(entities, False)


class DiscovergyElectricitySensor(CoordinatorEntity, SensorEntity):
    """Represents a discovergy electricity smart meter sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_name = (
            f"{meter.measurement_type.capitalize()} "
            f"{meter.location.street} "
            f"{meter.location.street_number} - "
            f"{description.name}"
        )
        self._attr_unique_id = f"{meter.full_serial_number}-{description.key}"
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, meter.get_meter_id())},
            ATTR_NAME: f"{meter.measurement_type.capitalize()} {meter.location.street} {meter.location.street_number}",
            ATTR_MODEL: f"{meter.type} {meter.full_serial_number}",
            ATTR_MANUFACTURER: MANUFACTURER,
        }

    @property
    def native_value(self) -> StateType:
        """Return the sensor state."""
        if self.coordinator.data:
            if (
                self.entity_description.key == "energy"
                or self.entity_description.key == "energyOut"
            ):
                return (
                    self.coordinator.data.values[self.entity_description.key]
                    / 10000000000
                )

            return self.coordinator.data.values[self.entity_description.key] / 1000

        return None
