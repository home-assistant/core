"""DVLA binary sensor platform."""

from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator


@dataclass(frozen=True, kw_only=True)
class DVLABinarySensorEntityDescription(BinarySensorEntityDescription):
    """DVLA binary sensor description."""

    on_value: str | bool = True
    off_value: str | bool = False


# Fallback/Overrides for icons and on_values
ENTITY_METADATA = {
    "taxStatus": {
        "icon": "mdi:cash-clock",
        "on_value": "Taxed",
        "off_value": "Not Taxed",
        "title": "Taxed",
    },
    "motStatus": {
        "icon": "mdi:car-wrench",
        "on_value": "Valid",
        "off_value": "Invalid",
        "title": "M.O.T Valid",
    },
    "markedForExport": {"icon": "mdi:shipping-pallet", "title": "Marked for Export"},
    "automatedVehicle": {"icon": "mdi:car-connected"},
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

    sensors = []

    for key, prop in vehicle_properties.items():
        metadata: dict[str, Any] = ENTITY_METADATA.get(key, {})

        # Only create binary sensors for booleans OR if we have explicit metadata (like taxStatus)
        if prop.get("type") != "boolean" and not metadata:
            continue

        # Special case: if it's not a boolean in the schema but we want it as a binary sensor
        # (e.g. taxStatus/motStatus which are strings in schema but binary here)
        # we need to make sure we don't duplicate if the sensor platform also picks it up.
        # Actually, in the current design, taxStatus is both a sensor (string) and binary_sensor (bool).

        on_value: str | bool = True
        off_value: str | bool = False
        if metadata:
            on_value = metadata.get("on_value", True)
            off_value = metadata.get("off_value", False)

        description = DVLABinarySensorEntityDescription(
            key=key,
            name=metadata.get(
                "title", prop.get("title", key.replace("_", " ").title())
            ),
            icon=metadata.get("icon", "mdi:car"),
            on_value=on_value,
            off_value=off_value,
        )

        if key in coordinator.data:
            sensors.append(DVLABinarySensor(coordinator, name, description))

    async_add_entities(sensors, update_before_add=True)


class DVLABinarySensor(CoordinatorEntity[DVLACoordinator], BinarySensorEntity):
    """Define an DVLA sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DVLACoordinator,
        name: str,
        description: DVLABinarySensorEntityDescription,
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
        self._attr_unique_id = f"{name}-{description.key}-binary".lower()
        self.entity_id = f"binary_sensor.{DOMAIN}_{name}_{description.key}".lower()
        self.attrs: dict[str, Any] = {}
        self.entity_description = description
        self._attr_is_on = False
        self.update_from_coordinator()

    def update_from_coordinator(self):
        """Update sensor state and attributes from coordinator data."""
        if not self.coordinator.data:
            return

        value: str | bool | None = self.coordinator.data.get(
            self.entity_description.key
        )
        on_value = self.entity_description.on_value
        off_value = self.entity_description.off_value

        if value is None:
            self._attr_is_on = None
        elif isinstance(on_value, str) and isinstance(value, str):
            if value.casefold() == on_value.casefold():
                self._attr_is_on = True
            elif (
                isinstance(off_value, str) and value.casefold() == off_value.casefold()
            ):
                self._attr_is_on = False
            else:
                self._attr_is_on = False
        else:
            self._attr_is_on = bool(value == on_value)

        for key in self.coordinator.data:
            self.attrs[key] = self.coordinator.data[key]

    @override
    @callback
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
        return bool(self.coordinator.data)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.attrs
