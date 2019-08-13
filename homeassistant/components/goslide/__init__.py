"""Component for the Go Slide API."""

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from .const import (
    DOMAIN,
    SLIDES,
    API,
    COMPONENT,
    DEFAULT_TIMEOUT,
    CONF_RETRY,
    DEFAULT_RETRY,
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
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the GoSlide platform."""

    # pylint: disable=unused-argument
    async def update_slides(now=None):
        """Update slide information."""
        result = await hass.data[DOMAIN][API].slidesoverview()

        if result is None:
            _LOGGER.error("GoSlide API does not work or returned an error")
            return

        if result:
            _LOGGER.debug("GoSlide API returned %d slide(s)", len(result))
        else:
            _LOGGER.warning("GoSlide API returned 0 slides")

        for key in hass.data[DOMAIN][SLIDES]:
            hass.data[DOMAIN][SLIDES][key]["pos"] = None

        for slide in result:
            if "device_id" not in slide:
                _LOGGER.error(
                    "Found invalid GoSlide entry, 'device_id' is " "missing. Entry=%s",
                    slide,
                )
                continue

            uid = slide["device_id"].replace("slide_", "")
            slidenew = {}
            slidenew["mac"] = uid
            slidenew["id"] = slide["id"]
            slidenew["name"] = slide["device_name"]

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
                if slidenew["pos"] < 0:
                    slidenew["pos"] = 0
                elif slidenew["pos"] > 1:
                    slidenew["pos"] = 1
            elif "code" in slide["device_info"]:
                slidenew["online"] = False
                _LOGGER.warning(
                    "Slide %s (%s) is offline with " "code=%s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"]["code"],
                )
            else:
                slidenew["online"] = False
                _LOGGER.error(
                    "Slide %s (%s) has invalid 'device_info'" " %s",
                    slide["id"],
                    slidenew["mac"],
                    slide["device_info"],
                )

            hass.data[DOMAIN][SLIDES][uid] = slidenew
            _LOGGER.debug("Updated entry=%s", slidenew)

    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][SLIDES] = {}

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    scaninterval = config[DOMAIN][CONF_SCAN_INTERVAL]
    timeout = config[DOMAIN][CONF_TIMEOUT]
    retry = config[DOMAIN][CONF_RETRY]

    from goslideapi import GoSlideCloud

    hass.data[DOMAIN][API] = GoSlideCloud(username, password, timeout)

    # pylint: disable=broad-except
    try:
        result = await hass.data[DOMAIN][API].login()
    except Exception as err:
        _LOGGER.error("Error connecting to GoSlide Cloud: %s", str(err))
        _LOGGER.error("Going to retry in %s seconds", retry)
        async_call_later(hass, retry, async_setup(hass, config))
        return True

    # pylint: disable=no-else-return
    if result is None:
        _LOGGER.error("GoSlide API returned unknown error during " "authentication")
        return False
    elif result is False:
        _LOGGER.error("GoSlide authentication failed, check " "username/password")
        return False

    await update_slides()

    hass.async_create_task(async_load_platform(hass, COMPONENT, DOMAIN, {}, config))

    async_track_time_interval(hass, update_slides, scaninterval)

    return True
