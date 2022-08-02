"""Support for openexchangerates.org exchange rates service."""
from __future__ import annotations

from dataclasses import dataclass, field

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_BASE, CONF_NAME, CONF_QUOTE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_UPDATE_INTERVAL, DOMAIN, LOGGER
from .coordinator import OpenexchangeratesCoordinator

ATTRIBUTION = "Data provided by openexchangerates.org"

DEFAULT_BASE = "USD"
DEFAULT_NAME = "Exchange Rate Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUOTE): cv.string,
        vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


@dataclass
class DomainData:
    """Data structure to hold data for this domain."""

    coordinators: dict[tuple[str, str], OpenexchangeratesCoordinator] = field(
        default_factory=dict, init=False
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Open Exchange Rates sensor."""
    name: str = config[CONF_NAME]
    api_key: str = config[CONF_API_KEY]
    base: str = config[CONF_BASE]
    quote: str = config[CONF_QUOTE]

    integration_data: DomainData = hass.data.setdefault(DOMAIN, DomainData())
    coordinators = integration_data.coordinators

    if (api_key, base) not in coordinators:
        # Create one coordinator per base currency per API key.
        update_interval = BASE_UPDATE_INTERVAL * (
            len(
                {
                    coordinator_base
                    for coordinator_api_key, coordinator_base in coordinators
                    if coordinator_api_key == api_key
                }
            )
            + 1
        )
        coordinator = coordinators[api_key, base] = OpenexchangeratesCoordinator(
            hass,
            async_get_clientsession(hass),
            api_key,
            base,
            update_interval,
        )

        LOGGER.debug(
            "Coordinator update interval set to: %s", coordinator.update_interval
        )

        # Set new interval on all coordinators for this API key.
        for (
            coordinator_api_key,
            _,
        ), coordinator in coordinators.items():
            if coordinator_api_key == api_key:
                coordinator.update_interval = update_interval

    coordinator = coordinators[api_key, base]
    async with coordinator.setup_lock:
        # We need to make sure that the coordinator data is ready.
        if not coordinator.data:
            await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise PlatformNotReady

    async_add_entities([OpenexchangeratesSensor(coordinator, name, quote)])


class OpenexchangeratesSensor(
    CoordinatorEntity[OpenexchangeratesCoordinator], SensorEntity
):
    """Representation of an Open Exchange Rates sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: OpenexchangeratesCoordinator, name: str, quote: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._quote = quote
        self._attr_native_unit_of_measurement = quote

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(self.coordinator.data.rates[self._quote], 4)

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        """Return other attributes of the sensor."""
        return self.coordinator.data.rates
