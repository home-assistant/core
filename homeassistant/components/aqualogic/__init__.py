"""Support for AquaLogic devices."""

import contextlib
from datetime import timedelta
import logging
import threading
import time
from typing import override

from aqualogic.core import AquaLogic
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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

    hass.async_create_task(_async_import(hass, config[DOMAIN]))
    return True


async def _async_import(hass: HomeAssistant, conf: dict) -> None:
    """Import AquaLogic configuration from YAML and surface appropriate issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: conf[CONF_HOST], CONF_PORT: conf[CONF_PORT]},
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            breaks_in_ha_version="2027.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_cannot_connect",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "AquaLogic",
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "AquaLogic",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: AquaLogicConfigEntry) -> bool:
    """Set up AquaLogic from a config entry."""
    processor = AquaLogicProcessor(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    entry.runtime_data = processor

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    processor.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquaLogicConfigEntry) -> bool:
    """Unload an AquaLogic config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        processor = entry.runtime_data
        processor.shutdown()
        await hass.async_add_executor_job(lambda: processor.join(timeout=5))
        if processor.is_alive():
            _LOGGER.warning("Processor thread did not stop within timeout")
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
        self._panel: AquaLogic | None = None

    def shutdown(self) -> None:
        """Signal shutdown of processing event."""
        _LOGGER.debug("Event processing signaled exit")
        self._shutdown = True
        if (panel := self._panel) is not None and panel._socket is not None:  # noqa: SLF001
            with contextlib.suppress(OSError):
                panel._socket.close()  # noqa: SLF001

    def data_changed(self, panel: AquaLogic) -> None:
        """Aqualogic data changed callback."""
        dispatcher_send(self._hass, UPDATE_TOPIC)

    @override
    def run(self) -> None:
        """Event thread."""

        while True:
            panel = AquaLogic()
            self._panel = panel
            try:
                panel.connect(self._host, self._port)
                panel.process(self.data_changed)
            except OSError:
                pass
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected error in AquaLogic processor: %s",
                    type(err).__name__,
                )

            if self._shutdown:
                return

            _LOGGER.warning(
                "Connection to %s:%d lost, retrying in %d seconds",
                self._host,
                self._port,
                int(RECONNECT_INTERVAL.total_seconds()),
            )
            time.sleep(RECONNECT_INTERVAL.total_seconds())

    @property
    def panel(self) -> AquaLogic | None:
        """Retrieve the AquaLogic object."""
        return self._panel
