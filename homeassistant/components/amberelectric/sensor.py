"""Amber Electric Sensor definitions."""

# There are three types of sensor: Current, Forecast and Grid
# Current and forecast will create general, controlled load and feed in as required
# At the moment renewables in the only grid sensor.

from __future__ import annotations

from typing import Any

from amberelectric.models.channel import ChannelType
from amberelectric.models.current_interval import CurrentInterval
from amberelectric.models.forecast_interval import ForecastInterval

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR, PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AmberConfigEntry, AmberUpdateCoordinator
from .formatters import (
    format_cents_to_dollars,
    friendly_channel_type,
    normalize_descriptor,
)

UNIT = f"{CURRENCY_DOLLAR}/{UnitOfEnergy.KILO_WATT_HOUR}"


class AmberSensor(CoordinatorEntity[AmberUpdateCoordinator], SensorEntity):
    """Amber Base Sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AmberUpdateCoordinator,
        description: SensorEntityDescription,
        channel_type: str,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self.site_id = coordinator.site_id
        self.entity_description = description
        self.channel_type = channel_type

        self._attr_unique_id = (
            f"{self.site_id}-{self.entity_description.key}-{self.channel_type}"
        )


class AmberPriceSensor(AmberSensor):
    """Amber Price Sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the current price in $/kWh."""
        interval = self.coordinator.data[self.entity_description.key][self.channel_type]

        if interval.channel_type == ChannelType.FEEDIN:
            return format_cents_to_dollars(interval.per_kwh) * -1
        return format_cents_to_dollars(interval.per_kwh)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional pieces of information about the price."""
        interval = self.coordinator.data[self.entity_description.key][self.channel_type]

        data: dict[str, Any] = {}
        if interval is None:
            return data

        data["duration"] = interval.duration
        data["date"] = interval.var_date.isoformat()
        data["per_kwh"] = format_cents_to_dollars(interval.per_kwh)
        if interval.channel_type == ChannelType.FEEDIN:
            data["per_kwh"] = data["per_kwh"] * -1
        data["nem_date"] = interval.nem_time.isoformat()
        data["spot_per_kwh"] = format_cents_to_dollars(interval.spot_per_kwh)
        data["start_time"] = interval.start_time.isoformat()
        data["end_time"] = interval.end_time.isoformat()
        data["renewables"] = round(interval.renewables)
        data["estimate"] = interval.estimate
        data["spike_status"] = interval.spike_status.value
        data["channel_type"] = interval.channel_type.value

        if interval.range is not None:
            data["range_min"] = format_cents_to_dollars(interval.range.min)
            data["range_max"] = format_cents_to_dollars(interval.range.max)

        return data


class AmberForecastSensor(AmberSensor):
    """Amber Forecast Sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the first forecast price in $/kWh."""
        intervals = self.coordinator.data[self.entity_description.key].get(
            self.channel_type
        )
        if not intervals:
            return None
        interval = intervals[0]

        if interval.channel_type == ChannelType.FEEDIN:
            return format_cents_to_dollars(interval.per_kwh) * -1
        return format_cents_to_dollars(interval.per_kwh)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional pieces of information about the price."""
        intervals = self.coordinator.data[self.entity_description.key].get(
            self.channel_type
        )

        if not intervals:
            return None

        data = {
            "forecasts": [],
            "channel_type": intervals[0].channel_type.value,
        }

        for interval in intervals:
            datum = {}
            datum["duration"] = interval.duration
            datum["date"] = interval.var_date.isoformat()
            datum["nem_date"] = interval.nem_time.isoformat()
            datum["per_kwh"] = format_cents_to_dollars(interval.per_kwh)
            if interval.channel_type == ChannelType.FEEDIN:
                datum["per_kwh"] = datum["per_kwh"] * -1
            datum["spot_per_kwh"] = format_cents_to_dollars(interval.spot_per_kwh)
            datum["start_time"] = interval.start_time.isoformat()
            datum["end_time"] = interval.end_time.isoformat()
            datum["renewables"] = round(interval.renewables)
            datum["spike_status"] = interval.spike_status.value
            datum["descriptor"] = normalize_descriptor(interval.descriptor)

            if interval.range is not None:
                datum["range_min"] = format_cents_to_dollars(interval.range.min)
                datum["range_max"] = format_cents_to_dollars(interval.range.max)

            data["forecasts"].append(datum)

        return data

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        automations = automations_with_entity(self.hass, self.entity_id)
        scripts = scripts_with_entity(self.hass, self.entity_id)
        items = automations + scripts
        if not items:
            return

        entity_reg: er.EntityRegistry = er.async_get(self.hass)
        entity_automations = [
            automation_entity
            for automation_id in automations
            if (automation_entity := entity_reg.async_get(automation_id))
        ]
        entity_scripts = [
            script_entity
            for script_id in scripts
            if (script_entity := entity_reg.async_get(script_id))
        ]

        items_list = [
            f"- [{item.original_name}](/config/automation/edit/{item.unique_id})"
            for item in entity_automations
        ] + [
            f"- [{item.original_name}](/config/script/edit/{item.unique_id})"
            for item in entity_scripts
        ]

        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_binary_valve_{self.entity_id}",
            breaks_in_ha_version="2025.11.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_forecast_sensor",
            translation_placeholders={
                "entity": self.entity_id,
                "items": "\n".join(items_list),
            },
        )


class AmberPriceDescriptorSensor(AmberSensor):
    """Amber Price Descriptor Sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the current price descriptor."""
        return self.coordinator.data[self.entity_description.key][self.channel_type]  # type: ignore[no-any-return]


class AmberGridSensor(CoordinatorEntity[AmberUpdateCoordinator], SensorEntity):
    """Sensor to show single grid specific values."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AmberUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self.site_id = coordinator.site_id
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site_id}-{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the value of the sensor."""
        return self.coordinator.data["grid"][self.entity_description.key]  # type: ignore[no-any-return]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = entry.runtime_data

    current: dict[str, CurrentInterval] = coordinator.data["current"]
    forecasts: dict[str, list[ForecastInterval]] = coordinator.data["forecasts"]

    entities: list[SensorEntity] = []
    for channel_type in current:
        description = SensorEntityDescription(
            key="current",
            name=f"{entry.title} - {friendly_channel_type(channel_type)} Price",
            native_unit_of_measurement=UNIT,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key=channel_type,
        )
        entities.append(AmberPriceSensor(coordinator, description, channel_type))

    for channel_type in current:
        description = SensorEntityDescription(
            key="descriptors",
            name=(
                f"{entry.title} - {friendly_channel_type(channel_type)} Price"
                " Descriptor"
            ),
            translation_key=channel_type,
        )
        entities.append(
            AmberPriceDescriptorSensor(coordinator, description, channel_type)
        )

    for channel_type in forecasts:
        description = SensorEntityDescription(
            key="forecasts",
            name=f"{entry.title} - {friendly_channel_type(channel_type)} Forecast",
            native_unit_of_measurement=UNIT,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key=channel_type,
        )
        entities.append(AmberForecastSensor(coordinator, description, channel_type))

    renewables_description = SensorEntityDescription(
        key="renewables",
        name=f"{entry.title} - Renewables",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="renewables",
    )
    entities.append(AmberGridSensor(coordinator, renewables_description))

    async_add_entities(entities)
