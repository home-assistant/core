"""Support for ReCollect Waste sensors."""
from typing import Callable, List

from aiorecollect.client import PickupType
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DATA_COORDINATOR, DOMAIN, LOGGER

ATTR_PICKUP_TYPES = "pickup_types"
ATTR_AREA_NAME = "area_name"
ATTR_NEXT_PICKUP_TYPES = "next_pickup_types"
ATTR_NEXT_PICKUP_DATE = "next_pickup_date"

DEFAULT_ATTRIBUTION = "Pickup data provided by ReCollect Waste"
DEFAULT_NAME = "recollect_waste"
DEFAULT_ICON = "mdi:trash-can-outline"

CONF_NAME = "name"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLACE_ID): cv.string,
        vol.Required(CONF_SERVICE_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


@callback
def async_get_pickup_type_names(
    entry: ConfigEntry, pickup_types: List[PickupType]
) -> List[str]:
    """Return proper pickup type names from their associated objects."""
    return [
        t.friendly_name
        if entry.options.get(CONF_FRIENDLY_NAME) and t.friendly_name
        else t.name
        for t in pickup_types
    ]


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable,
    discovery_info: dict = None,
):
    """Import Recollect Waste configuration from YAML."""
    LOGGER.warning(
        "Loading ReCollect Waste via platform setup is deprecated. "
        "Please remove it from your configuration."
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]
    async_add_entities([ReCollectWasteSensor(coordinator, entry)])


class ReCollectWasteSensor(CoordinatorEntity):
    """ReCollect Waste Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attributes = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._entry = entry
        self._state = None

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return DEFAULT_ICON

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return DEFAULT_NAME

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._entry.data[CONF_PLACE_ID]}{self._entry.data[CONF_SERVICE_ID]}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        pickup_event = self.coordinator.data[0]
        next_pickup_event = self.coordinator.data[1]
        next_date = str(next_pickup_event.date)

        self._state = pickup_event.date
        self._attributes.update(
            {
                ATTR_PICKUP_TYPES: async_get_pickup_type_names(
                    self._entry, pickup_event.pickup_types
                ),
                ATTR_AREA_NAME: pickup_event.area_name,
                ATTR_NEXT_PICKUP_TYPES: async_get_pickup_type_names(
                    self._entry, next_pickup_event.pickup_types
                ),
                ATTR_NEXT_PICKUP_DATE: next_date,
            }
        )
