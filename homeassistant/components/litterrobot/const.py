"""Constants for the Litter-Robot integration."""
from typing import Union

from pylitterbot import FeederRobot, LitterRobot

DOMAIN = "litterrobot"
RobotTypes = Union[FeederRobot, LitterRobot]
