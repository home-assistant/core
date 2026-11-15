"""Config flow for the Bambu Lab integration."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, override

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabClient,
    BambuLabConnectionError,
    BambuLabSerialMismatchError,
    DiscoveredPrinter,
    discover,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ACCESS_CODE, CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

ACCESS_CODE_SCHEMA = {
    probatio.Required(probatio.Secret(CONF_ACCESS_CODE)): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
}

STEP_ACCESS_CODE_DATA_SCHEMA = probatio.Schema(ACCESS_CODE_SCHEMA)

STEP_MANUAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_SERIAL_NUMBER): TextSelector(),
        **ACCESS_CODE_SCHEMA,
    }
)


class BambuLabConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bambu Lab."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_task: asyncio.Task[dict[str, DiscoveredPrinter]] | None = None
        self._printers: dict[str, DiscoveredPrinter] = {}
        self._printer: DiscoveredPrinter | None = None
        self._no_printers_found = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask how to find the printer."""
        return self.async_show_menu(step_id="user", menu_options=["discover", "manual"])

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Look for printers on the network."""
        if (task := self._discovery_task) is None or not task.done():
            if task is None:
                task = self.hass.async_create_task(self._async_discover())
                self._discovery_task = task
            return self.async_show_progress(
                step_id="discover",
                progress_action="discover",
                progress_task=task,
            )

        self._printers = task.result()
        self._discovery_task = None
        if not self._printers:
            self._no_printers_found = True
            return self.async_show_progress_done(next_step_id="manual")
        if len(self._printers) == 1:
            (self._printer,) = self._printers.values()
            return self.async_show_progress_done(next_step_id="access_code")
        return self.async_show_progress_done(next_step_id="pick_printer")

    async def _async_discover(self) -> dict[str, DiscoveredPrinter]:
        """Return the printers on the network that are not set up yet."""
        try:
            printers = await discover()
        except BambuLabConnectionError:
            return {}
        configured = self._async_current_ids()
        return {
            printer.serial: printer
            for printer in printers
            if printer.serial not in configured
        }

    async def async_step_pick_printer(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which of the printers to set up."""
        if user_input is not None:
            self._printer = self._printers[user_input[CONF_SERIAL_NUMBER]]
            return await self.async_step_access_code()

        return self.async_show_form(
            step_id="pick_printer",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_SERIAL_NUMBER): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=printer.serial,
                                    label=f"{_name(printer)} ({printer.host})",
                                )
                                for printer in self._printers.values()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_access_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the access code of a printer that was found."""
        if TYPE_CHECKING:
            assert self._printer is not None
        printer = self._printer
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BambuLabClient(
                printer.host, printer.serial, user_input[CONF_ACCESS_CODE]
            )
            if (error := await self._async_connect(client)) is None:
                return await self._async_create_entry(
                    client, printer.host, user_input[CONF_ACCESS_CODE]
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="access_code",
            data_schema=STEP_ACCESS_CODE_DATA_SCHEMA,
            description_placeholders={"name": _name(printer), "host": printer.host},
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for everything that is needed to connect to a printer."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BambuLabClient(
                user_input[CONF_HOST],
                user_input[CONF_SERIAL_NUMBER],
                user_input[CONF_ACCESS_CODE],
            )
            if (error := await self._async_connect(client)) is None:
                return await self._async_create_entry(
                    client, user_input[CONF_HOST], user_input[CONF_ACCESS_CODE]
                )
            errors["base"] = error
        elif self._no_printers_found:
            errors["base"] = "no_printers_found"

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_MANUAL_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def _async_connect(self, client: BambuLabClient) -> str | None:
        """Connect to the printer to verify it, and return what went wrong."""
        try:
            await client.connect()
        except BambuLabAuthenticationError:
            return "invalid_auth"
        except BambuLabSerialMismatchError:
            return "serial_number_mismatch"
        except BambuLabCertificateError:
            return "untrusted_certificate"
        except BambuLabConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        await client.disconnect()
        return None

    async def _async_create_entry(
        self, client: BambuLabClient, host: str, access_code: str
    ) -> ConfigFlowResult:
        """Create the config entry of a printer that was verified."""
        await self.async_set_unique_id(client.serial, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=client.info.model_name or client.serial,
            data={
                CONF_HOST: host,
                CONF_SERIAL_NUMBER: client.serial,
                CONF_ACCESS_CODE: access_code,
            },
        )


def _name(printer: DiscoveredPrinter) -> str:
    """Return the name to show for a printer that was found."""
    return printer.name or printer.serial
