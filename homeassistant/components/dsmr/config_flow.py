"""Config flow for DSMR integration."""
import asyncio
from functools import partial
import logging
from typing import Any, Dict, Optional

from dsmr_parser import obis_references as obis_ref
from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
import serial

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class DSMRConnection:
    """Test the connection to DSMR and receive telegram to read serial ids."""

    def __init__(self, host, port, dsmr_version):
        """Initialize."""
        self._host = host
        self._port = port
        self._dsmr_version = dsmr_version
        self._telegram = {}

    def equipment_identifier(self):
        """Equipment identifier."""
        if obis_ref.EQUIPMENT_IDENTIFIER in self._telegram:
            dsmr_object = self._telegram[obis_ref.EQUIPMENT_IDENTIFIER]
            return getattr(dsmr_object, "value", None)

    def equipment_identifier_gas(self):
        """Equipment identifier gas."""
        if obis_ref.EQUIPMENT_IDENTIFIER_GAS in self._telegram:
            dsmr_object = self._telegram[obis_ref.EQUIPMENT_IDENTIFIER_GAS]
            return getattr(dsmr_object, "value", None)

    async def validate_connect(self, hass: core.HomeAssistant) -> bool:
        """Test if we can validate connection with the device."""

        def update_telegram(telegram):
            self._telegram = telegram

            transport.close()

        if self._host is None:
            reader_factory = partial(
                create_dsmr_reader,
                self._port,
                self._dsmr_version,
                update_telegram,
                loop=hass.loop,
            )
        else:
            reader_factory = partial(
                create_tcp_dsmr_reader,
                self._host,
                self._port,
                self._dsmr_version,
                update_telegram,
                loop=hass.loop,
            )

        try:
            transport, protocol = await hass.loop.create_task(reader_factory())
        except (
            serial.serialutil.SerialException,
            ConnectionRefusedError,
            TimeoutError,
            asyncio.TimeoutError,
        ):
            _LOGGER.exception("Error connecting to DSMR")
            return False

        if transport:
            await protocol.wait_closed()

        return True


class DSMRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSMR."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def _abort_if_host_port_configured(
        self,
        port: str,
        host: str = None,
        updates: Optional[Dict[Any, Any]] = None,
        reload_on_update: bool = True,
    ):
        """Test if host and port are already configured."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host and entry.data[CONF_PORT] == port:
                if updates is not None:
                    changed = self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, **updates}
                    )
                    if (
                        changed
                        and reload_on_update
                        and entry.state
                        in (
                            config_entries.ENTRY_STATE_LOADED,
                            config_entries.ENTRY_STATE_SETUP_RETRY,
                        )
                    ):
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )
                return self.async_abort(reason="already_configured")

        return None

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""
        host = import_config.get(CONF_HOST)
        port = import_config[CONF_PORT]

        status = self._abort_if_host_port_configured(port, host, import_config)
        if status is not None:
            return status

        if host is not None:
            name = f"{host}:{port}"
        else:
            name = port

        return self.async_create_entry(title=name, data=import_config)
