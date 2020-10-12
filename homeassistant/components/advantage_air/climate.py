"""Climate platform for Advantage Air integration."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN,
)

ADVANTAGE_AIR_HVAC_MODES = {
    "heat": HVAC_MODE_HEAT,
    "cool": HVAC_MODE_COOL,
    "vent": HVAC_MODE_FAN_ONLY,
    "dry": HVAC_MODE_DRY,
}
HASS_HVAC_MODES = {v: k for k, v in ADVANTAGE_AIR_HVAC_MODES.items()}

ADVANTAGE_AIR_FAN_MODES = {
    "auto": FAN_AUTO,
    "low": FAN_LOW,
    "medium": FAN_MEDIUM,
    "high": FAN_HIGH,
}
HASS_FAN_MODES = {v: k for k, v in ADVANTAGE_AIR_FAN_MODES.items()}
FAN_SPEEDS = {FAN_LOW: 30, FAN_MEDIUM: 60, FAN_HIGH: 100}

AC_HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
]
ZONE_HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_FAN_ONLY]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir climate platform."""

    instance = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirAC(instance, ac_key))
        for zone_key in instance["coordinator"].data["aircons"][ac_key]["zones"]:
            # Only add zone climate control when zone is in temperature control
            if (
                instance["coordinator"].data["aircons"][ac_key]["zones"][zone_key][
                    "type"
                ]
                != 0
            ):
                entities.append(AdvantageAirZone(instance, ac_key, zone_key))
    async_add_entities(entities)


class AdvantageAirClimateEntity(CoordinatorEntity, ClimateEntity):
    """AdvantageAir Climate class."""

    def __init__(self, instance):
        """Initialize the base Advantage Air climate entity."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self):
        """Return the supported temperature step."""
        return PRECISION_WHOLE

    @property
    def max_temp(self):
        """Return the maximum supported temperature."""
        return 32

    @property
    def min_temp(self):
        """Return the minimum supported temperature."""
        return 16

    @property
    def device_info(self):
        """Return parent device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["system"]["rid"])},
            "name": self.coordinator.data["system"]["name"],
            "manufacturer": "Advantage Air",
            "model": self.coordinator.data["system"]["sysType"],
            "sw_version": self.coordinator.data["system"]["myAppRev"],
        }


class AdvantageAirAC(AdvantageAirClimateEntity):
    """AdvantageAir AC unit."""

    def __init__(self, instance, ac_key):
        """Initialize the Advantage Air AC climate entity."""
        super().__init__(instance)
        self.ac_key = ac_key

    @property
    def name(self):
        """Return the name."""
        return self.coordinator.data["aircons"][self.ac_key]["info"]["name"]

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}'

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self.coordinator.data["aircons"][self.ac_key]["info"]["setTemp"]

    @property
    def hvac_mode(self):
        """Return the current HVAC modes."""
        if (
            self.coordinator.data["aircons"][self.ac_key]["info"]["state"]
            == ADVANTAGE_AIR_STATE_ON
        ):
            return ADVANTAGE_AIR_HVAC_MODES.get(
                self.coordinator.data["aircons"][self.ac_key]["info"]["mode"]
            )
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the supported HVAC modes."""
        return AC_HVAC_MODES

    @property
    def fan_mode(self):
        """Return the current fan modes."""
        return ADVANTAGE_AIR_FAN_MODES.get(
            self.coordinator.data["aircons"][self.ac_key]["info"]["fan"], FAN_OFF
        )

    @property
    def fan_modes(self):
        """Return the supported fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    @property
    def device_state_attributes(self):
        """Return additional attributes about AC unit."""
        return self.coordinator.data["aircons"][self.ac_key]["info"]

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_change(
                {self.ac_key: {"info": {"state": ADVANTAGE_AIR_STATE_OFF}}}
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "info": {
                            "state": ADVANTAGE_AIR_STATE_ON,
                            "mode": HASS_HVAC_MODES.get(hvac_mode),
                        }
                    }
                }
            )

    async def async_set_fan_mode(self, fan_mode):
        """Set the Fan Mode."""
        await self.async_change(
            {self.ac_key: {"info": {"fan": HASS_FAN_MODES.get(fan_mode)}}}
        )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change({self.ac_key: {"info": {"setTemp": temp}}})


class AdvantageAirZone(AdvantageAirClimateEntity):
    """AdvantageAir Zone control."""

    def __init__(self, instance, ac_key, zone_key):
        """Initialize the Advantage Air Zone climate entity."""
        super().__init__(instance)
        self.ac_key = ac_key
        self.zone_key = zone_key

    @property
    def name(self):
        """Return the name."""
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
            "name"
        ]

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}'

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
            "measuredTemp"
        ]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
            "setTemp"
        ]

    @property
    def hvac_mode(self):
        """Return the current HVAC modes."""
        if (
            self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key][
                "state"
            ]
            == ADVANTAGE_AIR_STATE_OPEN
        ):
            return HVAC_MODE_FAN_ONLY
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return supported HVAC modes."""
        return ZONE_HVAC_MODES

    @property
    def device_state_attributes(self):
        """Return additional attributes about Zone."""
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC Mode and State."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_CLOSE}}
                    }
                }
            )
        else:
            await self.async_change(
                {
                    self.ac_key: {
                        "zones": {self.zone_key: {"state": ADVANTAGE_AIR_STATE_OPEN}}
                    }
                }
            )

    async def async_set_temperature(self, **kwargs):
        """Set the Temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_change(
            {self.ac_key: {"zones": {self.zone_key: {"setTemp": temp}}}}
        )
