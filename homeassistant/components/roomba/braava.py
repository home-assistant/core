"""Class for Braava devices."""
import logging

from homeassistant.components.vacuum import SUPPORT_FAN_SPEED

from .irobot_base import SUPPORT_IROBOT, IRobotVacuum

_LOGGER = logging.getLogger(__name__)

ATTR_DETECTED_PAD = "detected_pad"
ATTR_LID_CLOSED = "lid_closed"
ATTR_TANK_PRESENT = "tank_present"
ATTR_TANK_LEVEL = "tank_level"
ATTR_PAD_WETNESS = "spray_amount"

OVERLAP_STANDARD = 67
OVERLAP_DEEP = 85
OVERLAP_EXTENDED = 25
MOP_STANDARD = "Standard"
MOP_DEEP = "Deep"
MOP_EXTENDED = "Extended"
BRAAVA_MOP_BEHAVIORS = [MOP_STANDARD, MOP_DEEP, MOP_EXTENDED]
BRAAVA_SPRAY_AMOUNT = [1, 2, 3]

# Braava Jets can set mopping behavior through fanspeed
SUPPORT_BRAAVA = SUPPORT_IROBOT | SUPPORT_FAN_SPEED


class BraavaJet(IRobotVacuum):
    """Braava Jet."""

    def __init__(self, roomba, blid):
        """Initialize the Roomba handler."""
        super().__init__(roomba, blid)

        # Initialize fan speed list
        speed_list = []
        for behavior in BRAAVA_MOP_BEHAVIORS:
            for spray in BRAAVA_SPRAY_AMOUNT:
                speed_list.append(f"{behavior}-{spray}")
        self._speed_list = speed_list

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_BRAAVA

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        # Mopping behavior and spray amount as fan speed
        rank_overlap = self.vacuum_state.get("rankOverlap", {})
        behavior = None
        if rank_overlap == OVERLAP_STANDARD:
            behavior = MOP_STANDARD
        elif rank_overlap == OVERLAP_DEEP:
            behavior = MOP_DEEP
        elif rank_overlap == OVERLAP_EXTENDED:
            behavior = MOP_EXTENDED
        pad_wetness = self.vacuum_state.get("padWetness", {})
        # "disposable" and "reusable" values are always the same
        pad_wetness_value = pad_wetness.get("disposable")
        return f"{behavior}-{pad_wetness_value}"

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._speed_list

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        try:
            split = fan_speed.split("-", 1)
            behavior = split[0]
            spray = int(split[1])
            if behavior.capitalize() in BRAAVA_MOP_BEHAVIORS:
                behavior = behavior.capitalize()
        except IndexError:
            _LOGGER.error(
                "Fan speed error: expected {behavior}-{spray_amount}, got '%s'",
                fan_speed,
            )
            return
        except ValueError:
            _LOGGER.error("Spray amount error: expected integer, got '%s'", split[1])
            return
        if behavior not in BRAAVA_MOP_BEHAVIORS:
            _LOGGER.error(
                "Mop behavior error: expected one of %s, got '%s'",
                str(BRAAVA_MOP_BEHAVIORS),
                behavior,
            )
            return
        if spray not in BRAAVA_SPRAY_AMOUNT:
            _LOGGER.error(
                "Spray amount error: expected one of %s, got '%d'",
                str(BRAAVA_SPRAY_AMOUNT),
                spray,
            )
            return

        overlap = 0
        if behavior == MOP_STANDARD:
            overlap = OVERLAP_STANDARD
        elif behavior == MOP_DEEP:
            overlap = OVERLAP_DEEP
        else:
            overlap = OVERLAP_EXTENDED
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "rankOverlap", overlap
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference,
            "padWetness",
            {"disposable": spray, "reusable": spray},
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        state_attrs = super().device_state_attributes

        # Get Braava state
        state = self.vacuum_state
        detected_pad = state.get("detectedPad")
        mop_ready = state.get("mopReady", {})
        lid_closed = mop_ready.get("lidClosed")
        tank_present = mop_ready.get("tankPresent")
        tank_level = state.get("tankLvl")
        state_attrs[ATTR_DETECTED_PAD] = detected_pad
        state_attrs[ATTR_LID_CLOSED] = lid_closed
        state_attrs[ATTR_TANK_PRESENT] = tank_present
        state_attrs[ATTR_TANK_LEVEL] = tank_level

        return state_attrs
