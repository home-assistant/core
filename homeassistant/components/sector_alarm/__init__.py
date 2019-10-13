"""The Sector Alarm Integration."""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_CODE, CONF_EMAIL
from homeassistant.helpers import discovery

DOMAIN = "sector_alarm"

_LOGGER = logging.getLogger(__name__)

CONF_ALARM_ID = "alarm_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_ALARM_ID): cv.string,
                vol.Required(CONF_CODE): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialitation for Sector Alarm."""
    try:
        import sectoralarmlib.sector as sectorlib

        alarm = sectorlib.SectorAlarm(
            config[DOMAIN][CONF_EMAIL],
            config[DOMAIN][CONF_PASSWORD],
            config[DOMAIN][CONF_ALARM_ID],
            config[DOMAIN][CONF_CODE],
        )
    except RuntimeError:
        _LOGGER.error("Could not login. Wrong username or password?")
        return

    hass.data[DOMAIN] = alarm

    discovery.load_platform(hass, "sensor", DOMAIN, {CONF_NAME: DOMAIN}, config)

    discovery.load_platform(
        hass,
        "alarm_control_panel",
        DOMAIN,
        {
            CONF_CODE: config[DOMAIN][CONF_CODE],
            CONF_ALARM_ID: config[DOMAIN][CONF_ALARM_ID],
        },
        config,
    )

    return True
