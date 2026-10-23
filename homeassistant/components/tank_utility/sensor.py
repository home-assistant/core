"""Support for Tank Utility propane monitor sensors."""

from typing import Any, override

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD, PERCENTAGE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_ATTRS, SENSOR_ROUNDING_PRECISION, SENSOR_TYPE
from .coordinator import TankUtilityConfigEntry, TankUtilityDataUpdateCoordinator

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_EMAIL): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Optional(CONF_DEVICES): probatio.All(
            probatio.EnsureList(), probatio.NonEmpty()
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TankUtilityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tank Utility sensor entities based on a config entry."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        new_devices = set(coordinator.data) - known_devices
        if not new_devices:
            return
        known_devices.update(new_devices)
        async_add_entities(
            TankUtilitySensor(coordinator, device_id) for device_id in new_devices
        )

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Tank Utility platform from YAML (deprecated)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=dict(config),
    )
    if result.get("type") is FlowResultType.ABORT:
        if (reason := result.get("reason")) == "already_in_progress":
            return
        if reason != "already_configured":
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{reason}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
            )
            return

    ir.async_delete_issue(hass, DOMAIN, "deprecated_yaml_import_issue_invalid_auth")
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Tank Utility",
        },
    )


class TankUtilitySensor(
    CoordinatorEntity[TankUtilityDataUpdateCoordinator], SensorEntity
):
    """Representation of a Tank Utility sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TankUtilityDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_tank"
        device_data = coordinator.data.get(device_id, {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_data.get("name") or f"Tank Utility {device_id}",
            manufacturer="Tank Utility",
            model=f"{device_data.get('fuelType', 'Propane').capitalize()} Monitor",
            configuration_url="https://data.tankutility.com",
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_id in self.coordinator.data

    @property
    def device_data(self) -> dict[str, Any]:
        """Return data for this device from the coordinator."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (val := self.device_data.get(SENSOR_TYPE)) is not None:
            return round(val, SENSOR_ROUNDING_PRECISION)
        return None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.device_data
        return {k: v for k, v in data.items() if k in SENSOR_ATTRS}
