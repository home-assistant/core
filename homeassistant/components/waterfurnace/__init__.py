"""Support for WaterFurnace geothermal systems."""

from __future__ import annotations

from datetime import timedelta
import logging
import threading
import time

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, INTEGRATION_TITLE, MAX_FAILS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

UPDATE_TOPIC = f"{DOMAIN}_update"
SCAN_INTERVAL = timedelta(seconds=10)
ERROR_INTERVAL = timedelta(seconds=300)
NOTIFICATION_ID = "waterfurnace_website_notification"
NOTIFICATION_TITLE = "WaterFurnace website status"
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
type WaterFurnaceConfigEntry = ConfigEntry[WaterFurnaceData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the WaterFurnace configuration from YAML."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_setup(hass, config))

    return True


async def _async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config[DOMAIN],
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.8.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Set up WaterFurnace from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = WaterFurnace(username, password)

    try:
        await hass.async_add_executor_job(client.login)
    except WFCredentialError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please update your credentials."
        ) from err

    if not client.gwid:
        raise ConfigEntryNotReady(
            "Failed to connect to WaterFurnace service: No GWID found for device"
        )

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class WaterFurnaceData(threading.Thread):
    """WaterFurnace Data collector.

    This is implemented as a dedicated thread polling a websocket in a
    tight loop. The websocket will shut itself from the server side if
    a packet is not sent at least every 30 seconds. The reading is
    cheap, the login is less cheap, so keeping this open and polling
    on a very regular cadence is actually the least io intensive thing
    to do.
    """

    def __init__(self, hass: HomeAssistant, client) -> None:
        """Initialize the data object."""
        super().__init__()
        self.hass = hass
        self.client = client
        self.unit = self.client.gwid
        self.data = None
        self._shutdown = False
        self._fails = 0
        self.device_metadata = next(
            (device for device in client.devices if device.gwid == self.unit), None
        )

    def _reconnect(self):
        """Reconnect on a failure."""

        self._fails += 1
        if self._fails > MAX_FAILS:
            _LOGGER.error("Failed to refresh login credentials. Thread stopped")
            persistent_notification.create(
                self.hass,
                (
                    "Error:<br/>Connection to waterfurnace website failed "
                    "the maximum number of times. Thread has stopped"
                ),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID,
            )

            self._shutdown = True
            return

        # sleep first before the reconnect attempt
        _LOGGER.debug("Sleeping for fail # %s", self._fails)
        time.sleep(self._fails * ERROR_INTERVAL.total_seconds())

        try:
            self.client.login()
            self.data = self.client.read()
        except WFException:
            _LOGGER.exception("Failed to reconnect attempt %s", self._fails)
        else:
            _LOGGER.debug("Reconnected to furnace")
            self._fails = 0

    def run(self):
        """Thread run loop."""

        @callback
        def register():
            """Connect to hass for shutdown."""

            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown")
                self._shutdown = True
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        self.hass.add_job(register)

        # This does a tight loop in sending read calls to the
        # websocket. That's a blocking call, which returns pretty
        # quickly (1 second). It's important that we do this
        # frequently though, because if we don't call the websocket at
        # least every 30 seconds the server side closes the
        # connection.
        while True:
            if self._shutdown:
                _LOGGER.debug("Graceful shutdown")
                return

            try:
                self.data = self.client.read()

            except WFException:
                # WFExceptions are things the WF library understands
                # that pretty much can all be solved by logging in and
                # back out again.
                _LOGGER.exception("Failed to read data, attempting to recover")
                self._reconnect()

            else:
                dispatcher_send(self.hass, UPDATE_TOPIC)
                time.sleep(SCAN_INTERVAL.total_seconds())
