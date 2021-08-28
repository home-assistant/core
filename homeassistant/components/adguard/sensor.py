"""Support for AdGuard Home sensors."""
from __future__ import annotations

from datetime import timedelta

from adguardhome import AdGuardHome, AdGuardHomeConnectionError

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TIME_MILLISECONDS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdGuardHomeDeviceEntity
from .const import DATA_ADGUARD_CLIENT, DATA_ADGUARD_VERSION, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdGuard Home sensor based on a config entry."""
    adguard = hass.data[DOMAIN][entry.entry_id][DATA_ADGUARD_CLIENT]

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][entry.entry_id][DATA_ADGUARD_VERSION] = version

    sensors = [
        AdGuardHomeDNSQueriesSensor(adguard, entry),
        AdGuardHomeBlockedFilteringSensor(adguard, entry),
        AdGuardHomePercentageBlockedSensor(adguard, entry),
        AdGuardHomeReplacedParentalSensor(adguard, entry),
        AdGuardHomeReplacedSafeBrowsingSensor(adguard, entry),
        AdGuardHomeReplacedSafeSearchSensor(adguard, entry),
        AdGuardHomeAverageProcessingTimeSensor(adguard, entry),
        AdGuardHomeRulesCountSensor(adguard, entry),
    ]

    async_add_entities(sensors, True)


class AdGuardHomeSensor(AdGuardHomeDeviceEntity, SensorEntity):
    """Defines a AdGuard Home sensor."""

    def __init__(
        self,
        adguard: AdGuardHome,
        entry: ConfigEntry,
        name: str,
        icon: str,
        measurement: str,
        unit_of_measurement: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize AdGuard Home sensor."""
        self._state: int | str | None = None
        self._unit_of_measurement = unit_of_measurement
        self.measurement = measurement

        super().__init__(adguard, entry, name, icon, enabled_default)

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
    def native_value(self) -> int | str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class AdGuardHomeDNSQueriesSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home DNS Queries sensor."""

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
            "AdGuard DNS Queries",
            "mdi:magnify",
            "dns_queries",
            "queries",
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.stats.dns_queries()


class AdGuardHomeBlockedFilteringSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home blocked by filtering sensor."""

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
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

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
            "AdGuard DNS Queries Blocked Ratio",
            "mdi:magnify-close",
            "blocked_percentage",
            PERCENTAGE,
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        percentage = await self.adguard.stats.blocked_percentage()
        self._state = f"{percentage:.2f}"


class AdGuardHomeReplacedParentalSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home replaced by parental control sensor."""

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
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

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
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

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
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

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
            "AdGuard Average Processing Speed",
            "mdi:speedometer",
            "average_speed",
            TIME_MILLISECONDS,
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        average = await self.adguard.stats.avg_processing_time()
        self._state = f"{average:.2f}"


class AdGuardHomeRulesCountSensor(AdGuardHomeSensor):
    """Defines a AdGuard Home rules count sensor."""

    def __init__(self, adguard: AdGuardHome, entry: ConfigEntry) -> None:
        """Initialize AdGuard Home sensor."""
        super().__init__(
            adguard,
            entry,
            "AdGuard Rules Count",
            "mdi:counter",
            "rules_count",
            "rules",
            enabled_default=False,
        )

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.filtering.rules_count(allowlist=False)
