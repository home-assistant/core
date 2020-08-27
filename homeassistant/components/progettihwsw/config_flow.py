"""Config flow for ProgettiHWSW Automation integration."""

from ProgettiHWSW.ProgettiHWSWAPI import ProgettiHWSWAPI
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required("host"): str})


class EntryValidator:
    """Class to validate data given by user."""

    def __init__(self, host):
        """Initialize the data."""
        self._host = host
        self._phwsw_instance = ProgettiHWSWAPI(host)

    async def check_board_validity(self, hass):
        """Check that if board actually exists. If it does, return the specs of that board."""
        return await hass.async_add_executor_job(self._phwsw_instance.check_board)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user host input."""

    validity_checker = EntryValidator(data["host"])
    is_valid = await validity_checker.check_board_validity(hass)

    if is_valid is False:
        raise UnexistingBoard

    return {
        "title": is_valid["title"],
        "relay_count": is_valid["relay_count"],
        "input_count": is_valid["input_count"],
        "is_old": is_valid["is_old"],
    }


async def validate_input_relay_modes(data):
    """Validate the user input in relay modes form."""
    for name, mode in data.items():
        if mode != "bistable" and mode != "monostable":
            raise WrongInfo

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ProgettiHWSW Automation."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_relay_modes(self, user_input=None):
        """Manage relay modes step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input_relay_modes(user_input)
                whole_data = user_input
                whole_data.update(self.step_user_user_input)

                return self.async_create_entry(
                    title=whole_data["title"], data=whole_data
                )
            except WrongInfo:
                errors["base"] = "wrong_info_relay_modes"
            except Exception:
                errors["base"] = "unknown"

        relay_modes_schema = {}
        for i in range(1, int(self.step_user_user_input["relay_count"]) + 1):
            relay_modes_schema[
                vol.Required(f"relay_{str(i)}", default="bistable")
            ] = str

        return self.async_show_form(
            step_id="relay_modes",
            data_schema=vol.Schema(relay_modes_schema),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                user_input.update(info)
                self.step_user_user_input = user_input
                return await self.async_step_relay_modes()
            except UnexistingBoard:
                errors["base"] = "unexisting_board"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class UnexistingBoard(exceptions.HomeAssistantError):
    """Error to indicate we cannot identify host."""


class WrongInfo(exceptions.HomeAssistantError):
    """Error to indicate we cannot validate relay modes input."""
