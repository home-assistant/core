"""The becker component."""
import logging

from pybecker.becker import Becker
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CHANNEL,
    CONF_COVERS,
    CONF_DEVICE,
    CONF_UNIT,
    DEFAULT_CONF_USB_STICK_PATH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PAIR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHANNEL): vol.All(int, vol.Range(min=1, max=7)),
        vol.Optional(CONF_UNIT): vol.All(int, vol.Range(min=1, max=5)),
    }
)


async def async_setup(hass, config):
    """Set up the Becker platform."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}
    hass.data[DOMAIN] = {}

    # User has configured covers
    if CONF_COVERS not in conf:
        return True
    hass.data[DOMAIN][CONF_COVERS] = {}
    covers = conf[CONF_COVERS]

    if CONF_DEVICE in conf:
        hass.data[DOMAIN][CONF_DEVICE] = conf[CONF_DEVICE]

    for cover_conf in covers:
        channel = cover_conf[CONF_CHANNEL]
        # Store config in hass.data so the config entry can find it
        hass.data[DOMAIN][CONF_COVERS][channel] = cover_conf
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={"cover": cover_conf}
            )
        )
    return True


async def async_setup_entry(hass, entry):
    """Establish connection with Becker Centronic."""
    conf = entry.data

    stick_path = conf[CONF_DEVICE]
    # if stick_path is not set in integration try to get it from configuration
    if not stick_path:
        stick_path = hass.data[DOMAIN][CONF_DEVICE]

    _LOGGER.debug("Setting Centronic stick on port {stick_path}")
    becker = BeckerConnection(stick_path)

    if not becker:
        raise ConfigEntryNotReady

    for _ in range(2):
        _LOGGER.debug("Init call to cover channel 1")
        await becker.connection.stop("1")

    hass.data[DOMAIN]["connector"] = becker.connection

    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: becker})
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "cover")
    )

    hass.services.async_register(DOMAIN, "pair", becker.handle_pair, PAIR_SCHEMA)
    hass.services.async_register(DOMAIN, "log_units", becker.handle_log_units)
    return True


class BeckerConnection:
    """Keep the Becker instance in one place and centralize the update."""

    def __init__(self, centronic_path=None):
        """Create a new instance of Becker Connection."""
        if not centronic_path:
            centronic_path = DEFAULT_CONF_USB_STICK_PATH

        self.connection = Becker(centronic_path, True)

    async def handle_pair(self, call):
        """Service to pair with a cover receiver."""

        channel = call.data[CONF_CHANNEL]
        unit = call.data.get(CONF_UNIT, 1)
        await self.connection.pair(f"{unit}:{channel}")

    async def handle_log_units(self, call):
        """Service that logs all paired units."""
        units = await self.connection.list_units()

        unit_id = 1
        _LOGGER.info("Configured Becker centronic units:")
        for row in units:
            unit_code, increment = row[0:2]
            _LOGGER.info(
                "Unit id %d, unit code %s, increment %d", unit_id, unit_code, increment
            )
            unit_id += 1
