"""Class for Roomba devices."""
import logging

from homeassistant.components.vacuum import VacuumEntityFeature

from .irobot_base import SUPPORT_IROBOT, IRobotVacuum

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_FULL = "bin_full"
ATTR_BIN_PRESENT = "bin_present"

FAN_SPEED_AUTOMATIC = "Automatic"
FAN_SPEED_ECO = "Eco"
FAN_SPEED_PERFORMANCE = "Performance"
FAN_SPEEDS = [FAN_SPEED_AUTOMATIC, FAN_SPEED_ECO, FAN_SPEED_PERFORMANCE]

# Only Roombas with CarpetBost can set their fanspeed
SUPPORT_ROOMBA_CARPET_BOOST = SUPPORT_IROBOT | VacuumEntityFeature.FAN_SPEED


class RoombaVacuum(IRobotVacuum):
    """Basic Roomba robot (without carpet boost)."""

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        state_attrs = super().extra_state_attributes

        # Get bin state
        bin_raw_state = self.vacuum_state.get("bin", {})
        bin_state = {}
        if bin_raw_state.get("present") is not None:
            bin_state[ATTR_BIN_PRESENT] = bin_raw_state.get("present")
        if bin_raw_state.get("full") is not None:
            bin_state[ATTR_BIN_FULL] = bin_raw_state.get("full")
        state_attrs.update(bin_state)

        return state_attrs


class RoombaVacuumCarpetBoost(RoombaVacuum):
    """Roomba robot with carpet boost."""

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROOMBA_CARPET_BOOST

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        fan_speed = None
        carpet_boost = self.vacuum_state.get("carpetBoost")
        high_perf = self.vacuum_state.get("vacHigh")
        if carpet_boost is not None and high_perf is not None:
            if carpet_boost:
                fan_speed = FAN_SPEED_AUTOMATIC
            elif high_perf:
                fan_speed = FAN_SPEED_PERFORMANCE
            else:  # carpet_boost and high_perf are False
                fan_speed = FAN_SPEED_ECO
        return fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return FAN_SPEEDS

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = fan_speed.capitalize()
        _LOGGER.debug("Set fan speed to: %s", fan_speed)
        high_perf = None
        carpet_boost = None
        if fan_speed == FAN_SPEED_AUTOMATIC:
            high_perf = False
            carpet_boost = True
        elif fan_speed == FAN_SPEED_ECO:
            high_perf = False
            carpet_boost = False
        elif fan_speed == FAN_SPEED_PERFORMANCE:
            high_perf = True
            carpet_boost = False
        else:
            _LOGGER.error("No such fan speed available: %s", fan_speed)
            return
        # The set_preference method does only accept string values
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "carpetBoost", str(carpet_boost)
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "vacHigh", str(high_perf)
        )
