"""Config flow for DSMR integration."""

import asyncio
from functools import partial
from typing import Any, override

from dsmr_parser import obis_references as obis_ref
from dsmr_parser.clients.protocol import create_dsmr_reader
from dsmr_parser.clients.rfxtrx_protocol import create_rfxtrx_dsmr_reader
from dsmr_parser.objects import DSMRObject
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SerialPortSelector

from .const import (
    CONF_DSMR_VERSION,
    CONF_ENCRYPTION_KEY,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    CONF_TIME_BETWEEN_UPDATE,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DOMAIN,
    DSMR_PROTOCOL,
    DSMR_VERSIONS,
    DSMR_VERSIONS_WITHOUT_EQUIPMENT_ID,
    ENCRYPTED_DSMR_VERSIONS,
    LOGGER,
    RFXTRX_DSMR_PROTOCOL,
)


class DSMRConnection:
    """Test the connection to DSMR and receive telegram to read serial ids."""

    def __init__(
        self,
        port: str,
        dsmr_version: str,
        protocol: str,
        encryption_key: str = "",
    ) -> None:
        """Initialize."""
        self._port = port
        self._dsmr_version = dsmr_version
        self._protocol = protocol
        self._encryption_key = encryption_key
        self._decryption_failed = False
        self._telegram: dict[str, DSMRObject] = {}
        self._equipment_identifier = obis_ref.EQUIPMENT_IDENTIFIER
        if dsmr_version == "5B":
            self._equipment_identifier = obis_ref.BELGIUM_EQUIPMENT_IDENTIFIER
        if dsmr_version in ("5L", "5EONHU", "MSn"):
            self._equipment_identifier = obis_ref.LUXEMBOURG_EQUIPMENT_IDENTIFIER
        if dsmr_version == "Q3D":
            self._equipment_identifier = obis_ref.Q3D_EQUIPMENT_IDENTIFIER

    def equipment_identifier(self) -> str | None:
        """Equipment identifier."""
        if self._equipment_identifier in self._telegram:
            dsmr_object = self._telegram[self._equipment_identifier]
            identifier: str | None = getattr(dsmr_object, "value", None)
            return identifier
        return None

    def equipment_identifier_gas(self) -> str | None:
        """Equipment identifier gas."""
        if obis_ref.EQUIPMENT_IDENTIFIER_GAS in self._telegram:
            dsmr_object = self._telegram[obis_ref.EQUIPMENT_IDENTIFIER_GAS]
            identifier: str | None = getattr(dsmr_object, "value", None)
            return identifier
        return None

    async def validate_connect(self, hass: HomeAssistant) -> bool:
        """Test if we can validate connection with the device."""

        def update_telegram(telegram: dict[str, DSMRObject]) -> None:
            if self._equipment_identifier in telegram:
                self._telegram = telegram
                transport.close()
            # Some meters (e.g. Swedish, Austrian Sagemcom) have no equipment
            # identifier, so fall back to the telegram timestamp.
            if (
                self._dsmr_version in DSMR_VERSIONS_WITHOUT_EQUIPMENT_ID
                and obis_ref.P1_MESSAGE_TIMESTAMP in telegram
            ):
                self._telegram = telegram
                transport.close()

        # The encryption key is only supported by the standard DSMR reader, not
        # by the RFXtrx reader; encrypted meters always use DSMR_PROTOCOL.
        # authentication_key=None opts into decrypt-without-verification (the GCM
        # tag is not checked; integrity comes from the telegram CRC).
        key_kwargs: dict[str, Any] = {}
        if self._protocol == DSMR_PROTOCOL:
            create_reader = create_dsmr_reader
            key_kwargs = {
                "encryption_key": self._encryption_key,
                "authentication_key": None,
            }
        else:
            create_reader = create_rfxtrx_dsmr_reader
        reader_factory = partial(
            create_reader,
            self._port,
            self._dsmr_version,
            update_telegram,
            loop=hass.loop,
            **key_kwargs,
        )

        try:
            transport, protocol = await reader_factory()
        except OSError:
            LOGGER.exception("Error connecting to DSMR")
            return False

        if transport:
            try:
                async with asyncio.timeout(30):
                    await protocol.wait_closed()
            except TimeoutError:
                # Timeout (no data received), close transport
                # and return True (if telegram is empty, will
                # result in CannotCommunicate error)
                transport.close()
                await protocol.wait_closed()
            # A wrong key tears the connection down immediately (the protocol
            # closes the transport on a DecryptionError), so wait_closed()
            # returns before the timeout. Surface it as a key error.
            if getattr(protocol, "decryption_error", None) is not None:
                self._decryption_failed = True
        return True

    def decryption_failed(self) -> bool:
        """Return whether decryption failed (wrong key)."""
        return self._decryption_failed


