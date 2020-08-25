"""Config flow for sia integration."""
from pysiaalarm import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT

from .const import (
    ABORT_ALREADY_CONFIGURED,
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DEFAULT_NAME,
    DOMAIN,
)

HUB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): int,
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_ENCRYPTION_KEY, None): str,
        vol.Required(CONF_PING_INTERVAL): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_ENCRYPTION_KEY, None): str,
        vol.Required(CONF_PING_INTERVAL): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)


def validate_input(data: dict) -> dict:
    """Validate the input by the user."""
    errors = {}
    if data:
        try:
            SIAAccount(data[CONF_ACCOUNT], data.get(CONF_ENCRYPTION_KEY))
        except InvalidKeyFormatError:
            errors["base"] = "invalid_key_format"
        except InvalidKeyLengthError:
            errors["base"] = "invalid_key_length"
        except InvalidAccountFormatError:
            errors["base"] = "invalid_account_format"
        except InvalidAccountLengthError:
            errors["base"] = "invalid_account_length"
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "unknown"

        if not 1 <= int(data[CONF_PING_INTERVAL]) <= 1440:
            errors["base"] = "invalid_ping"
        if int(data[CONF_ZONES]) <= 0:
            errors["base"] = "invalid_zones"
    return errors


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
            return self.async_show_form(
                step_id="additional_account", data_schema=ACCOUNT_SCHEMA, errors=errors
            )

        # parse the user_input and store in self.data
        add_data = user_input.copy()
        add_data.pop(CONF_ADDITIONAL_ACCOUNTS)
        self.data[CONF_ACCOUNTS].append(add_data)

        # call additional accounts if necessary
        if user_input[CONF_ADDITIONAL_ACCOUNTS]:
            return self.async_show_form(
                step_id="additional_account", data_schema=ACCOUNT_SCHEMA, errors=errors
            )

        # done
        return self.async_create_entry(
            title=f"SIA Alarm on port {self.data[CONF_PORT]}", data=self.data
        )

    async def async_step_user(self, user_input: dict = None):
        """Handle the initial step."""
        errors = validate_input(user_input)
        if not user_input or errors:
            return self.async_show_form(
                step_id="user", data_schema=HUB_SCHEMA, errors=errors
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
            return self.async_show_form(
                step_id="additional_account", data_schema=ACCOUNT_SCHEMA, errors=errors
            )

        # done
        return self.async_create_entry(
            title=f"SIA Alarm on port {self.data[CONF_PORT]}", data=self.data
        )
