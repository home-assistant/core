"""Support for KEBA charging stations."""

import asyncio
import logging

from keba_kecontact.connection import KebaKeContact
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FS,
    CONF_FS_FALLBACK,
    CONF_FS_INTERVAL,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    CONF_RFID,
    DEFAULT_FS,
    DEFAULT_FS_FALLBACK,
    DEFAULT_FS_PERSIST,
    DEFAULT_FS_TIMEOUT,
    DEFAULT_RFID,
    DOMAIN,
    MAX_FAST_POLLING_COUNT,
    MAX_POLLING_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.NOTIFY,
    Platform.SENSOR,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.removed(CONF_FS_INTERVAL, raise_if_present=False),
            vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_RFID, default=DEFAULT_RFID): cv.string,
                    vol.Optional(CONF_FS, default=DEFAULT_FS): cv.boolean,
                    vol.Optional(
                        CONF_FS_TIMEOUT, default=DEFAULT_FS_TIMEOUT
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_FS_FALLBACK, default=DEFAULT_FS_FALLBACK
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_FS_PERSIST, default=DEFAULT_FS_PERSIST
                    ): cv.positive_int,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_SERVICE_MAP = {
    "request_data": "async_request_data",
    "set_energy": "async_set_energy",
    "set_current": "async_set_current",
    "authorize": "async_start",
    "deauthorize": "async_stop",
    "enable": "async_enable_ev",
    "disable": "async_disable_ev",
    "set_failsafe": "async_set_failsafe",
}

