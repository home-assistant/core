"""Config flow for ProgettiHWSW Automation integration."""

from typing import TYPE_CHECKING, Any

from ProgettiHWSW.ProgettiHWSWAPI import ProgettiHWSWAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Required("host"): str, vol.Required("port", default=80): int}
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user host input."""

    api_instance = ProgettiHWSWAPI(f"{data['host']}:{data['port']}")
    is_valid = await api_instance.check_board()

    if not is_valid:
        raise CannotConnect

    return {
        "title": is_valid["title"],
        "relay_count": is_valid["relay_count"],
        "input_count": is_valid["input_count"],
        "is_old": is_valid["is_old"],
    }


class ProgettiHWSWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ProgettiHWSW Automation."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize class variables."""
        self.s1_in: dict[str, Any] | None = None

    async def async_step_relay_modes(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Manage relay modes step."""
        errors: dict[str, str] = {}
        if TYPE_CHECKING:
            assert self.s1_in is not None
        if user_input is not None:
            whole_data = user_input
            whole_data.update(self.s1_in)

            return self.async_create_entry(title=whole_data["title"], data=whole_data)

        relay_modes_schema = {}
        for i in range(1, int(self.s1_in["relay_count"]) + 1):
            relay_modes_schema[vol.Required(f"relay_{i!s}", default="bistable")] = (
                vol.In(
                    {
                        "bistable": "Bistable (ON/OFF Mode)",
                        "monostable": "Monostable (Timer Mode)",
                    }
                )
            )

        return self.async_show_form(
            step_id="relay_modes",
            data_schema=vol.Schema(relay_modes_schema),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {"host": user_input["host"], "port": user_input["port"]}
            )

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                user_input.update(info)
                self.s1_in = user_input
                return await self.async_step_relay_modes()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot identify host."""


class WrongInfo(HomeAssistantError):
    """Error to indicate we cannot validate relay modes input."""


class ExistingEntry(HomeAssistantError):
    """Error to indicate we cannot validate relay modes input."""
