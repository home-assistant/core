"""Class for Combo devices."""
import logging

from homeassistant.components.vacuum import VacuumEntityFeature

from .irobot_base import SUPPORT_IROBOT, IRobotVacuum

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_DETECTED = "detected_bin"
ATTR_PAD_WETNESS = "spray_amount"
ATTR_NAV_MODE = "navigation_mode"
ATTR_VACC_POWER = "vacuuming_power"

LOW_POWER = "Low"
HIGH_POWER = "High"

NAV_REACTIVE = "Reactive"
NAV_STRAIGHT_LINE = "Straight"

COMBO_LIQUID_ECO = "Eco"
COMBO_LIQUID_STANDARD = "Standard"
COMBO_LIQUID_ULTRA = "Ultra"

# NAV_REACTIVE = 0; NAV_STRAIGHT_LIVE = 1
COMBO_NAVIGATION_MODES = [NAV_REACTIVE, NAV_STRAIGHT_LINE]
COMBO_VACUUM_POWER = [LOW_POWER, HIGH_POWER]
COMBO_LIQUID_AMOUNT = [COMBO_LIQUID_ECO, COMBO_LIQUID_STANDARD, COMBO_LIQUID_ULTRA]

SUPPORT_COMBO = SUPPORT_IROBOT | VacuumEntityFeature.FAN_SPEED


class RoombaCombo(IRobotVacuum):
    """Combo."""

    def __init__(self, roomba, blid):
        """Initialize the Roomba handler."""
        super().__init__(roomba, blid)

        # Initialize fan speed list
        speed_list = []
        for behavior in COMBO_VACUUM_POWER:
            for spray in COMBO_LIQUID_AMOUNT:
                for mode in COMBO_NAVIGATION_MODES:
                    speed_list.append(f"{behavior} - {spray} - {mode}")
        self._speed_list = speed_list

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_COMBO

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        # Mopping behavior and spray amount as fan speed
        vac_high = self.vacuum_state.get("vacHigh")
        behavior = HIGH_POWER
        if vac_high is False:
            behavior = LOW_POWER
        return f"Vacuum mode: {behavior} Power"

    @property
    def get_fan_speed(self):
        """Return the actual fan speed."""
        vac_high = self.vacuum_state.get("vacHigh")
        behavior = HIGH_POWER
        if vac_high is False:
            behavior = LOW_POWER
        return f"{behavior}"

    @property
    def get_liquid_amount(self):
        """Return the liquid amount."""
        pad = self.vacuum_state.get("padWetness", {})
        liquid_amount = pad.get("padPlate")
        behaviour = COMBO_LIQUID_AMOUNT[liquid_amount - 1]
        return f"{behaviour}"

    @property
    def get_nav_mode(self):
        """Return the navigation mode."""
        nav_mode = self.vacuum_state.get("navStrategy")
        behaviour = COMBO_NAVIGATION_MODES[nav_mode]
        return f"{behaviour}"

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._speed_list

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        try:
            split = fan_speed.split(" - ", 2)
            vacuum_power = split[0]
            liquid_amount = split[1]
            mode = split[2]
        except IndexError:
            _LOGGER.error(
                "Fan speed error: expected {behavior} - {spray_amount} {mode}, got '%s'",
                fan_speed,
            )
            return
        if liquid_amount not in COMBO_LIQUID_AMOUNT:
            _LOGGER.error(
                "Liquid behavior error: expected one of %s, got '%s'",
                str(COMBO_LIQUID_AMOUNT),
                liquid_amount,
            )
            return
        if vacuum_power not in COMBO_VACUUM_POWER:
            _LOGGER.error(
                "Vacuum behavior error: expected one of %s, got '%s'",
                str(COMBO_VACUUM_POWER),
                vacuum_power,
            )
            return
        if mode not in COMBO_NAVIGATION_MODES:
            _LOGGER.error(
                "Mode error: expected one of %s, got '%d'",
                str(COMBO_NAVIGATION_MODES),
                mode,
            )
            return

        high_vac = False
        if vacuum_power == HIGH_POWER:
            high_vac = True

        liquid_amount = COMBO_LIQUID_AMOUNT.index(liquid_amount) + 1
        mode = COMBO_NAVIGATION_MODES.index(mode)

        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "vacHigh", str(high_vac)
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference,
            "padWetness",
            {"padPlate": liquid_amount},
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "navStrategy", mode
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        state_attrs = super().extra_state_attributes

        # Get Combo state
        state = self.vacuum_state
        detected_bin = state.get("bin").get("present")
        state_attrs[ATTR_VACC_POWER] = self.get_fan_speed
        state_attrs[ATTR_PAD_WETNESS] = self.get_liquid_amount
        state_attrs[ATTR_NAV_MODE] = self.get_nav_mode
        state_attrs[ATTR_BIN_DETECTED] = detected_bin

        return state_attrs
