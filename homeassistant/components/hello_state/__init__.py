"""Test state."""

from homeassistant.helpers.typing import ConfigType

DOMAIN = "hello_state"


def setup(hass, config: ConfigType) -> bool:
    """Set the initial hello_state.world state."""
    hass.states.set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True
