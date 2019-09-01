"""Component for the Go Slide API."""

import logging
from datetime import timedelta

import voluptuous as vol

from goslideapi import GoSlideCloud

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    STATE_OPEN,
    STATE_CLOSED,
    STATE_OPENING,
    STATE_CLOSING,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from .const import DOMAIN, SLIDES, API, COMPONENT, DEFAULT_RETRY

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
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Slide platform."""

    async def update_slides(now=None):
        """Update slide information."""
        result = await hass.data[DOMAIN][API].slidesoverview()

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
                    "Found invalid Slide entry, 'device_id' is " "missing. Entry=%s",
                    slide,
                )
                continue

            uid = slide["device_id"].replace("slide_", "")
            slidenew = hass.data[DOMAIN][SLIDES].get(uid, {})
            slidenew["mac"] = uid
            slidenew["id"] = slide["id"]
            slidenew["name"] = slide["device_name"]
            slidenew["state"] = None
            oldpos = slidenew.get("pos", None)
            slidenew["pos"] = None
            slidenew["online"] = False

            if "device_info" not in slide:
                _LOGGER.error(
                    "Slide %s (%s) has no 'device_info' Entry=%s",
                    slide["id"],
                    slidenew["mac"],
                    slide,
                )
                continue

            # Check if we have 'pos' (OK) or 'code' (NOK)
            if "pos" in slide["device_info"]:
                slidenew["online"] = True
                slidenew["pos"] = slide["device_info"]["pos"]
                slidenew["pos"] = max(0, min(1, slidenew["pos"]))

                if oldpos is None or oldpos == slidenew["pos"]:
                    slidenew["state"] = (
                        STATE_CLOSED if slidenew["pos"] > 0.95 else STATE_OPEN
                    )
                elif oldpos < slidenew["pos"]:
                    slidenew["state"] = (
                        STATE_CLOSED if slidenew["pos"] >= 0.95 else STATE_CLOSING
                    )
                else:
                    slidenew["state"] = (
                        STATE_OPEN if slidenew["pos"] <= 0.05 else STATE_OPENING
                    )
            elif "code" in slide["device_info"]:
                _LOGGER.warning(
                    "Slide %s (%s) is offline with " "code=%s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"]["code"],
                )
            else:
                _LOGGER.error(
                    "Slide %s (%s) has invalid 'device_info'" " %s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"],
                )

            old_slide = hass.data[DOMAIN][SLIDES].setdefault(uid, {})
            old_slide.update(slidenew)
            _LOGGER.debug("Updated entry=%s", slidenew)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][SLIDES] = {}

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    scaninterval = config[DOMAIN][CONF_SCAN_INTERVAL]

    hass.data[DOMAIN][API] = GoSlideCloud(username, password)

    # pylint: disable=broad-except
    try:
        result = await hass.data[DOMAIN][API].login()
    except Exception as err:
        _LOGGER.error(
            "Error connecting to Slide Cloud: %s, Going to retry in %s seconds",
            str(err),
            DEFAULT_RETRY,
        )
        async_call_later(hass, DEFAULT_RETRY, async_setup(hass, config))
        return True

    if result is None:
        _LOGGER.error("Slide API returned unknown error during " "authentication")
        return False
    if result is False:
        _LOGGER.error("Slide authentication failed, check " "username/password")
        return False

    await update_slides()

    hass.async_create_task(async_load_platform(hass, COMPONENT, DOMAIN, {}, config))

    async_track_time_interval(hass, update_slides, scaninterval)

    return True
