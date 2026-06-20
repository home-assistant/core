"""Support for the Forecast.Solar sensor service."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from forecast_solar.models import Estimate

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ForecastSolarConfigEntry
from .const import DOMAIN
from .coordinator import ForecastSolarDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class ForecastSolarSensorEntityDescription(SensorEntityDescription):
    """Describes a Forecast.Solar Sensor."""

    state: Callable[[Estimate], Any] | None = None
    attributes: Callable[[Estimate], dict[str, Any]] | None = None


def _series_for_date(
    series: dict[datetime, int], target_date: date, tz: ZoneInfo
) -> dict[str, int]:
    """Return ISO-keyed entries from a Forecast.Solar series for one date.

    Series keys are UTC-aware datetimes (the Forecast.Solar library v4+
    requests data using UTC). ``target_date`` is a calendar date in the
    API/site timezone, so each key is converted to that timezone both
    for the date comparison and for the emitted ISO string — downstream
    consumers see local-zoned timestamps (e.g. ``+10:00``) rather than
    ``+00:00``.
    """
    return {
        local_ts.isoformat(): val
        for ts, val in series.items()
        for local_ts in (ts.astimezone(tz),)
        if local_ts.date() == target_date
    }


def _series_in_tz(series: dict[datetime, int], tz: ZoneInfo) -> dict[str, int]:
    """Return all ISO-keyed entries from a series, converted to ``tz``.

    Keys are emitted with the site/API timezone offset (rather than
    ``+00:00``) so downstream consumers parsing the attribute map
    directly see local-zoned timestamps. No date filter is applied:
    the full forecast horizon returned by the Forecast.Solar library
    is preserved.
    """
    return {ts.astimezone(tz).isoformat(): val for ts, val in series.items()}


def _today_attributes(estimate: Estimate) -> dict[str, Any]:
    """Return the full power and energy forecast curves as state attributes.

    Each attribute is a mapping of ISO 8601 timestamp -> value, where
    ``watts`` is the estimated power in W at the timestamp and
    ``wh_period`` is the energy in Wh for the interval starting at that
    timestamp. ISO keys carry the site/API timezone offset.

    The full forecast window returned by the Forecast.Solar library
    (typically ~32 hours for free accounts, up to 3-6 days for paid
    accounts) is emitted so downstream optimizers and forecasters can
    consume more than a single day of lookahead. Recorder write cost
    is handled separately via ``_unrecorded_attributes`` on the entity
    class, so the live state payload is the only remaining concern;
    even the paid-tier window at 15-minute resolution stays well under
    typical attribute size limits.

    The function name is preserved for backwards compatibility; despite
    the name, the emitted series is the full horizon rather than only
    today.
    """
    tz = ZoneInfo(estimate.api_timezone)
    return {
        "watts": _series_in_tz(estimate.watts, tz),
        "wh_period": _series_in_tz(estimate.wh_period, tz),
    }


SENSORS: tuple[ForecastSolarSensorEntityDescription, ...] = (
    ForecastSolarSensorEntityDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        state=lambda estimate: estimate.energy_production_today,
        attributes=_today_attributes,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_production_today_remaining",
        translation_key="energy_production_today_remaining",
        state=lambda estimate: estimate.energy_production_today_remaining,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_production_tomorrow",
        translation_key="energy_production_tomorrow",
        state=lambda estimate: estimate.energy_production_tomorrow,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_highest_peak_time_today",
        translation_key="power_highest_peak_time_today",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_highest_peak_time_tomorrow",
        translation_key="power_highest_peak_time_tomorrow",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_now",
        translation_key="power_production_now",
        device_class=SensorDeviceClass.POWER,
        state=lambda estimate: estimate.power_production_now,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_hour",
        translation_key="power_production_next_hour",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=1)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_12hours",
        translation_key="power_production_next_12hours",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=12)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="power_production_next_24hours",
        translation_key="power_production_next_24hours",
        state=lambda estimate: estimate.power_production_at_time(
            estimate.now() + timedelta(hours=24)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_current_hour",
        translation_key="energy_current_hour",
        state=lambda estimate: estimate.energy_current_hour,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ForecastSolarSensorEntityDescription(
        key="energy_next_hour",
        translation_key="energy_next_hour",
        state=lambda estimate: estimate.sum_energy_production(1),
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecastSolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = entry.runtime_data

    async_add_entities(
        ForecastSolarSensorEntity(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in SENSORS
    )


class ForecastSolarSensorEntity(
    CoordinatorEntity[ForecastSolarDataUpdateCoordinator], SensorEntity
):
    """Defines a Forecast.Solar sensor."""

    entity_description: ForecastSolarSensorEntityDescription
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"watts", "wh_period"})

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ForecastSolarDataUpdateCoordinator,
        entity_description: ForecastSolarSensorEntityDescription,
    ) -> None:
        """Initialize Forecast.Solar sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self.entity_id = f"{SENSOR_DOMAIN}.{entity_description.key}"
        self._attr_unique_id = f"{entry_id}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Forecast.Solar",
            model=coordinator.data.account_type.value,
            name="Solar production forecast",
            configuration_url="https://forecast.solar",
        )

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        if self.entity_description.state is None:
            state: StateType | datetime = getattr(
                self.coordinator.data, self.entity_description.key
            )
        else:
            state = self.entity_description.state(self.coordinator.data)

        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return any extra state attributes for the sensor."""
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
