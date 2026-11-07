"""Config flow for TSUN micro-inverters."""

import logging
from typing import Any, override

from tsun_local_api import (
    LoggerMetadata,
    TsunClient,
    TsunConnectionError,
    TsunError,
    async_read_logger_metadata,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_FIRMWARE_VERSION,
    CONF_INVERTER_SN,
    CONF_LOGGER_SN,
    CONF_MAC_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _connection_schema(*, request_logger_sn: bool = False) -> vol.Schema:
    schema: dict[vol.Marker, Any] = {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
    if request_logger_sn:
        schema[vol.Required(CONF_LOGGER_SN)] = vol.All(
            vol.Coerce(int), vol.Range(min=1, max=0xFFFFFFFF)
        )
    return vol.Schema(schema)


async def _async_validate(data: dict[str, Any], metadata: LoggerMetadata) -> str:
    client = TsunClient(
        data[CONF_HOST],
        data[CONF_LOGGER_SN],
        port=data[CONF_PORT],
        metadata=metadata,
    )
    telemetry = await client.async_read()
    return telemetry.device.model


class TsunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TSUN."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._request_logger_sn = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a TSUN micro-inverter from its local address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            automatically_detected = CONF_LOGGER_SN not in data
            metadata = LoggerMetadata()
            try:
                metadata = await async_read_logger_metadata(
                    async_get_clientsession(self.hass),
                    str(data[CONF_HOST]),
                )
            except TsunError:
                if automatically_detected:
                    self._request_logger_sn = True
                    errors["base"] = "cannot_detect_logger_sn"
            except Exception:
                _LOGGER.exception("Unexpected exception while connecting to TSUN")
                errors["base"] = "unknown"

            if not errors and automatically_detected:
                if metadata.logger_sn is None:
                    self._request_logger_sn = True
                    errors["base"] = "cannot_detect_logger_sn"
                else:
                    data[CONF_LOGGER_SN] = metadata.logger_sn

            if not errors:
                metadata = LoggerMetadata(
                    logger_sn=int(data[CONF_LOGGER_SN]),
                    inverter_serial_number=metadata.inverter_serial_number,
                    firmware_version=metadata.firmware_version,
                    mac_address=metadata.mac_address,
                )
                try:
                    model = await _async_validate(data, metadata)
                except TsunConnectionError:
                    errors["base"] = "cannot_connect"
                except TsunError:
                    errors["base"] = "invalid_response"
                except Exception:
                    _LOGGER.exception("Unexpected exception while connecting to TSUN")
                    errors["base"] = "unknown"
                else:
                    unique_id = str(data[CONF_LOGGER_SN])
                    await self.async_set_unique_id(unique_id)
                    metadata_updates = {
                        key: value
                        for key, value in {
                            CONF_INVERTER_SN: metadata.inverter_serial_number,
                            CONF_FIRMWARE_VERSION: metadata.firmware_version,
                            CONF_MAC_ADDRESS: metadata.mac_address,
                        }.items()
                        if value is not None
                    }
                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: data[CONF_HOST],
                            CONF_PORT: data[CONF_PORT],
                            **metadata_updates,
                        }
                    )
                    data.update(metadata_updates)
                    return self.async_create_entry(title=model, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _connection_schema(request_logger_sn=self._request_logger_sn),
                user_input or {},
            ),
            errors=errors,
        )
