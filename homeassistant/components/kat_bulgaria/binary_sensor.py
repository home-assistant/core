"""Setup for the binary sensor from the configuration.yaml."""

from datetime import datetime, timedelta
import logging

from kat_bulgaria.obligations import (
    REGEX_DRIVING_LICENSE,
    REGEX_EGN,
    KatError,
    KatFatalError,
    KatPersonDetails,
    check_obligations,
)
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    BINARY_SENSOR_ENTITY_PREFIX,
    BINARY_SENSOR_NAME_PREFIX,
    CONF_DRIVING_LICENSE,
    CONF_PERSON_EGN,
    CONF_PERSON_NAME,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kat_bulgaria"

SCAN_INTERVAL = timedelta(minutes=20)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PERSON_EGN): vol.All(cv.string, vol.Match(REGEX_EGN)),
        vol.Required(CONF_DRIVING_LICENSE): vol.All(
            cv.string, vol.Match(REGEX_DRIVING_LICENSE)
        ),
        vol.Optional(CONF_PERSON_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up the platform."""

    add_entities([KatObligationSensor(config)], update_before_add=True)


class KatObligationSensor(BinarySensorEntity):
    """An entity that holds the properties for the KAT fines."""

    def __init__(self, config) -> None:
        """Set up the KAT Sensor."""
        self.egn = config[CONF_PERSON_EGN]
        self.driver_license_number = config[CONF_DRIVING_LICENSE]
        self.person_name = None

        self.person = KatPersonDetails(self.egn, self.driver_license_number)

        # The name and entity identifier, defaults to driver license number
        identifier = self.driver_license_number

        # If a name is provided, use that in the name and in the entity
        if CONF_PERSON_NAME in config:
            self.person_name = config[CONF_PERSON_NAME]
            identifier = self.person_name

        # Set the sensor name and entity_id
        self._attr_name = f"{BINARY_SENSOR_NAME_PREFIX}{identifier}"
        self._attr_unique_id = f"{BINARY_SENSOR_ENTITY_PREFIX}{identifier}"

    def update(self) -> None:
        """Fetch new state data for the sensor."""

        try:
            data = check_obligations(self.person, request_timeout=5)
        except KatError as err:
            _LOGGER.info(str(err))
            return
        except (ValueError, KatFatalError) as err:
            _LOGGER.error(str(err))
            return

        if data is not None:
            self._attr_is_on = data.has_obligations
            self._attr_extra_state_attributes = {
                "last_updated": datetime.now().isoformat()
            }
