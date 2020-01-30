"""Support for AdGuard Home sensors."""
from datetime import timedelta
import logging

from adguardhome import AdGuardHomeConnectionError

from homeassistant.components.adguard import AdGuardHomeDeviceEntity
from homeassistant.components.adguard.const import (
    DATA_ADGUARD_CLIENT,
    DATA_ADGUARD_VERION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up AdGuard Home sensor based on a config entry."""
    adguard = hass.data[DOMAIN][DATA_ADGUARD_CLIENT]

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][DATA_ADGUARD_VERION] = version

    sensors = [
        AdGuardHomeDNSQueriesSensor(adguard),
        AdGuardHomeBlockedFilteringSensor(adguard),
        AdGuardHomePercentageBlockedSensor(adguard),
        AdGuardHomeReplacedParentalSensor(adguard),
        AdGuardHomeReplacedSafeBrowsingSensor(adguard),
        AdGuardHomeReplacedSafeSearchSensor(adguard),
        AdGuardHomeAverageProcessingTimeSensor(adguard),
        AdGuardHomeRulesCountSensor(adguard),
    ]

    async_add_entities(sensors, True)


class AdGuardHomeSensor(AdGuardHomeDeviceEntity):
    """Defines a AdGuard Home sensor."""

    def __init__(
        self,
        adguard,
        name: str,
        icon: str,
        measurement: str,
        unit_of_measurement: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize AdGuard Home sensor."""
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.measurement = measurement

        super().__init__(adguard, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.adguard.host,
                str(self.adguard.port),
                "sensor",
                self.measurement,
            ]
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class AdGuardHomeDNSQueriesSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home DNS Queries sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard, "AdGuard DNS Queries", "mdi:magnify", "dns_queries", "queries"
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.dns_queries()


class AdGuardHomeBlockedFilteringSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home blocked by filtering sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard DNS Queries Blocked",
            "mdi:magnify-close",
            "blocked_filtering",
            "queries",
            enabled_default=False,
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.blocked_filtering()


class AdGuardHomePercentageBlockedSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home blocked percentage sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard DNS Queries Blocked Ratio",
            "mdi:magnify-close",
            "blocked_percentage",
            "%",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        percentage = await self.adguard.stats.blocked_percentage()
        self._state = f"{percentage:.2f}"


class AdGuardHomeReplacedParentalSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home replaced by parental control sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard Parental Control Blocked",
            "mdi:human-male-girl",
            "blocked_parental",
            "requests",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.replaced_parental()


class AdGuardHomeReplacedSafeBrowsingSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home replaced by safe browsing sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard Safe Browsing Blocked",
            "mdi:shield-half-full",
            "blocked_safebrowsing",
            "requests",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.replaced_safebrowsing()


class AdGuardHomeReplacedSafeSearchSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home replaced by safe search sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard Safe Searches Enforced",
            "mdi:shield-search",
            "enforced_safesearch",
            "requests",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.replaced_safesearch()


class AdGuardHomeAverageProcessingTimeSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home average processing time sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard Average Processing Speed",
            "mdi:speedometer",
            "average_speed",
            "ms",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        average = await self.adguard.stats.avg_processing_time()
        self._state = f"{average:.2f}"


class AdGuardHomeRulesCountSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home rules count sensor."""

    def __init__(self, adguard):
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            "AdGuard Rules Count",
            "mdi:counter",
            "rules_count",
            "rules",
            enabled_default=False,
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.filtering.rules_count()
