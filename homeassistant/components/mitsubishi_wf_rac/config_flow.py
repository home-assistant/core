"""Config flow for the Mitsubishi WF-RAC integration."""

from collections.abc import Callable
import logging
from typing import Any, override
from uuid import uuid4

import probatio
from pywfrac import Repository, WfRacAccountTableFullError, WfRacError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_BASE, CONF_DEVICE_ID, CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_AIRCO_ID, CONF_OPERATOR_ID, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class WfRacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 8
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Start a flow with no identifiers generated yet."""
        self._discovery_info: dict[str, Any] = {}
        self._generated_operator_id: str | None = None
        self._generated_device_id: str | None = None

    def _existing_value(self, key: str) -> str | None:
        """Return the first non-empty value of key among the existing entries."""
        for entry in self._async_current_entries():
            if value := entry.data.get(key):
                return str(value)
        return None

    def _repository(self, data: dict[str, Any], port: int) -> Repository:
        return Repository(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            port,
            data[CONF_OPERATOR_ID],
            data[CONF_DEVICE_ID],
        )

    async def _async_connect(
        self,
        data: dict[str, Any],
        allow_port_fallback: bool = False,
    ) -> Repository:
        """Read the airco's id into data and return the client that got it.

        allow_port_fallback is for discovery only; a typed port is not retried.
        """
        repository = self._repository(data, data[CONF_PORT])

        try:
            airco_id = await repository.get_airco_id()
        except (WfRacError, KeyError, TypeError) as query_failed:
            # Announced ports can be wrong; the real one is fixed in the firmware.
            if not allow_port_fallback or data[CONF_PORT] == DEFAULT_PORT:
                _LOGGER.debug("Could not query the airco: %s", query_failed)
                raise CannotConnect from query_failed
            _LOGGER.warning(
                "No answer on announced port %s, retrying on %s. Please report "
                "this with the discovery details - the announced port is "
                "supposed to be %s on every firmware branch",
                data[CONF_PORT],
                DEFAULT_PORT,
                DEFAULT_PORT,
            )
            repository = self._repository(data, DEFAULT_PORT)
            try:
                airco_id = await repository.get_airco_id()
            except (WfRacError, KeyError, TypeError) as retry_failed:
                _LOGGER.debug("Could not query the airco: %s", retry_failed)
                raise CannotConnect from retry_failed
            data[CONF_PORT] = DEFAULT_PORT

        if not airco_id:
            raise CannotConnect
        data[CONF_AIRCO_ID] = airco_id
        return repository

    async def _async_register(self, repository: Repository, airco_id: str) -> None:
        """Take one of the airco's account slots."""
        _LOGGER.debug("Registering with airco [%s]", airco_id)
        try:
            await repository.async_register(airco_id, self.hass.config.time_zone)
        except WfRacAccountTableFullError as table_full:
            _LOGGER.debug("Registration refused: %s", table_full)
            raise TooManyDevicesRegistered from table_full
        except (WfRacError, KeyError, TypeError) as registration_failed:
            _LOGGER.debug("Registration failed: %s", registration_failed)
            raise CannotConnect from registration_failed

    @staticmethod
    def _form_error(error: Exception) -> str:
        """Return the form error key for a failed connect or registration."""
        if isinstance(error, KnownError):
            _LOGGER.debug("Create failed: %s", error)
            return error.error_name
        # Flow boundary: show an error form instead of crashing the flow.
        _LOGGER.error("Unexpected exception", exc_info=error)
        return "unknown"

    async def _async_fetch_operator_id(self) -> str:
        """Fetch UUID operator id if exists otherwise create it."""
        if existing := self._existing_value(CONF_OPERATOR_ID):
            return existing
        # Generated once per flow: a registration with a lost answer still took a slot.
        if self._generated_operator_id is None:
            # 36 characters: firmware 025 drops a request with a longer one.
            self._generated_operator_id = f"hassio-{str(uuid4())[7:]}"
        return self._generated_operator_id

    async def _async_fetch_device_id(self) -> str:
        """Fetch unique device id if exists otherwise create it."""
        if existing := self._existing_value(CONF_DEVICE_ID):
            return existing
        if self._generated_device_id is None:
            self._generated_device_id = f"homeassistant-device-{uuid4().hex[21:]}"
        return self._generated_device_id

    async def _async_create_common(
        self,
        step_id: str,
        build_schema: Callable[[], probatio.Schema],
        user_input: dict[str, Any] | None = None,
        description_placeholders: dict[str, str] | None = None,
        allow_port_fallback: bool = False,
    ) -> ConfigFlowResult:
        """Create a new entry.

        The schema is built per call so a re-shown form suggests the current values.
        """
        errors: dict[str, str] = {}
        description_placeholders = description_placeholders or {}

        if user_input:
            user_input[CONF_OPERATOR_ID] = await self._async_fetch_operator_id()
            user_input[CONF_DEVICE_ID] = await self._async_fetch_device_id()
            try:
                repository = await self._async_connect(
                    user_input, allow_port_fallback=allow_port_fallback
                )
            except Exception as error:  # noqa: BLE001
                errors[CONF_BASE] = self._form_error(error)
            else:
                airco_id: str = user_input[CONF_AIRCO_ID]
                # Before registering: that takes one of four account slots, never freed.
                await self.async_set_unique_id(airco_id.lower())
                self._abort_if_unique_id_configured()
                try:
                    await self._async_register(repository, airco_id)
                except Exception as error:  # noqa: BLE001
                    errors[CONF_BASE] = self._form_error(error)
                else:
                    # The last four characters match the label on the module.
                    return self.async_create_entry(
                        title=f"WF-RAC {airco_id[-4:]}", data=user_input
                    )

        return self.async_show_form(
            step_id=step_id,
            data_schema=build_schema(),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device discovered by zeroconf."""
        description_placeholders = {
            "id": self._discovery_info[CONF_AIRCO_ID],
            "host": self._discovery_info[CONF_HOST],
            "port": self._discovery_info[CONF_PORT],
        }

        if user_input:
            user_input[CONF_HOST] = self._discovery_info[CONF_HOST]
            user_input.setdefault(CONF_PORT, self._discovery_info[CONF_PORT])

        def build_schema() -> probatio.Schema:
            # After a fallback, a cleared field must land on the port that answered.
            port = (user_input or self._discovery_info)[CONF_PORT]
            return self.add_suggested_values_to_schema(
                probatio.Schema(
                    {probatio.Optional(CONF_PORT, default=port): probatio.Port()}
                ),
                user_input,
            )

        return await self._async_create_common(
            step_id="discovery_confirm",
            build_schema=build_schema,
            user_input=user_input,
            description_placeholders=description_placeholders,
            # A port edited in the form is not second-guessed.
            allow_port_fallback=not user_input
            or user_input[CONF_PORT] == self._discovery_info[CONF_PORT],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding device manually."""

        def build_schema() -> probatio.Schema:
            return self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): cv.string,
                        probatio.Optional(
                            CONF_PORT, default=DEFAULT_PORT
                        ): probatio.Port(),
                    }
                ),
                user_input,
            )

        if user_input:
            # Before any registration: that spends one of the four slots.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        return await self._async_create_common(
            step_id="user", build_schema=build_schema, user_input=user_input
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # DNS is case-insensitive; lower case first so the suffix is stripped.
        local_name = discovery_info.hostname.rstrip(".").lower()
        node_name = local_name.removesuffix(".local")
        host = discovery_info.host
        # An announcement without a port is still this module.
        port = discovery_info.port or DEFAULT_PORT

        _LOGGER.debug(
            "zeroconf discovery: hostname=%r, host=%r, port=%r",
            discovery_info.hostname,
            discovery_info.host,
            discovery_info.port,
        )

        # Lower case on both sides: this id comes from the hostname.
        await self.async_set_unique_id(node_name)
        # Update the address only; announced ports can be wrong.
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._async_abort_entries_match({CONF_HOST: host})

        info = {CONF_HOST: host, CONF_PORT: port}
        info[CONF_AIRCO_ID] = node_name
        self._discovery_info = info
        self.context["title_placeholders"] = {"name": f"WF-RAC {node_name[-4:]}"}

        return await self.async_step_discovery_confirm()


class KnownError(Exception):
    """Base class for flow errors; error_name is the form error key."""

    error_name = "unknown"


class CannotConnect(KnownError):
    """Error to indicate we cannot connect."""

    error_name = "cannot_connect"


class TooManyDevicesRegistered(KnownError):
    """Error to indicate that there are too many devices registered."""

    error_name = "too_many_devices_registered"
