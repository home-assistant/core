"""Config flow for AquaLogic."""

import contextlib
import threading
from typing import Any, override

from aqualogic.core import AquaLogic
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT): cv.port,
    }
)

# Worst case scenario, this covers both a plain socket timeout (READ_TIMEOUT)
# and an additional frame-scan timeout (another READ_TIMEOUT), plus one second.
_PROBE_TIMEOUT = AquaLogic.READ_TIMEOUT * 2 + 1


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidDevice(Exception):
    """Error to indicate the device is not an AquaLogic panel."""


def _verify_device(host: str, port: int) -> None:
    """Connect and verify the device is an AquaLogic panel.

    Raises CannotConnect if the host is unreachable.
    Raises InvalidDevice if no valid AquaLogic data is received within the timeout.
    """
    confirmed = threading.Event()

    def _on_data(_: AquaLogic) -> None:
        confirmed.set()

    panel = AquaLogic()
    try:
        panel.connect(host, port)
    except OSError as err:
        raise CannotConnect from err

    probe = threading.Thread(target=panel.process, args=(_on_data,), daemon=True)
    probe.start()
    try:
        confirmed.wait(timeout=_PROBE_TIMEOUT)
    finally:
        if (sock := panel._socket) is not None:  # noqa: SLF001
            with contextlib.suppress(OSError):
                sock.close()

    if not confirmed.is_set():
        raise InvalidDevice


class AquaLogicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AquaLogic."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)

            try:
                await self.hass.async_add_executor_job(
                    _verify_device, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidDevice:
                errors["base"] = "invalid_device"
            else:
                return self.async_create_entry(title="AquaLogic", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import AquaLogic config from configuration.yaml."""
        self._async_abort_entries_match(
            {CONF_HOST: import_data[CONF_HOST], CONF_PORT: import_data[CONF_PORT]}
        )

        try:
            await self.hass.async_add_executor_job(
                _verify_device, import_data[CONF_HOST], import_data[CONF_PORT]
            )
        except CannotConnect, InvalidDevice:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="AquaLogic", data=import_data)
