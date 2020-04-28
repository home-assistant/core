"""Support for showing device locations."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

CONF_REQUIRE_ADMIN = "require_admin"

DOMAIN = "map"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Register the built-in map panel."""
    hass.components.frontend.async_register_built_in_panel(
        "map",
        "map",
        "hass:tooltip-account",
        require_admin=CONF_REQUIRE_ADMIN,
    )
    return True
