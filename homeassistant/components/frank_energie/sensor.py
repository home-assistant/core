"""Frank Energie current electricity and gas price information service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from python_frank_energie.models import Invoices, MarketPrices, MonthSummary

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_TIME,
    CONF_COORDINATOR,
    DATA_MONTH_SUMMARY,
    DOMAIN,
    SERVICE_NAME_COSTS,
    SERVICE_NAME_PRICES,
)
from .coordinator import FrankEnergieCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class FrankEnergieEntityDescriptionMixin:
    """Mixin values for HomeWizard entities."""

    value_fn: Callable[[Invoices | MarketPrices | MonthSummary], StateType]


@dataclass
class FrankEnergieEntityDescription(
    SensorEntityDescription, FrankEnergieEntityDescriptionMixin
):
    """Describes Frank Energie sensor entity."""

    authenticated: bool = False
    service_name: str | None = SERVICE_NAME_PRICES
    attr_fn: Callable[
        [Invoices | MarketPrices | MonthSummary], dict[str, StateType | list]
    ] = lambda _: {}


SENSOR_TYPES: tuple[FrankEnergieEntityDescription, ...] = (
    FrankEnergieEntityDescription(
        key="electricity_markup",
        translation_key="electricity_markup",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.total,
        attr_fn=lambda data: {"prices": data.electricity.asdict("total")},
    ),
    FrankEnergieEntityDescription(
        key="electricity_market",
        translation_key="electricity_market",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.market_price,
        attr_fn=lambda data: {"prices": data.electricity.asdict("market_price")},
    ),
    FrankEnergieEntityDescription(
        key="electricity_tax",
        translation_key="electricity_tax",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.market_price_with_tax,
        attr_fn=lambda data: {
            "prices": data.electricity.asdict("market_price_with_tax")
        },
    ),
    FrankEnergieEntityDescription(
        key="electricity_tax_vat",
        translation_key="electricity_tax_vat",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.market_price_tax,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="electricity_sourcing",
        translation_key="electricity_sourcing",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.sourcing_markup_price,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="electricity_tax_only",
        translation_key="electricity_tax_only",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.energy_tax_price,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="electricity_billed",
        translation_key="electricity_billed",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.current_hour.sourcing_markup_price
        + data.electricity.current_hour.market_price_with_tax,
    ),
    FrankEnergieEntityDescription(
        key="gas_markup",
        translation_key="gas_markup",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.total,
        attr_fn=lambda data: {"prices": data.gas.asdict("total")},
    ),
    FrankEnergieEntityDescription(
        key="gas_market",
        translation_key="gas_market",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.market_price,
        attr_fn=lambda data: {"prices": data.gas.asdict("market_price")},
    ),
    FrankEnergieEntityDescription(
        key="gas_tax",
        translation_key="gas_tax",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.market_price_with_tax,
        attr_fn=lambda data: {"prices": data.gas.asdict("market_price_with_tax")},
    ),
    FrankEnergieEntityDescription(
        key="gas_tax_vat",
        translation_key="gas_tax_vat",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.market_price_tax,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="gas_sourcing",
        translation_key="gas_sourcing",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.sourcing_markup_price,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="gas_tax_only",
        translation_key="gas_tax_only",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.energy_tax_price,
        entity_registry_enabled_default=False,
    ),
    FrankEnergieEntityDescription(
        key="gas_billed",
        translation_key="gas_billed",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.current_hour.sourcing_markup_price
        + data.gas.current_hour.market_price_with_tax,
    ),
    FrankEnergieEntityDescription(
        key="gas_min",
        translation_key="gas_min",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.today_min.total,
        attr_fn=lambda data: {ATTR_TIME: data.gas.today_min.date_from},
    ),
    FrankEnergieEntityDescription(
        key="gas_max",
        translation_key="gas_max",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gas.today_max.total,
        attr_fn=lambda data: {ATTR_TIME: data.gas.today_max.date_from},
    ),
    FrankEnergieEntityDescription(
        key="electricity_min",
        translation_key="electricity_min",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.today_min.total,
        attr_fn=lambda data: {ATTR_TIME: data.electricity.today_min.date_from},
    ),
    FrankEnergieEntityDescription(
        key="electricity_max",
        translation_key="electricity_max",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.today_max.total,
        attr_fn=lambda data: {ATTR_TIME: data.electricity.today_max.date_from},
    ),
    FrankEnergieEntityDescription(
        key="electricity_avg",
        translation_key="electricity_avg",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.electricity.today_avg,
    ),
    FrankEnergieEntityDescription(
        key="actual_costs_until_last_meter_reading_date",
        translation_key="actual_costs_until_last_meter_reading_date",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data[
            DATA_MONTH_SUMMARY
        ].actualCostsUntilLastMeterReadingDate,
        attr_fn=lambda data: {"Last update": data.month_summary.lastMeterReadingDate},
    ),
    FrankEnergieEntityDescription(
        key="expected_costs_until_last_meter_reading_date",
        translation_key="expected_costs_until_last_meter_reading_date",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data[
            DATA_MONTH_SUMMARY
        ].expectedCostsUntilLastMeterReadingDate,
        attr_fn=lambda data: {"Last update": data.month_summary.lastMeterReadingDate},
    ),
    FrankEnergieEntityDescription(
        key="expected_costs_this_month",
        translation_key="expected_costs_this_month",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data.month_summary.expectedCosts,
    ),
    FrankEnergieEntityDescription(
        key="invoice_previous_period",
        translation_key="invoice_previous_period",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data.invoices.previousPeriodInvoice.TotalAmount
        if data.invoices.previousPeriodInvoice
        else None,
        attr_fn=lambda data: {
            "Start date": data.invoices.previousPeriodInvoice.StartDate,
            "Description": data.invoices.previousPeriodInvoice.PeriodDescription,
        },
    ),
    FrankEnergieEntityDescription(
        key="invoice_current_period",
        translation_key="invoice_current_period",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data.invoices.currentPeriodInvoice.TotalAmount
        if data.invoices.currentPeriodInvoice
        else None,
        attr_fn=lambda data: {
            "Start date": data.invoices.currentPeriodInvoice.StartDate,
            "Description": data.invoices.currentPeriodInvoice.PeriodDescription,
        },
    ),
    FrankEnergieEntityDescription(
        key="invoice_upcoming_period",
        translation_key="invoice_upcoming_period",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        authenticated=True,
        service_name=SERVICE_NAME_COSTS,
        value_fn=lambda data: data.invoices.upcomingPeriodInvoice.TotalAmount
        if data.invoices.upcomingPeriodInvoice
        else None,
        attr_fn=lambda data: {
            "Start date": data.invoices.upcomingPeriodInvoice.StartDate,
            "Description": data.invoices.upcomingPeriodInvoice.PeriodDescription,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Frank Energie sensor entries."""
    frank_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    # Add an entity for each sensor type, when authenticated is True,
    # only add the entity if the user is authenticated
    async_add_entities(
        [
            FrankEnergieSensor(frank_coordinator, description, config_entry)
            for description in SENSOR_TYPES
            if not description.authenticated or frank_coordinator.api.is_authenticated
        ],
        True,
    )


class FrankEnergieSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Frank Energie sensor."""

    _attr_has_entity_name = True

    _attr_attribution = "Data provided by Frank Energie"
    _attr_icon = "mdi:currency-eur"

    _unsub_update: Callable[[], None] | None = None

    def __init__(
        self,
        coordinator: FrankEnergieCoordinator,
        description: FrankEnergieEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description: FrankEnergieEntityDescription = description
        self._attr_unique_id = f"{entry.unique_id}.{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}-{description.service_name}")},
            name=f"Frank Energie - {description.service_name}",
            manufacturer="Frank Energie",
            entry_type=DeviceEntryType.SERVICE,
        )

        self._update_job = HassJob(self._handle_scheduled_update)

        super().__init__(coordinator)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        try:
            self._attr_native_value = self.entity_description.value_fn(
                self.coordinator.data
            )
        except (TypeError, IndexError, ValueError):
            # No data available
            self._attr_native_value = None

        # Cancel the currently scheduled event if there is any
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

        # Schedule the next update at exactly the next whole hour sharp
        self._unsub_update = event.async_track_point_in_utc_time(
            self.hass,
            self._update_job,
            dt_util.utcnow().replace(minute=0, second=0) + timedelta(hours=1),
        )

    async def _handle_scheduled_update(self, _):
        """Handle a scheduled update."""
        # Only handle the scheduled update for entities which have a reference to hass,
        # which disabled sensors don't have.
        if self.hass is None:
            return

        self.async_schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.entity_description.attr_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.native_value is not None
