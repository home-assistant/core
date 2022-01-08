"""RKI Covid numbers sensor."""

from datetime import datetime, timedelta
import logging
from typing import Callable, Dict, Optional

from rki_covid_parser.parser import RkiCovidParser
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, STATE_CLASS_MEASUREMENT
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator
from .const import (
    ATTR_COUNTY,
    ATTRIBUTION,
    CONF_BASEURL,
    CONF_DISTRICT_NAME,
    CONF_DISTRICTS,
)

_LOGGER = logging.getLogger(__name__)

# wait for x minutes after restart, before refreshing
SCAN_INTERVAL = timedelta(minutes=10)

# schema for each config entry
DISTRICT_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

# schema for each platform sensor
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_BASEURL): str,
        vol.Required(CONF_DISTRICTS): vol.All(cv.ensure_list, [DISTRICT_SCHEMA]),
    }
)

SENSORS = {
    "count": "mdi:virus",
    "deaths": "mdi:cross",
    "recovered": "mdi:bottle-tonic-plus-outline",
    "weekIncidence": "mdi:clipboard-pulse",
    "casesPer100k": "mdi:home-group",
    "newCases": "mdi:shield-bug",
    "newDeaths": "mdi:shield-cross",
    "newRecovered": "mdi:shield-sync",
    "hospitalizationCasesBaby": "mdi:baby-face-outline",
    "hospitalizationIncidenceBaby": "mdi:baby-face",
    "hospitalizationCasesChildren": "mdi:account-child-outline",
    "hospitalizationIncidenceChildren": "mdi:account-child",
    "hospitalizationCasesTeen": "mdi:face-woman",
    "hospitalizationIncidenceTeen": "mdi:face-woman-outline",
    "hospitalizationCasesGrown": "mdi:face-man",
    "hospitalizationIncidenceGrown": "mdi:face-man-outline",
    "hospitalizationCasesSenior": "mdi:account-cowboy-hat-outline",
    "hospitalizationIncidenceSenior": "mdi:account-cowboy-hat",
    "hospitalizationCasesOld": "mdi:human-white-cane",
    "hospitalizationIncidenceOld": "mdi:human-cane",
}


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.debug("setup sensor for platform")
    session = async_get_clientsession(hass)

    if CONF_BASEURL in config:
        _LOGGER.warning("Baseurl is not supported anymore.")

    parser = RkiCovidParser(session)
    coordinator = await get_coordinator(hass, parser)

    if coordinator is None or coordinator.data is None:
        raise PlatformNotReady("Data coordinator could not be initialized!")

    districts = config[CONF_DISTRICTS]

    sensors = [
        RKICovidNumbersSensor(coordinator, district[CONF_DISTRICT_NAME], info_type)
        for info_type in SENSORS
        for district in districts
    ]
    async_add_entities(sensors, update_before_add=True)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Create sensors from a config entry in the integrations UI."""
    _LOGGER.debug(f"create sensor from config entry {config_entry.data}")
    session = async_get_clientsession(hass)
    parser = RkiCovidParser(session)
    coordinator = await get_coordinator(hass, parser)

    if coordinator is None or coordinator.data is None:
        raise PlatformNotReady("Data coordinator could not be initialized!")

    district = config_entry.data[ATTR_COUNTY]
    sensors = [
        RKICovidNumbersSensor(coordinator, district, info_type) for info_type in SENSORS
    ]
    async_add_entities(sensors, update_before_add=True)


class RKICovidNumbersSensor(CoordinatorEntity):
    """Representation of a sensor."""

    name = None
    unique_id = None

    def __init__(
        self,
        coordinator: update_coordinator.DataUpdateCoordinator,
        district: Dict[str, str],
        info_type: str,
    ):
        """Initialize a new sensor."""
        _LOGGER.debug(f"initialize {info_type} sensor for {district}")
        super().__init__(coordinator)

        data = coordinator.data[district]

        if data.county:
            self.name = f"{data.county} {info_type}"
        else:
            self.name = f"{data.name} {info_type}"
        self.unique_id = f"{district}-{info_type}"
        self.district = district
        self.info_type = info_type
        self.updated = datetime.now()
        self._attr_attribution = f"last updated {self.updated.strftime('%d %b, %Y  %H:%M:%S')} \n{ATTRIBUTION}"
        self._attr_unit_of_measurement = self._measurement_unit()
        self._attr_state = self._native_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.district in self.coordinator.data
        )

    def _native_state(self) -> Optional[str]:
        """Return current state."""
        try:
            return getattr(self.coordinator.data[self.district], self.info_type)
        except AttributeError:
            return None

    @property
    def icon(self):
        """Return the icon."""
        return SENSORS[self.info_type]

    @property
    def state_class(self):
        """Opt-in for long-term statistics."""
        return STATE_CLASS_MEASUREMENT

    def _measurement_unit(self) -> str:
        """Return unit of measurement."""
        if self.info_type in ("count", "deaths", "recovered"):
            return "people"
        elif self.info_type in (
            "weekIncidence",
            "hospitalizationIncidenceBaby",
            "hospitalizationIncidenceChildren",
            "hospitalizationIncidenceTeen",
            "hospitalizationIncidenceGrown",
            "hospitalizationIncidenceSenior",
            "hospitalizationIncidenceOld",
        ):
            return "nb"
        else:
            return "cases"
