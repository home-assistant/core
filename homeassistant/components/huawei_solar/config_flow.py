"""Config flow for Huawei Solar integration."""
from __future__ import annotations

import logging
from typing import Any

from huawei_solar import (
    ConnectionException,
    HuaweiSolarBridge,
    HuaweiSolarException,
    ReadException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_SLAVE_IDS, DEFAULT_PORT, DEFAULT_SLAVE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SLAVE_IDS, default=str(DEFAULT_SLAVE_ID)): str,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    bridge = None
    try:
        bridge = await HuaweiSolarBridge.create(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            slave_id=data[CONF_SLAVE_IDS][0],
        )

        _LOGGER.info(
            "Successfully connected to inverter %s with SN %s",
            bridge.model_name,
            bridge.serial_number,
        )

        result = {
            "model_name": bridge.model_name,
            "serial_number": bridge.serial_number,
        }

        # Also validate the other slave-ids
        for slave_id in data[CONF_SLAVE_IDS][1:]:
            try:
                slave_bridge = await HuaweiSolarBridge.create_extra_slave(
                    bridge, slave_id
                )

                _LOGGER.info(
                    "Successfully connected to slave inverter %s: %s with SN %s",
                    slave_id,
                    slave_bridge.model_name,
                    slave_bridge.serial_number,
                )
            except HuaweiSolarException as err:
                _LOGGER.error("Could not connect to slave %s", slave_id)
                raise SlaveException(f"Could not connect to slave {slave_id}") from err

        # Return info that you want to store in the config entry.
        return result

    finally:
        if bridge is not None:
            # Cleanup this inverter object explicitly to prevent it from trying to maintain a modbus connection
            await bridge.stop()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Huawei Solar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""

        self._host: str | None = None
        self._port: int | None = None
        self._slave_ids: list[int] | None = None

        self._inverter_info: dict | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input is not None:
            try:
                user_input[CONF_SLAVE_IDS] = list(
                    map(int, user_input[CONF_SLAVE_IDS].split(","))
                )
            except ValueError:
                errors["base"] = "invalid_slave_ids"
            else:

                try:
                    info = await validate_input(user_input)

                except ConnectionException:
                    errors["base"] = "cannot_connect"
                except SlaveException:
                    errors["base"] = "slave_cannot_connect"
                except ReadException:
                    errors["base"] = "read_error"
                except Exception as exception:  # pylint: disable=broad-except
                    _LOGGER.exception(exception)
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(info["serial_number"])
                    self._abort_if_unique_id_configured()

                    self._host = user_input[CONF_HOST]
                    self._port = user_input[CONF_PORT]
                    self._slave_ids = user_input[CONF_SLAVE_IDS]

                    self._inverter_info = info
                    self.context["title_placeholders"] = {"name": info["model_name"]}

                    return await self._create_entry()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _create_entry(self):
        """Create the entry."""
        assert self._host is not None
        assert self._port is not None
        assert self._slave_ids is not None

        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_SLAVE_IDS: self._slave_ids,
        }

        return self.async_create_entry(
            title=self._inverter_info["model_name"], data=data
        )


class SlaveException(Exception):
    """Error while testing communication with a slave."""
