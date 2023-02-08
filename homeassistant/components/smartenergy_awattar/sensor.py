"""Platform for Awattar sensor integration."""

from collections.abc import Callable, Mapping
import logging
from typing import Any

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AWATTAR_COORDINATOR, DOMAIN, MANUFACTURER, UNIT

_LOGGER: logging.Logger = logging.getLogger(__name__)


class ForecastSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor on the forecast of the energy prices integration."""

    def __init__(
        self,
        coordinator,
        entity_id,
    ) -> None:
        """Initialize the Base sensor."""
        super().__init__(coordinator)
        self._entity_id: str = entity_id
        self._name: str = "Awattar forecast"
        self._unit: str = UNIT

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return self._unit

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._entity_id)},
            "name": self._name,
            "manufacturer": MANUFACTURER,
            "model": "",
        }

    @property
    def capability_attributes(self) -> Mapping[str, Any] | None:
        """Return the capability attributes."""
        data: dict = self.coordinator.data

        if "forecast" in data:
            return {
                "forecast": data["forecast"],
            }

        return {}

    @property
    def available(self) -> bool:
        """Make the sensor (un)available based on the data availability."""
        return not self.coordinator.data


def _setup_entities(
    hass: HomeAssistant,
    async_add_entities: Callable,
    coordinator_name: str,
) -> None:
    async_add_entities(
        [
            ForecastSensor(
                hass.data[DOMAIN][coordinator_name],
                f"{SENSOR_DOMAIN}.{DOMAIN}_forecast",
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set sensors from a config entry created in the integrations UI."""

    entry_id: str = config_entry.entry_id
    config: dict = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the Awattar sensor for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    _setup_entities(hass, async_add_entities, f"{entry_id}_coordinator")


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up Awattar Sensor platform."""
    _LOGGER.debug("Setting up the Awattar sensor platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    _setup_entities(hass, async_add_entities, AWATTAR_COORDINATOR)
