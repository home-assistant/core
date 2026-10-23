"""Config flow for Victron Modbus."""

import logging
from typing import Any, override

from modbus_connection import ModbusError, ModbusUdpParams
import probatio
from victron_modbus import UnsupportedDeviceError, async_identify

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, PORT, UNIT_ID
from .models import MODEL_BY_CLASS, MODELS

_LOGGER = logging.getLogger(__name__)

STEP_USER = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


class IdentifyError(Exception):
    """The device could not be identified; ``reason`` is the error key."""

    def __init__(self, reason: str) -> None:
        """Initialize with the translation key of the error to show."""
        super().__init__(reason)
        self.reason = reason


class VictronModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Modbus.

    The model is read from the device's product ID and the entry is keyed on
    its serial number, so the user only enters the host.
    """

    VERSION = 1

    _host: str
    _model: str

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a device discovered through mDNS."""
        self._host = str(discovery_info.ip_address)
        try:
            self._model, serial = await self._async_identify(self._host)
        except IdentifyError as err:
            return self.async_abort(reason=err.reason)
        await self.async_set_unique_id(serial)
        # A configured device announced at another address (a second interface,
        # or a new DHCP lease) moves the entry only if its address stopped working.
        updates = None
        if (
            (
                entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, serial
                )
            )
            is not None
            and entry.source != SOURCE_IGNORE
            and entry.data[CONF_HOST] != self._host
            and not await self._async_answers(entry.data[CONF_HOST], serial)
        ):
            updates = {CONF_HOST: self._host}
        self._abort_if_unique_id_configured(updates=updates)
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up the discovered device."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "model": MODELS[self._model].name,
                    "host": self._host,
                },
            )
        return self._async_create_entry()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address, and identify the device found there."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            try:
                self._model, serial = await self._async_identify(self._host)
            except IdentifyError as err:
                errors["base"] = err.reason
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self._async_create_entry()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the address of this device."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                model, serial = await self._async_identify(host)
            except IdentifyError as err:
                errors["base"] = err.reason
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_MODEL: model},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

    @property
    def _title(self) -> str:
        """The model and serial number, which tell two devices of a model apart."""
        return f"{MODELS[self._model].name} ({self.unique_id})"

    def _async_create_entry(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._title,
            data={CONF_HOST: self._host, CONF_MODEL: self._model},
        )

    async def _async_answers(self, host: str, serial: str) -> bool:
        """Whether the device with this serial number still answers at ``host``."""
        try:
            _, found = await self._async_identify(host)
        except IdentifyError:
            return False
        return found == serial

    async def _async_identify(self, host: str) -> tuple[str, str]:
        """Read the product ID and serial number through a temporary unit.

        Returns the model key and the serial number. Raises ``IdentifyError``
        with the reason to show the user.
        """
        params = ModbusUdpParams(host=host, port=PORT)
        try:
            async with async_get_temporary_unit(self.hass, params, UNIT_ID) as unit:
                device = await async_identify(unit)
        except UnsupportedDeviceError as err:
            _LOGGER.debug("Unsupported device at %s: %s", host, err)
            raise IdentifyError("unsupported_device") from err
        except (ModbusError, HomeAssistantError, OSError, ValueError) as err:
            _LOGGER.debug("Unable to connect to %s: %s", host, err)
            raise IdentifyError("cannot_connect") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error identifying the device at %s", host)
            raise IdentifyError("unknown") from err
        if not (serial := device.info.serial_number):
            # The serial number keys the entry, so a device without one (such as
            # an unprovisioned unit) can't be told apart from others.
            _LOGGER.debug("Device at %s reports no serial number", host)
            raise IdentifyError("no_serial")
        return MODEL_BY_CLASS[type(device)], serial
