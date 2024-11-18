"""Component for the Slide API."""

from datetime import timedelta
import logging

from goslideapi import GoSlideCloud, goslideapi
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    API,
    COMPONENT_PLATFORM,
    CONF_INVERT_POSITION,
    DEFAULT_OFFSET,
    DEFAULT_RETRY,
    DOMAIN,
    SLIDES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(CONF_INVERT_POSITION, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Slide platform."""

    async def update_slides(now=None):
        """Update slide information."""
        result = await hass.data[DOMAIN][API].slides_overview()

        if result is None:
            _LOGGER.error("Slide API does not work or returned an error")
            return

        if result:
            _LOGGER.debug("Slide API returned %d slide(s)", len(result))
        else:
            _LOGGER.warning("Slide API returned 0 slides")

        for slide in result:
            if "device_id" not in slide:
                _LOGGER.error(
                    "Found invalid Slide entry, device_id is missing. Entry=%s", slide
                )
                continue

            uid = slide["device_id"].replace("slide_", "")
            slidenew = hass.data[DOMAIN][SLIDES].setdefault(uid, {})
            slidenew["mac"] = uid
            slidenew["id"] = slide["id"]
            slidenew["name"] = slide["device_name"]
            slidenew["state"] = None
            oldpos = slidenew.get("pos")
            slidenew["pos"] = None
            slidenew["online"] = False
            slidenew["invert"] = config[DOMAIN][CONF_INVERT_POSITION]

            if "device_info" not in slide:
                _LOGGER.error(
                    "Slide %s (%s) has no device_info Entry=%s",
                    slide["id"],
                    slidenew["mac"],
                    slide,
                )
                continue

            # Check if we have pos (OK) or code (NOK)
            if "pos" in slide["device_info"]:
                slidenew["online"] = True
                slidenew["pos"] = slide["device_info"]["pos"]
                slidenew["pos"] = max(0, min(1, slidenew["pos"]))

                if oldpos is None or oldpos == slidenew["pos"]:
                    slidenew["state"] = (
                        STATE_CLOSED
                        if slidenew["pos"] > (1 - DEFAULT_OFFSET)
                        else STATE_OPEN
                    )
                elif oldpos < slidenew["pos"]:
                    slidenew["state"] = (
                        STATE_CLOSED
                        if slidenew["pos"] >= (1 - DEFAULT_OFFSET)
                        else STATE_CLOSING
                    )
                else:
                    slidenew["state"] = (
                        STATE_OPEN
                        if slidenew["pos"] <= DEFAULT_OFFSET
                        else STATE_OPENING
                    )
            elif "code" in slide["device_info"]:
                _LOGGER.warning(
                    "Slide %s (%s) is offline with code=%s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"]["code"],
                )
            else:
                _LOGGER.error(
                    "Slide %s (%s) has invalid device_info %s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"],
                )

            _LOGGER.debug("Updated entry=%s", slidenew)

    async def retry_setup(now):
        """Retry setup if a connection/timeout happens on Slide API."""
        await async_setup(hass, config)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][SLIDES] = {}

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    scaninterval = config[DOMAIN][CONF_SCAN_INTERVAL]

    hass.data[DOMAIN][API] = GoSlideCloud(username, password)

    try:
        result = await hass.data[DOMAIN][API].login()
    except (goslideapi.ClientConnectionError, goslideapi.ClientTimeoutError) as err:
        _LOGGER.error(
            "Error connecting to Slide Cloud: %s, going to retry in %s second(s)",
            err,
            DEFAULT_RETRY,
        )
        async_call_later(hass, DEFAULT_RETRY, retry_setup)
        return True

    if not result:
        _LOGGER.error("Slide API returned unknown error during authentication")
        return False

    _LOGGER.debug("Slide API successfully authenticated")

    await update_slides()

    hass.async_create_task(
        async_load_platform(hass, COMPONENT_PLATFORM, DOMAIN, {}, config)
    )

    async_track_time_interval(hass, update_slides, scaninterval)

    return True
