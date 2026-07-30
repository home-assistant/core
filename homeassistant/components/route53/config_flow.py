"""Config flow for AWS Route53 integration."""

import logging
from typing import Any, override

import boto3
import botocore.exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Without these, a mistyped zone ID surfaces as an authentication failure
ZONE_ERROR_CODES = {"NoSuchHostedZone", "InvalidInput"}

ERROR_FIELDS = {"invalid_zone": CONF_ZONE}


def _clean_records(value: list[str]) -> list[str]:
    """Strip record names, rejecting a list without any usable entry.

    An empty Changes batch is rejected by Route53, so catch it in the form.
    """
    records = [record.strip() for record in value]
    if not records or not all(records):
        raise vol.Invalid("every record must be non-empty")
    return records


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_ZONE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_DOMAIN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_RECORDS): vol.All(
            TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)),
            _clean_records,
        ),
        vol.Optional(CONF_TTL, default=DEFAULT_TTL): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=86400,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        ),
    }
)


# boto3 blocks twice here: creating the client reads its service model from
# disk, and get_hosted_zone makes a network call. Both need the executor.
def _validate_auth(
    aws_access_key_id: str, aws_secret_access_key: str, zone: str
) -> None:
    """Validate we can access Route53."""
    client = boto3.client(
        "route53",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    # Fetching the hosted zone verifies both the credentials and the zone ID
    client.get_hosted_zone(Id=zone)


class Route53ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Route53."""

    VERSION = 1

    async def _async_validate(self, user_input: dict[str, Any]) -> str | None:
        """Validate the input, returning an error key when it fails."""
        try:
            await self.hass.async_add_executor_job(
                _validate_auth,
                user_input[CONF_ACCESS_KEY_ID],
                user_input[CONF_SECRET_ACCESS_KEY],
                user_input[CONF_ZONE],
            )
        except botocore.exceptions.ClientError as err:
            _LOGGER.error("AWS rejected the request: %s", err)
            if err.response["Error"]["Code"] in ZONE_ERROR_CODES:
                return "invalid_zone"
            return "invalid_auth"
        except botocore.exceptions.BotoCoreError as err:
            _LOGGER.error("Failed to reach AWS: %s", err)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_DOMAIN] = user_input[CONF_DOMAIN].rstrip(".").lower()
            await self.async_set_unique_id(
                f"{user_input[CONF_ZONE]}_{user_input[CONF_DOMAIN]}"
            )
            self._abort_if_unique_id_configured()

            if error := await self._async_validate(user_input):
                errors[ERROR_FIELDS.get(error, "base")] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_DOMAIN], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # The YAML schema accepts blank records, unlike the form schema
        try:
            user_input[CONF_RECORDS] = _clean_records(user_input[CONF_RECORDS])
        except vol.Invalid:
            _LOGGER.error("No usable records in the YAML configuration")
            return self.async_abort(reason="invalid_records")

        user_input[CONF_DOMAIN] = user_input[CONF_DOMAIN].rstrip(".").lower()
        await self.async_set_unique_id(
            f"{user_input[CONF_ZONE]}_{user_input[CONF_DOMAIN]}"
        )
        self._abort_if_unique_id_configured()

        if error := await self._async_validate(user_input):
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=user_input[CONF_DOMAIN],
            data=user_input,
        )
