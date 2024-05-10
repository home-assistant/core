"""Constants for the zcc integration."""

from typing import List  # noqa: F401, UP035

CONTROLLER = "zimi_controller"
DOMAIN = "zimi"
PLATFORMS = ["cover", "fan", "light", "sensor", "switch"]  # type: List[str]

TIMEOUT = "timeout"
VERBOSITY = "verbosity"
WATCHDOG = "watchdog"
