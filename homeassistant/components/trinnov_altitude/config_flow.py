"""Config flow for Hello World integration."""

from __future__ import annotations

import logging
from typing import Any

from trinnov_altitude.exceptions import ConnectionFailedError, ConnectionTimeoutError
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST

from . import TrinnovAltitude
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)
DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_input(data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    host = data[CONF_HOST].strip()
    device = TrinnovAltitude(host=host)
    device_id = None

    try:
        await device.connect()
        device_id = device.id
    except ConnectionFailedError as exc:
        raise ConnectionFailed from exc
    except ConnectionTimeoutError as exc:
        raise ConnectionTimeout from exc
    finally:
        await device.disconnect()

    return {"host": host, "id": device_id, "title": f"Trinnov Altitude ({device_id})"}


class TrinnovAltitudeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trinnov Altitude."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(user_input)
            except ConnectionFailed:
                errors["host"] = "invalid_host"
            except ConnectionTimeout:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["id"], raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: info["host"]})
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class ConnectionFailed(exceptions.HomeAssistantError):
    """Error to indicate that we could not connect to the provided host."""


class ConnectionTimeout(exceptions.HomeAssistantError):
    """Error to indicate that we timed out trying to connect to the provided host."""
