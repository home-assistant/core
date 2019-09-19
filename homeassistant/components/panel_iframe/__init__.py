"""Register an iFrame front end panel."""
import voluptuous as vol

from homeassistant.const import CONF_ICON, CONF_URL
import homeassistant.helpers.config_validation as cv

DOMAIN = "panel_iframe"

CONF_TITLE = "title"

CONF_RELATIVE_URL_ERROR_MSG = "Invalid relative URL. Absolute path required."
CONF_RELATIVE_URL_REGEX = r"\A/"
CONF_REQUIRE_ADMIN = "require_admin"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Schema(
                {
                    # pylint: disable=no-value-for-parameter
                    vol.Optional(CONF_TITLE): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
                    vol.Required(CONF_URL): vol.Any(
                        vol.Match(
                            CONF_RELATIVE_URL_REGEX, msg=CONF_RELATIVE_URL_ERROR_MSG
                        ),
                        vol.Url(),
                    ),
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the iFrame frontend panels."""
    for url_path, info in config[DOMAIN].items():
        hass.components.frontend.async_register_built_in_panel(
            "iframe",
            info.get(CONF_TITLE),
            info.get(CONF_ICON),
            url_path,
            {"url": info[CONF_URL]},
            require_admin=info[CONF_REQUIRE_ADMIN],
        )

    return True