type KebaConfigEntry = ConfigEntry[KebaHandler]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services and import YAML configuration."""

    async def execute_service(call: ServiceCall) -> None:
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        if not entries:
            return
        keba: KebaHandler = entries[0].runtime_data
        function_name = _SERVICE_MAP[call.service]
        await getattr(keba, function_name)(call.data)

    for service in _SERVICE_MAP:
        hass.services.async_register(DOMAIN, service, execute_service)

    if DOMAIN in config:
        hass.async_create_task(_async_import_yaml(hass, config[DOMAIN]))
    return True


async def _async_import_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    """Import YAML configuration and create the deprecation repair issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if result["type"] is FlowResultType.ABORT and result["reason"] not in (
        "already_configured",
        "single_instance_allowed",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2027.1.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Keba Charging Station",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.1.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Keba Charging Station",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: KebaConfigEntry) -> bool:
    """Set up KEBA charging station from a config entry."""
    host = entry.data[CONF_HOST]
    keba = KebaHandler(hass, host, entry.data[CONF_RFID])

    try:
        connected = await keba.setup()
    except OSError as ex:
        raise ConfigEntryNotReady(
            f"Cannot connect to KEBA charging station at {host}: {ex}"
        ) from ex

    if not connected:
        raise ConfigEntryNotReady(f"Cannot connect to KEBA charging station at {host}")

    failsafe = entry.data[CONF_FS]
    timeout = entry.data[CONF_FS_TIMEOUT] if failsafe else 0
    fallback = entry.data[CONF_FS_FALLBACK] if failsafe else 0
    persist = entry.data[CONF_FS_PERSIST] if failsafe else 0
    try:
        await keba.set_failsafe(int(timeout), float(fallback), bool(persist))
    except ValueError as ex:
        _LOGGER.warning("Charging station rejected failsafe settings: %s", ex)

    entry.runtime_data = keba
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    keba.start_periodic_request()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KebaConfigEntry) -> bool:
    """Unload a KEBA config entry."""
    entry.runtime_data.stop_periodic_request()
    # asyncio schedules the actual socket close via call_soon; yield once so
    # the OS port is released before async_setup_entry binds it again.
    await asyncio.sleep(0)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class KebaHandler(KebaKeContact):
    """Representation of a KEBA charging station connection."""

    def __init__(self, hass: HomeAssistant, host: str, rfid: str) -> None:
        """Initialize charging station connection."""
        super().__init__(host, self.hass_callback)

        self._update_listeners: list = []
        self._hass = hass
        self.rfid = rfid
        self.device_name = "keba"  # correct device name will be set in setup()
        self.device_id = "keba_wallbox_"  # correct device id will be set in setup()

        self._fast_polling_count = MAX_FAST_POLLING_COUNT
        self._polling_task: asyncio.Task | None = None

    def start_periodic_request(self):
        """Start periodic data polling."""
        self._polling_task = self._hass.loop.create_task(self._periodic_request())

    def stop_periodic_request(self) -> None:
        """Cancel periodic data polling and release the UDP socket."""
        if self._polling_task is not None:
            self._polling_task.cancel()
            self._polling_task = None
        if self.keba_protocol is not None and self.keba_protocol._transport is not None:  # noqa: SLF001
            self.keba_protocol._transport.close()  # noqa: SLF001

    async def _periodic_request(self):
        """Send  periodic update requests."""
        await self.request_data()

        if self._fast_polling_count < MAX_FAST_POLLING_COUNT:
            self._fast_polling_count += 1
            _LOGGER.debug("Periodic data request executed, now wait for 2 seconds")
            await asyncio.sleep(2)
        else:
            _LOGGER.debug(
                "Periodic data request executed, now wait for %s seconds",
                MAX_POLLING_INTERVAL,
            )
            await asyncio.sleep(MAX_POLLING_INTERVAL)

        _LOGGER.debug("Periodic data request rescheduled")
        self._polling_task = self._hass.loop.create_task(self._periodic_request())

    async def setup(self, loop=None):
        """Initialize KebaHandler object."""
        await super().setup(loop)

        # Request initial values and extract serial number
        await self.request_data()
        if (
            self.get_value("Serial") is not None
            and self.get_value("Product") is not None
        ):
            self.device_id = f"keba_wallbox_{self.get_value('Serial')}"
            self.device_name = self.get_value("Product")
            return True

        return False

    def hass_callback(self, data):
        """Handle component notification via callback."""

        # Inform entities about updated values
        for listener in self._update_listeners:
            listener()

        _LOGGER.debug("Notifying %d listeners", len(self._update_listeners))

    def _set_fast_polling(self):
        _LOGGER.debug("Fast polling enabled")
        self._fast_polling_count = 0
        if self._polling_task is not None:
            self._polling_task.cancel()
        self._polling_task = self._hass.loop.create_task(self._periodic_request())

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
        listener()
        return lambda: self._update_listeners.remove(listener)

    async def async_request_data(self, param):
        """Request new data in async way."""
        await self.request_data()
        _LOGGER.debug("New data from KEBA wallbox requested")

    async def async_set_energy(self, param):
        """Set energy target in async way."""
        try:
            energy = param["energy"]
            await self.set_energy(float(energy))
            self._set_fast_polling()
        except (KeyError, ValueError) as ex:
            _LOGGER.warning("Energy value is not correct. %s", ex)

    async def async_set_current(self, param):
        """Set current maximum in async way."""
        try:
            current = param["current"]
            await self.set_current(float(current))
            # No fast polling as this function might be called regularly
        except (KeyError, ValueError) as ex:
            _LOGGER.warning("Current value is not correct. %s", ex)

    async def async_start(self, param=None):
        """Authorize EV in async way."""
        await self.start(self.rfid)
        self._set_fast_polling()

    async def async_stop(self, param=None):
        """De-authorize EV in async way."""
        await self.stop(self.rfid)
        self._set_fast_polling()

    async def async_enable_ev(self, param=None):
        """Enable EV in async way."""
        await self.enable(True)
        self._set_fast_polling()

    async def async_disable_ev(self, param=None):
        """Disable EV in async way."""
        await self.enable(False)
        self._set_fast_polling()

    async def async_set_failsafe(self, param=None):
        """Set failsafe mode in async way."""
        try:
            timeout = param[CONF_FS_TIMEOUT]
            fallback = param[CONF_FS_FALLBACK]
            persist = param[CONF_FS_PERSIST]
            await self.set_failsafe(int(timeout), float(fallback), bool(persist))
            self._set_fast_polling()
        except (KeyError, ValueError) as ex:
            _LOGGER.warning(
                (
                    "Values are not correct for: failsafe_timeout, failsafe_fallback"
                    " and/or failsafe_persist: %s"
                ),
                ex,
            )
