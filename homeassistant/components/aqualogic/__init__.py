"""Support for AquaLogic devices."""

from datetime import timedelta
import logging
import threading
import time

from aqualogic.core import AquaLogic
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, UPDATE_TOPIC

_LOGGER = logging.getLogger(__name__)

RECONNECT_INTERVAL = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

type AquaLogicConfigEntry = ConfigEntry[AquaLogicProcessor]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AquaLogic component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: conf[CONF_HOST], CONF_PORT: conf[CONF_PORT]},
        )
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "AquaLogic",
        },
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AquaLogicConfigEntry) -> bool:
    """Set up AquaLogic from a config entry."""
    processor = AquaLogicProcessor(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    entry.runtime_data = processor

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, processor.shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    processor.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquaLogicConfigEntry) -> bool:
    """Unload an AquaLogic config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.shutdown()

    return unload_ok


class AquaLogicProcessor(threading.Thread):
    """AquaLogic event processor thread."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the data object."""
        super().__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        self._shutdown = False
        self._panel = None

    def shutdown(self, event: Event | None = None) -> None:
        """Signal shutdown of processing event."""
        _LOGGER.debug("Event processing signaled exit")
        self._shutdown = True

    def data_changed(self, panel: AquaLogic) -> None:
        """Aqualogic data changed callback."""
        dispatcher_send(self._hass, UPDATE_TOPIC)

    def run(self) -> None:
        """Event thread."""

        while True:
            panel = AquaLogic()
            self._panel = panel
            panel.connect(self._host, self._port)
            panel.process(self.data_changed)

            if self._shutdown:
                return

            _LOGGER.error("Connection to %s:%d lost", self._host, self._port)
            time.sleep(RECONNECT_INTERVAL.total_seconds())

    @property
    def panel(self) -> AquaLogic | None:
        """Retrieve the AquaLogic object."""
        return self._panel
