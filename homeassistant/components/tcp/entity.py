"""Common code for TCP component."""

from datetime import datetime, timedelta
import logging
import socket
import ssl
from typing import Final, override

from homeassistant.const import (
    CONF_HOST,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.template import Template

from . import TcpConfigEntry
from .const import CONF_BUFFER_SIZE, CONF_OBJECT_ID, CONF_VALUE_ON, DOMAIN
from .model import TcpSensorConfig

_LOGGER: Final = logging.getLogger(__name__)


class TcpEntity(Entity):
    """Base entity class for TCP platform."""

    _attr_has_entity_name = True
    _attr_name = None
    _entity_id_format: str

    def __init__(self, hass: HomeAssistant, entry: TcpConfigEntry) -> None:
        """Set all the config values."""
        data = entry.data
        template = data.get(CONF_VALUE_TEMPLATE)
        self._config: TcpSensorConfig = {
            CONF_HOST: data[CONF_HOST],
            CONF_PORT: data[CONF_PORT],
            CONF_TIMEOUT: data[CONF_TIMEOUT],
            CONF_PAYLOAD: data[CONF_PAYLOAD],
            CONF_UNIT_OF_MEASUREMENT: data.get(CONF_UNIT_OF_MEASUREMENT),
            CONF_VALUE_TEMPLATE: Template(template, hass) if template else None,
            CONF_VALUE_ON: data.get(CONF_VALUE_ON),
            CONF_BUFFER_SIZE: data[CONF_BUFFER_SIZE],
            CONF_SSL: data[CONF_SSL],
            CONF_VERIFY_SSL: data[CONF_VERIFY_SSL],
        }

        self._ssl_context: ssl.SSLContext | None = None
        if self._config[CONF_SSL]:
            self._ssl_context = ssl.create_default_context()
            if not self._config[CONF_VERIFY_SSL]:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE

        self._state: str | None = None
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )
        if object_id := data.get(CONF_OBJECT_ID):
            self.entity_id = self._entity_id_format.format(object_id)
        self._custom_interval: timedelta | None = None
        if (interval := data.get(CONF_SCAN_INTERVAL)) is not None:
            self._custom_interval = timedelta(seconds=interval)
            self._attr_should_poll = False

    def update(self) -> None:
        """Get the latest value for this sensor."""
        host = self._config[CONF_HOST]
        port = self._config[CONF_PORT]
        try:
            with socket.create_connection(
                (host, port), self._config[CONF_TIMEOUT]
            ) as raw_sock:
                sock = raw_sock
                if self._ssl_context is not None:
                    sock = self._ssl_context.wrap_socket(raw_sock, server_hostname=host)
                with sock:
                    sock.sendall(self._config[CONF_PAYLOAD].encode())
                    value = sock.recv(self._config[CONF_BUFFER_SIZE]).decode()
        except TimeoutError:
            self._attr_available = False
            _LOGGER.warning("Timeout communicating with %s on port %s", host, port)
            return
        except OSError as err:
            self._attr_available = False
            _LOGGER.error("Error communicating with %s on port %s: %s", host, port, err)
            return

        self._attr_available = True
        value_template = self._config[CONF_VALUE_TEMPLATE]
        if value_template is None:
            self._state = value
            return
        try:
            self._state = value_template.render(parse_result=False, value=value)
        except TemplateError:
            _LOGGER.error(
                "Unable to render template %r with value %r",
                value_template.template,
                value,
            )

    @override
    async def async_added_to_hass(self) -> None:
        """Poll with the interval imported from YAML, if any."""
        if self._custom_interval is not None and not (
            self.platform.config_entry
            and self.platform.config_entry.pref_disable_polling
        ):
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_interval_update, self._custom_interval
                )
            )

    async def _async_interval_update(self, now: datetime) -> None:
        """Update the entity at the custom interval."""
        await self.async_update_ha_state(True)
