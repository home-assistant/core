"""Constants for the Litter-Robot integration."""
from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot4

DOMAIN = "litterrobot"


class SupportedModels(dict):
    """Supported Litter Robot models."""

    LITTER_ROBOT = LitterRobot
    LITTER_ROBOT_3 = LitterRobot3
    LITTER_ROBOT_4 = LitterRobot4
    FEEDER_ROBOT = FeederRobot