async def _validate_dsmr_connection(
    hass: HomeAssistant, data: dict[str, Any], protocol: str
) -> dict[str, str | None]:
    """Validate the user input allows us to connect."""
    conn = DSMRConnection(
        data[CONF_PORT],
        data[CONF_DSMR_VERSION],
        protocol,
        data.get(CONF_ENCRYPTION_KEY, ""),
    )

    if not await conn.validate_connect(hass):
        raise CannotConnect

    if conn.decryption_failed():
        raise InvalidKey

    equipment_identifier = conn.equipment_identifier()
    equipment_identifier_gas = conn.equipment_identifier_gas()

    # Check only for equipment identifier in case no gas meter is connected
    if (
        equipment_identifier is None
        and data[CONF_DSMR_VERSION] not in DSMR_VERSIONS_WITHOUT_EQUIPMENT_ID
    ):
        raise CannotCommunicate

    return {
        CONF_SERIAL_ID: equipment_identifier,
        CONF_SERIAL_ID_GAS: equipment_identifier_gas,
    }


class DSMRFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSMR."""

    VERSION = 1

    _pending_data: dict[str, Any]
    _pending_title: str

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DSMROptionFlowHandler:
        """Get the options flow for this handler."""
        return DSMROptionFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes an integration.

        A single serial port selector handles both local serial devices and
        network connections; a network meter can be reached by entering a URL
        such as ``socket://host:port``.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_DSMR_VERSION] in ENCRYPTED_DSMR_VERSIONS:
                self._pending_data = user_input
                self._pending_title = user_input[CONF_PORT]
                return await self.async_step_encryption_key()

            data = await self.async_validate_dsmr(user_input, errors)
            if not errors:
                return self.async_create_entry(title=data[CONF_PORT], data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT): SerialPortSelector(),
                vol.Required(CONF_DSMR_VERSION): vol.In(DSMR_VERSIONS),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the decryption key of an encrypted meter.

        Only the encryption key is needed: decryption does not verify the GCM
        authentication tag (integrity comes from the telegram CRC), so no
        authentication key is required.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            data = await self.async_validate_dsmr(
                {**self._pending_data, **user_input}, errors
            )
            if not errors:
                return self.async_create_entry(title=self._pending_title, data=data)

        return self.async_show_form(
            step_id="encryption_key",
            data_schema=vol.Schema({vol.Required(CONF_ENCRYPTION_KEY): str}),
            errors=errors,
        )

    async def async_validate_dsmr(
        self, input_data: dict[str, Any], errors: dict[str, str]
    ) -> dict[str, Any]:
        """Validate dsmr connection and create data."""
        data = input_data

        try:
            try:
                protocol = DSMR_PROTOCOL
                info = await _validate_dsmr_connection(self.hass, data, protocol)
            except CannotCommunicate:
                # Encrypted meters are only supported over the standard DSMR
                # protocol, so don't fall back to RFXtrx for them.
                if data[CONF_DSMR_VERSION] in ENCRYPTED_DSMR_VERSIONS:
                    raise
                protocol = RFXTRX_DSMR_PROTOCOL
                info = await _validate_dsmr_connection(self.hass, data, protocol)

            data = {**data, **info, CONF_PROTOCOL: protocol}

            if info[CONF_SERIAL_ID]:
                await self.async_set_unique_id(info[CONF_SERIAL_ID])
                self._abort_if_unique_id_configured()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except CannotCommunicate:
            errors["base"] = "cannot_communicate"
        except InvalidKey:
            errors["base"] = "invalid_key"

        return data


class DSMROptionFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TIME_BETWEEN_UPDATE,
                        default=self.config_entry.options.get(
                            CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class CannotCommunicate(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidKey(HomeAssistantError):
    """Error to indicate the decryption key is invalid."""
