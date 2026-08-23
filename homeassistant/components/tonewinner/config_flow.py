"""Tonewinner configuration flow."""

import logging
from typing import Any, override

from tonewinner_rs232 import ReceiverInfo, TonewinnerReceiver
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as ConfigEntryFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.selector import SerialPortSelector

from .const import CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): SerialPortSelector(),
    }
)


class TonewinnerConfigFlow(ConfigEntryFlow, domain=DOMAIN):
    """Handle the Tonewinner config flow."""

    async def _async_probe_receiver(self, port: str) -> str | None:
        """Verify the port opens and return the receiver's model if reported."""
        receiver = TonewinnerReceiver(port)
        try:
            await receiver.connect()
            try:
                info: ReceiverInfo | None = await receiver.query_info()
            except ConnectionError:
                # Some firmware builds never answer the identity query.
                _LOGGER.debug("Receiver on %s did not report a model", port)
                return None
        finally:
            await receiver.disconnect()
        return info.model if info else None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step of configuration flow."""
        errors = {}
        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT]
            # Check before probing: an entry already holding the port would
            # make the probe fail even though the receiver is reachable.
            self._async_abort_entries_match({CONF_SERIAL_PORT: port})
            try:
                model = await self._async_probe_receiver(port)
            except OSError as err:
                _LOGGER.warning("Failed to probe receiver on %s: %s", port, err)
                errors["base"] = "cannot_connect"
            else:
                data: dict[str, Any] = {CONF_SERIAL_PORT: port}
                title = "Tonewinner"
                if model:
                    data[CONF_MODEL] = model
                    title = model
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the serial port connection."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT]
            if port == entry.data.get(CONF_SERIAL_PORT):
                # Unchanged port: the live connection is proof enough. The
                # probe could not run anyway while this entry holds the port.
                _LOGGER.debug("Serial port unchanged, reloading %s", entry.title)
                return self.async_update_reload_and_abort(entry)

            self._async_abort_entries_match({CONF_SERIAL_PORT: port})
            try:
                model = await self._async_probe_receiver(port)
            except OSError as err:
                _LOGGER.warning("Failed to probe receiver on %s: %s", port, err)
                errors["base"] = "cannot_connect"
            else:
                data: dict[str, Any] = {CONF_SERIAL_PORT: port}
                title = "Tonewinner"
                if model:
                    data[CONF_MODEL] = model
                    title = model
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    title=title,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, entry.data
            ),
            errors=errors,
        )
