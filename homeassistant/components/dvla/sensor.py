"""DVLA sensor platform."""

from contextlib import suppress
from datetime import date
from typing import Any, cast, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator

# Fallback/Overrides for icons and units
ENTITY_METADATA: dict[str, dict[str, Any]] = {
    "registrationNumber": {"icon": "mdi:ocr", "title": "Registration Number"},
    "taxStatus": {"icon": "mdi:cash-clock", "title": "Tax Status"},
    "taxDueDate": {
        "icon": "mdi:calendar-clock",
        "device_class": SensorDeviceClass.DATE,
        "title": "Tax Due Date",
    },
    "artEndDate": {
        "icon": "mdi:calendar-end",
        "device_class": SensorDeviceClass.DATE,
        "title": "Additional Rate of Tax End Date",
    },
    "motStatus": {"icon": "mdi:car-wrench"},
    "make": {"icon": "mdi:car"},
    "yearOfManufacture": {"icon": "mdi:calendar-month"},
    "engineCapacity": {
        "icon": "mdi:engine",
        "native_unit_of_measurement": "cc",
        "title": "Engine Capacity",
    },
    "co2Emissions": {
        "icon": "mdi:molecule-co2",
        "native_unit_of_measurement": "g/km",
        "title": "CO2 Emissions",
    },
    "fuelType": {"icon": "mdi:gas-station", "title": "Fuel Type"},
    "colour": {"icon": "mdi:spray"},
    "typeApproval": {"icon": "mdi:car"},
    "revenueWeight": {
        "icon": "mdi:weight-kilogram",
        "native_unit_of_measurement": UnitOfMass.KILOGRAMS,
    },
    "dateOfLastV5CIssued": {
        "icon": "mdi:calendar",
        "device_class": SensorDeviceClass.DATE,
    },
    "motExpiryDate": {
        "icon": "mdi:calendar-check",
        "device_class": SensorDeviceClass.DATE,
    },
    "wheelplan": {"icon": "mdi:tire"},
    "monthOfFirstRegistration": {"icon": "mdi:calendar-month", "device_class": None},
    "monthOfFirstDvlaRegistration": {
        "icon": "mdi:calendar-month-outline",
        "device_class": None,
    },
    "realDrivingEmissions": {
        "icon": "mdi:gas-station-outline",
        "title": "Real Driving Emissions",
    },
    "euroStatus": {"icon": "mdi:currency-eur", "title": "Euro Status"},
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    config = entry.runtime_data
    schema = config.get("schema", {})
    vehicle_properties = cast(
        dict[str, dict[str, Any]],
        schema.get("components", {})
        .get("schemas", {})
        .get("Vehicle", {})
        .get("properties", {}),
    )

    session = async_get_clientsession(hass)
    coordinator = DVLACoordinator(
        hass,
        entry,
        session,
        entry.data[CONF_REG_NUMBER],
    )

    await coordinator.async_refresh()

    name = entry.data[CONF_REG_NUMBER]

    sensors: list[DVLASensor] = []

    for key, prop in vehicle_properties.items():
        if prop.get("type") == "boolean":
            continue

        # Skip keys that are handled by binary sensors or specifically excluded
        # (Though most strings/integers go here)

        metadata = ENTITY_METADATA.get(key, {})

        # Use metadata device_class if it exists (even if it is None)
        if "device_class" in metadata:
            device_class = metadata["device_class"]
        elif prop.get("format") == "date":
            device_class = SensorDeviceClass.DATE
        else:
            device_class = None

        unit = metadata.get("native_unit_of_measurement")
        # Try to extract unit from description if not in metadata
        description_text = prop.get("description", "")
        if not unit:
            if "cubic centimetres" in description_text:
                unit = "cc"
            elif "grams per kilometre" in description_text:
                unit = "g/km"
            elif "kilograms" in description_text:
                unit = UnitOfMass.KILOGRAMS

        description = SensorEntityDescription(
            key=key,
            name=metadata.get("title", prop.get("description", "")),
            icon=metadata.get("icon", "mdi:car"),
            device_class=device_class,
            native_unit_of_measurement=unit,
        )

        if key in coordinator.data or key == "motExpiryDate":
            sensors.append(DVLASensor(coordinator, name, description))
    async_add_entities(sensors, update_before_add=True)


class DVLASensor(CoordinatorEntity[DVLACoordinator], SensorEntity):
    """Define an DVLA sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DVLACoordinator,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer=DOMAIN.upper(),
            model=coordinator.data.get("make"),
            name=name.upper(),
            configuration_url="https://github.com/jampez77/DVLA-Vehicle-Checker/",
        )
        self._attr_unique_id = f"{name}-{description.key}".lower()
        self.entity_id = f"sensor.{DOMAIN}_{name}_{description.key}".lower()
        self.attrs: dict[str, Any] = {}
        self.entity_description = description
        self._state: str | date | None = None
        self.update_from_coordinator()

    def update_from_coordinator(self) -> None:
        """Update sensor state and attributes from coordinator data."""
        self._state = self.coordinator.data.get(self.entity_description.key)

        if self.entity_description.key == "motExpiryDate" and not self._state:
            reg_month_str = self.coordinator.data.get("monthOfFirstRegistration")
            if reg_month_str:
                with suppress(ValueError):
                    year_str, month_str = reg_month_str.split("-")
                    calculated_date = date(int(year_str) + 3, int(month_str), 1)
                    self._state = calculated_date.isoformat()

        if (
            self._state
            and self.entity_description.device_class == SensorDeviceClass.DATE
        ):
            try:
                self._state = date.fromisoformat(str(self._state))
            except ValueError:
                self._state = None

        if self._state is not None:
            self.attrs.update(self.coordinator.data)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_coordinator()
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Handle adding to Home Assistant."""
        await super().async_added_to_hass()
        await self.async_update()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        # Ensure entity is available even if specific key is missing but we have coordinator data
        return bool(self.coordinator.data)

    @property
    @override
    def native_value(self) -> str | date | None:
        """Native value."""
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.attrs
