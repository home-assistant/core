"""Support for the EPH Controls Ember themostats."""

from datetime import timedelta
from enum import IntEnum
import logging
from typing import Any, override

import probatio
from pyephember2.pyephember2 import (
    ZoneMode,
    boiler_state,
    zone_current_temperature,
    zone_is_hotwater,
    zone_mode,
    zone_name,
    zone_target_temperature,
)

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import EphEmberConfigEntry
from .const import DOMAIN, signal_zone_update

_LOGGER = logging.getLogger(__name__)

INTEGRATION_TITLE = "EPH Controls"

# Import aborts that mean the YAML couldn't be imported
IMPORT_FAILURES = ("cannot_connect", "invalid_auth", "unknown")

# Return cached results if last scan was less then this time ago
SCAN_INTERVAL = timedelta(seconds=120)

OPERATION_LIST = [HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.OFF]

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
    }
)

EPH_TO_HA_STATE = {
    "AUTO": HVACMode.HEAT_COOL,
    "ON": HVACMode.HEAT,
    "OFF": HVACMode.OFF,
}


class EPHBoilerStates(IntEnum):
    """Boiler states for a zone given by the api."""

    FIXME = 0
    OFF = 1
    ON = 2


HA_STATE_TO_EPH = {value: key for key, value in EPH_TO_HA_STATE.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML configuration into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_USERNAME: config[CONF_USERNAME],
            CONF_PASSWORD: config[CONF_PASSWORD],
        },
    )

    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) in IMPORT_FAILURES
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2027.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EphEmberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a climate entity for each zone."""
    data = entry.runtime_data
    async_add_entities(
        EphEmberThermostat(data.ember, zone, entry.entry_id)
        for home in data.homes
        for zone in home["zones"]
    )


class EphEmberThermostat(ClimateEntity):
    """Representation of a EphEmber thermostat."""

    _attr_hvac_modes = OPERATION_LIST
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, ember, zone, entry_id: str) -> None:
        """Initialize the thermostat."""
        self._ember = ember
        self._entry_id = entry_id
        self._zone_name = zone_name(zone)
        self._zone = zone
        self._attr_unique_id = zone["zoneid"]

        # hot water = true, is immersive device without target temperature control.
        self._hot_water = zone_is_hotwater(zone)

        self._attr_name = self._zone_name

        if self._hot_water:
            self._attr_target_temperature_step = None
        else:
            self._attr_target_temperature_step = 0.5
            self._attr_supported_features = (
                ClimateEntityFeature.TURN_OFF
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TARGET_TEMPERATURE
            )

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return zone_current_temperature(self._zone)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return zone_target_temperature(self._zone)

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if boiler_state(self._zone) == EPHBoilerStates.ON:
            return HVACAction.HEATING

        return HVACAction.IDLE

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        mode = zone_mode(self._zone)
        return self.map_mode_eph_hass(mode)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode."""
        mode = self.map_mode_hass_eph(hvac_mode)
        if mode is not None:
            self._ember.set_zone_mode(self._zone["zoneid"], mode)
        else:
            _LOGGER.error("Invalid operation mode provided %s", hvac_mode)

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self._hot_water:
            return

        if temperature == self.native_target_temperature:
            return

        if temperature > self.max_temp or temperature < self.min_temp:
            return

        self._ember.set_zone_target_temperature(self._zone["zoneid"], temperature)

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        # Hot water temp doesn't support being changed
        if self._hot_water:
            return zone_target_temperature(self._zone)

        return 5.0

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._hot_water:
            return zone_target_temperature(self._zone)

        return 35.0

    @override
    async def async_added_to_hass(self) -> None:
        """Listen for live updates of this zone."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_zone_update(self._entry_id, self._zone["zoneid"]),
                self._async_zone_updated,
            )
        )

    @callback
    def _async_zone_updated(self, zone: dict[str, Any]) -> None:
        """Show a live update from the EPH Ember cloud."""
        self._zone = zone
        self._attr_available = True
        self.async_write_ha_state()

    def update(self) -> None:
        """Get the latest data."""
        try:
            self._ember.get_zones()
            self._zone = self._ember.get_zone(self._zone["zoneid"])
        except RuntimeError as err:
            if self._attr_available:
                _LOGGER.warning("Unable to update %s: %s", self._zone_name, err)
            self._attr_available = False
            return

        if not self._attr_available:
            _LOGGER.info("%s is available again", self._zone_name)
        self._attr_available = True

    @staticmethod
    def map_mode_hass_eph(operation_mode):
        """Map from Home Assistant mode to eph mode."""
        return getattr(ZoneMode, HA_STATE_TO_EPH.get(operation_mode), None)

    @staticmethod
    def map_mode_eph_hass(operation_mode):
        """Map from eph mode to Home Assistant mode."""
        if operation_mode is None:
            return HVACMode.HEAT_COOL
        return EPH_TO_HA_STATE.get(operation_mode.name, HVACMode.HEAT_COOL)
