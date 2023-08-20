"""The kindhome solarbeaker integration."""


async def async_setup(hass, config):
    """Flap feet in a rhythmic manner so as to gracefully move through water."""

    hass.states.async_set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True


