"""Constants for the WiZ Platform integration."""
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

DOMAIN = "wiz"
DEFAULT_NAME = "WiZ"

WIZ_EXCEPTIONS = (
    OSError,
    WizLightTimeOutError,
    TimeoutError,
    WizLightConnectionError,
    ConnectionRefusedError,
)
