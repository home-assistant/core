"""Support for Hydrawise cloud."""


from pydrawise.legacy import LegacyHydrawise
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, NOTIFICATION_ID, NOTIFICATION_TITLE, SCAN_INTERVAL
from .coordinator import HydrawiseDataUpdateCoordinator

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hunter Hydrawise component."""
    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        hydrawise = await hass.async_add_executor_job(LegacyHydrawise, access_token)
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        _show_failure_notification(hass, str(ex))
        return False

    if not hydrawise.current_controller:
        LOGGER.error("Failed to fetch Hydrawise data")
        _show_failure_notification(hass, "Failed to fetch Hydrawise data.")
        return False

    hass.data[DOMAIN] = HydrawiseDataUpdateCoordinator(hass, hydrawise, scan_interval)

    # NOTE: We don't need to call async_config_entry_first_refresh() because
    # data is fetched when the Hydrawiser object is instantiated.

    return True


def _show_failure_notification(hass: HomeAssistant, error: str) -> None:
    persistent_notification.create(
        hass,
        f"Error: {error}<br />You will need to restart hass after fixing.",
        title=NOTIFICATION_TITLE,
        notification_id=NOTIFICATION_ID,
    )
