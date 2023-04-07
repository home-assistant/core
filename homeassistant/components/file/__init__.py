"""The file component."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType

DOMAIN = "file"

WRITE_PARAM_FILENAME = "filename"
WRITE_PARAM_CONTENT = "content"
WRITE_PARAM_MODE = "mode"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file write service."""

    @callback
    def write(call: ServiceCall) -> None:
        """Write a file."""
        filename = call.data[WRITE_PARAM_FILENAME]
        content = call.data[WRITE_PARAM_CONTENT]
        mode = call.data.get(WRITE_PARAM_MODE, "w")

        filepath = hass.config.path(filename)

        with open(filepath, mode, encoding="utf8") as file:
            file.write(content)

    hass.services.async_register(DOMAIN, "write", write)

    return True
