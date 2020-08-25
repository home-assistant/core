"""Config flow for sia integration."""
import logging

from pysiaalarm import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT

from .const import (  # pylint: disable=unused-import
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DEFAULT_NAME,
    DOMAIN,
    INVALID_ACCOUNT_FORMAT,
    INVALID_ACCOUNT_LENGTH,
    INVALID_KEY_FORMAT,
    INVALID_KEY_LENGTH,
    INVALID_PING,
    INVALID_ZONES,
)

_LOGGER = logging.getLogger(__name__)


def validate_input(data: dict) -> dict:
    """Validate the input by the user."""
    errors = {}
    if data:
        try:
            SIAAccount(data[CONF_ACCOUNT], data.get(CONF_ENCRYPTION_KEY))
        except InvalidKeyFormatError:
            errors["base"] = INVALID_KEY_FORMAT
        except InvalidKeyLengthError:
            errors["base"] = INVALID_KEY_LENGTH
        except InvalidAccountFormatError:
            errors["base"] = INVALID_ACCOUNT_FORMAT
        except InvalidAccountLengthError:
            errors["base"] = INVALID_ACCOUNT_LENGTH
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "unknown"

        if not 1 <= int(data[CONF_PING_INTERVAL]) <= 1440:
            errors["base"] = INVALID_PING
        if int(data[CONF_ZONES]) <= 0:
            errors["base"] = INVALID_ZONES
    return errors


def create_schema(step_id: str, user_input: dict, errors: dict) -> vol.Schema:
    """Create a schema for the next or first form, using the errors to delete erroneous input, but filling the other fields."""
    port_sch = vol.Required(CONF_PORT)
    account_sch = vol.Required(CONF_ACCOUNT)
    encryption_sch = vol.Optional(CONF_ENCRYPTION_KEY)
    ping_sch = vol.Required(CONF_PING_INTERVAL, default=1)
    zones_sch = vol.Required(CONF_ZONES, default=1)
    additional_sch = vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False)

    if user_input:
        if not errors:
            errors = {"base": None}

        if step_id == "user":
            port_sch.default = vol.default_factory(user_input[CONF_PORT])
        if not errors["base"] in [INVALID_ACCOUNT_FORMAT, INVALID_ACCOUNT_LENGTH]:
            account_sch.default = vol.default_factory(user_input[CONF_ACCOUNT])
        if (
            not errors["base"] in [INVALID_KEY_FORMAT, INVALID_KEY_LENGTH]
            and user_input.get(CONF_ENCRYPTION_KEY, None) is not None
        ):
            encryption_sch.default = vol.default_factory(
                user_input[CONF_ENCRYPTION_KEY]
            )
        if errors["base"] != INVALID_PING:
            ping_sch.default = vol.default_factory(user_input[CONF_PING_INTERVAL])
        if errors["base"] != INVALID_ZONES:
            zones_sch.default = vol.default_factory(user_input[CONF_ZONES])

    if step_id == "user":
        return vol.Schema(
            {
                port_sch: int,
                account_sch: str,
                encryption_sch: str,
                ping_sch: int,
                zones_sch: int,
                additional_sch: bool,
            }
        )
    return vol.Schema(
        {
            account_sch: str,
            encryption_sch: str,
            ping_sch: int,
            zones_sch: int,
            additional_sch: bool,
        }
    )


class SIAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sia."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    data = {}

    async def async_step_additional_account(self, user_input: dict = None):
        """Handle the additional account step."""
        errors = validate_input(user_input)
        # validate and return with error
        if not user_input or errors:
            schema = create_schema("additional_account", user_input, errors)
            return self.async_show_form(
                step_id="additional_account", data_schema=schema, errors=errors,
            )

        # parse the user_input and store in self.data
        add_data = user_input.copy()
        add_data.pop(CONF_ADDITIONAL_ACCOUNTS)
        self.data[CONF_ACCOUNTS].append(add_data)

        # call additional accounts if necessary
        if user_input[CONF_ADDITIONAL_ACCOUNTS]:
            return await self.async_step_additional_account()
        # done
        return self.async_create_entry(
            title=f"SIA Alarm on port {self.data[CONF_PORT]}", data=self.data
        )

    async def async_step_user(self, user_input: dict = None):
        """Handle the initial step."""
        errors = validate_input(user_input)
        if not user_input or errors:
            schema = create_schema("user", user_input, errors)
            return self.async_show_form(
                step_id="user", data_schema=schema, errors=errors,
            )

        # check uniqueness of the setup
        await self.async_set_unique_id(user_input[CONF_PORT])
        self._abort_if_unique_id_configured()

        # parse the user_input and store in self.data
        self.data = {
            CONF_PORT: user_input[CONF_PORT],
            CONF_ACCOUNTS: [
                {
                    CONF_ACCOUNT: user_input[CONF_ACCOUNT],
                    CONF_ENCRYPTION_KEY: user_input.get(CONF_ENCRYPTION_KEY),
                    CONF_PING_INTERVAL: user_input[CONF_PING_INTERVAL],
                    CONF_ZONES: user_input[CONF_ZONES],
                }
            ],
        }

        # call additional accounts if necessary
        if user_input[CONF_ADDITIONAL_ACCOUNTS]:
            return await self.async_step_additional_account()

        # done
        return self.async_create_entry(
            title=f"SIA Alarm on port {self.data[CONF_PORT]}", data=self.data
        )
