"""Class for Braava devices."""
import logging

from homeassistant.components.vacuum import SUPPORT_OPTION

from .irobot_base import SUPPORT_IROBOT, IRobotVacuum

_LOGGER = logging.getLogger(__name__)

ATTR_DETECTED_PAD = "detected_pad"
ATTR_LID_CLOSED = "lid_closed"
ATTR_TANK_PRESENT = "tank_present"
ATTR_TANK_LEVEL = "tank_level"
ATTR_PAD_WETNESS = "spray_amount"

OPTION_WET_MOP_BEHAVIOR = "wet_mop_behavior"
OPTION_SPRAY_AMOUNT = "spray_amount"
BRAAVA_OPTIONS = [OPTION_WET_MOP_BEHAVIOR, OPTION_SPRAY_AMOUNT]

OVERLAP_STANDARD = 67
OVERLAP_DEEP = 85
OVERLAP_EXTENDED = 25
MOP_STANDARD = "Standard"
MOP_DEEP = "Deep"
MOP_EXTENDED = "Extended"
BRAAVA_MOP_BEHAVIORS = [MOP_STANDARD, MOP_DEEP, MOP_EXTENDED]
BRAAVA_SPRAY_AMOUNT = ["1", "2", "3"]

# Braava Jets can set mopping behavior through fanspeed
SUPPORT_BRAAVA = SUPPORT_IROBOT | SUPPORT_OPTION


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
    def wet_mop_behavior(self):
        """Return the mop behavior of the vacuum cleaner."""
        rank_overlap = self.vacuum_state.get("rankOverlap", {})
        behavior = None
        if rank_overlap == OVERLAP_STANDARD:
            behavior = MOP_STANDARD
        elif rank_overlap == OVERLAP_DEEP:
            behavior = MOP_DEEP
        elif rank_overlap == OVERLAP_EXTENDED:
            behavior = MOP_EXTENDED
        return behavior

    @property
    def wet_mop_behavior_list(self):
        """Return the available mop behaviors of the vacuum cleaner."""
        return BRAAVA_MOP_BEHAVIORS

    @property
    def spray_amount(self):
        """Return the spray amount of the vacuum cleaner."""
        pad_wetness = self.vacuum_state.get("padWetness", {})
        # "disposable" and "reusable" values are always the same
        pad_wetness_value = pad_wetness.get("disposable")
        return str(pad_wetness_value)

    @property
    def spray_amount_list(self):
        """Return the available spray amount of the vacuum cleaner."""
        return BRAAVA_SPRAY_AMOUNT

    @property
    def option_list(self):
        """Get the list of options of the vacuum cleaner."""
        return BRAAVA_OPTIONS

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

    async def async_set_option(self, option, value):
        """Set option value."""
        if option == OPTION_WET_MOP_BEHAVIOR:
            if value.capitalize() in BRAAVA_MOP_BEHAVIORS:
                value = value.capitalize()
            if value not in BRAAVA_MOP_BEHAVIORS:
                _LOGGER.error(
                    "Mop behavior error: expected one of %s, got '%s'",
                    str(BRAAVA_MOP_BEHAVIORS),
                    value,
                )
                return
            overlap = 0
            if value == MOP_STANDARD:
                overlap = OVERLAP_STANDARD
            elif value == MOP_DEEP:
                overlap = OVERLAP_DEEP
            else:
                overlap = OVERLAP_EXTENDED
            await self.hass.async_add_executor_job(
                self.vacuum.set_preference, "rankOverlap", overlap
            )
        elif option == OPTION_SPRAY_AMOUNT:
            if value not in BRAAVA_SPRAY_AMOUNT:
                _LOGGER.error(
                    "Spray amount error: expected one of %s, got '%s'",
                    BRAAVA_SPRAY_AMOUNT,
                    value,
                )
                return
            spray = int(value)
            await self.hass.async_add_executor_job(
                self.vacuum.set_preference,
                "padWetness",
                {"disposable": spray, "reusable": spray},
            )
        else:
            _LOGGER.error(
                "Option name error: expected %s or %s, got '%s'",
                OPTION_WET_MOP_BEHAVIOR,
                OPTION_SPRAY_AMOUNT,
                option,
            )
