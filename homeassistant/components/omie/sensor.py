"""Sensor for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from .const import CET, DOMAIN
from .coordinator import OMIECoordinator
from .util import _pick_series_cet

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

_ATTRIBUTION = "Data provided by OMIE.es"


@dataclass(frozen=True)
class OMIEPriceEntityDescription(SensorEntityDescription):
    """Describes OMIE price entities."""

    def __init__(self, key: str) -> None:
        """Construct an OMIEPriceEntityDescription that reports prices in €/kWh."""
        super().__init__(
            key=key,
            has_entity_name=True,
            translation_key=key,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
            icon="mdi:currency-eur",
            suggested_display_precision=4,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OMIE from its config entry."""
    coordinator: OMIECoordinator = entry.runtime_data

    device_info = DeviceInfo(
        configuration_url="https://www.omie.es/en/market-results",
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="OMI Group",
        name="OMIE",
        model="MIBEL market results",
    )

    def hass_tzinfo() -> ZoneInfo:
        return ZoneInfo(hass.config.time_zone)

    class OMIEPriceEntity(SensorEntity):
        def __init__(self, key: str) -> None:
            """Initialize the sensor."""
            self.entity_description = OMIEPriceEntityDescription(key)
            self._attr_device_info = device_info
            self._attr_unique_id = slugify(f"{key}")
            self._attr_should_poll = False
            self._attr_attribution = _ATTRIBUTION

        async def async_added_to_hass(self) -> None:
            """Register callbacks."""

            @callback
            def update() -> None:
                """Update this sensor's state from the coordinator results."""
                value = self._get_current_hour_value()
                self._attr_available = value is not None
                self._attr_native_value = value
                self.async_schedule_update_ha_state()

            self.async_on_remove(coordinator.async_add_listener(update))

        def _get_current_hour_value(self) -> float | None:
            """Get current hour's price value from coordinator data."""
            # to work out the start of the current hour we truncate from minutes downwards
            # rather than create a new datetime to ensure correctness across DST boundaries
            hass_now = utcnow().astimezone(hass_tzinfo())
            hour_start = hass_now.replace(minute=0, second=0, microsecond=0)
            hour_start_cet = hour_start.astimezone(CET)

            series_name = self.entity_description.key
            day_hours_raw = coordinator.data.get(hour_start_cet.date())
            day_hours_cet = _pick_series_cet(day_hours_raw, series_name)

            # Convert to €/kWh
            value_mwh = day_hours_cet.get(hour_start_cet)
            return value_mwh / 1000 if value_mwh is not None else None

    sensors = [
        OMIEPriceEntity("spot_price_pt"),
        OMIEPriceEntity("spot_price_es"),
    ]

    async_add_entities(sensors, update_before_add=True)
    await coordinator.async_config_entry_first_refresh()
