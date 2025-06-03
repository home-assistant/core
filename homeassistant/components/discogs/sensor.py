"""Show the amount of records in a user's Discogs collection and its value."""

from __future__ import annotations # Keep this for modern Python syntax

from datetime import timedelta
import logging
import random

import discogs_client
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA, # Renamed PLATFORM_SCHEMA
    SensorEntity,
    SensorEntityDescription, # New import for sensor descriptions
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant # New import for HomeAssistant type
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.entity_platform import AddEntitiesCallback # New import for callback type
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType # New imports for typing

_LOGGER = logging.getLogger(__name__)

ATTR_IDENTITY = "identity"

# ATTRIBUTION is now typically handled via _attr_attribution in the entity class
# ATTRIBUTION = "Data provided by Discogs" # Remove this line

DEFAULT_NAME = "Discogs"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
ICON_CASH = "mdi:cash"
UNIT_RECORDS = "records"
UNIT_CURRENCY = "$"

SCAN_INTERVAL = timedelta(minutes=10)

SENSOR_COLLECTION_TYPE = "collection"
SENSOR_WANTLIST_TYPE = "wantlist"
SENSOR_RANDOM_RECORD_TYPE = "random_record"
SENSOR_COLLECTION_VALUE_MIN_TYPE = "collection_value_min"
SENSOR_COLLECTION_VALUE_MEDIAN_TYPE = "collection_value_median"
SENSOR_COLLECTION_VALUE_MAX_TYPE = "collection_value_max"

# SENSORS dictionary is replaced by SENSOR_TYPES tuple of SensorEntityDescription objects
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_COLLECTION_TYPE,
        name="Collection",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_WANTLIST_TYPE,
        name="Wantlist",
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_RANDOM_RECORD_TYPE,
        name="Random Record",
        icon=ICON_PLAYER,
        # unit_of_measurement is None, so it's omitted
    ),
    SensorEntityDescription( # New sensor definition for min value
        key=SENSOR_COLLECTION_VALUE_MIN_TYPE,
        name="Collection Value (Min)",
        icon=ICON_CASH,
        native_unit_of_measurement=UNIT_CURRENCY,
    ),
    SensorEntityDescription( # New sensor definition for median value
        key=SENSOR_COLLECTION_VALUE_MEDIAN_TYPE,
        name="Collection Value (Median)",
        icon=ICON_CASH,
        native_unit_of_measurement=UNIT_CURRENCY,
    ),
    SensorEntityDescription( # New sensor definition for max value
        key=SENSOR_COLLECTION_VALUE_MAX_TYPE,
        name="Collection Value (Max)",
        icon=ICON_CASH,
        native_unit_of_measurement=UNIT_CURRENCY,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES] # Automatically generate keys from descriptions

# PLATFORM_SCHEMA now uses SENSOR_PLATFORM_SCHEMA from homeassistant.components.sensor
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Discogs sensor."""
    token = config[CONF_TOKEN]
    name = config[CONF_NAME]

    try:
        _discogs_client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)

        # Fetch collection value data
        collection_value = _discogs_client.identity().collection_value

        discogs_data = {
            "user": _discogs_client.identity().name,
            "folders": _discogs_client.identity().collection_folders,
            "collection_count": _discogs_client.identity().num_collection,
            "wantlist_count": _discogs_client.identity().num_wantlist,
            "collection_value_min": collection_value["minimum"],
            "collection_value_median": collection_value["median"],
            "collection_value_max": collection_value["maximum"],
        }
    except discogs_client.exceptions.HTTPError as err:
        _LOGGER.error("API token is not valid or Discogs API error: %s", err)
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        DiscogsSensor(discogs_data, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities, True)


# Class now inherits from SensorEntity
class DiscogsSensor(SensorEntity):
    """Create a new Discogs sensor for a specific type."""

    _attr_attribution = "Data provided by Discogs" # Standard way to add attribution

    def __init__(
        self, discogs_data, name, description: SensorEntityDescription
    ) -> None:
        """Initialize the Discogs sensor."""
        self.entity_description = description
        self._discogs_data = discogs_data
        self._attrs: dict = {} # For random record details

        # Set entity name using description.name
        self._attr_name = f"{name} {description.name}"

    @property
    def extra_state_attributes(self):
        """Return the device state attributes of the sensor."""
        # Use _attr_native_value for the current state value
        if self._attr_native_value is None: # Removed _attrs check, as it might be empty for some sensor types
            return None

        if (
            self.entity_description.key == SENSOR_RANDOM_RECORD_TYPE
            and self._attrs # Check if _attrs has data for random record
        ):
            return {
                "cat_no": self._attrs["labels"][0]["catno"],
                "cover_image": self._attrs["cover_image"],
                "format": (
                    f"{self._attrs['formats'][0]['name']} ({self._attrs['formats'][0]['descriptions'][0]})"
                ),
                "label": self._attrs["labels"][0]["name"],
                "released": self._attrs["year"],
                # ATTR_ATTRIBUTION is now handled by _attr_attribution
                ATTR_IDENTITY: self._discogs_data["user"],
            }
        # For all other sensor types (collection count, wantlist count, collection value)
        # the identity attribute is sufficient, and attribution is handled by _attr_attribution
        return {
            ATTR_IDENTITY: self._discogs_data["user"],
        }

    def get_random_record(self) -> str | None: # Type hint for return
        """Get a random record suggestion from the user's collection."""
        # Index 0 in the folders is the 'All' folder
        collection = self._discogs_data["folders"][0]
        if collection.count > 0:
            random_index = random.randrange(collection.count)
            random_record = collection.releases[random_index].release

            self._attrs = random_record.data
            return (
                f"{random_record.data['artists'][0]['name']} -"
                f" {random_record.data['title']}"
            )
        return None # Return None if collection is empty

    def update(self) -> None: # Type hint for return
        """Set state to the amount of records or collection value."""
        # Use self.entity_description.key to identify the sensor type
        if self.entity_description.key == SENSOR_COLLECTION_TYPE:
            self._attr_native_value = self._discogs_data["collection_count"]
        elif self.entity_description.key == SENSOR_WANTLIST_TYPE:
            self._attr_native_value = self._discogs_data["wantlist_count"]
        elif self.entity_description.key == SENSOR_COLLECTION_VALUE_MIN_TYPE:
            self._attr_native_value = float(self._discogs_data["collection_value_min"].replace(UNIT_CURRENCY, ''))
        elif self.entity_description.key == SENSOR_COLLECTION_VALUE_MEDIAN_TYPE:
            self._attr_native_value = float(self._discogs_data["collection_value_median"].replace(UNIT_CURRENCY, ''))
        elif self.entity_description.key == SENSOR_COLLECTION_VALUE_MAX_TYPE:
            self._attr_native_value = float(self._discogs_data["collection_value_max"].replace(UNIT_CURRENCY, ''))
        else: # SENSOR_RANDOM_RECORD_TYPE
            self._attr_native_value = self.get_random_record()