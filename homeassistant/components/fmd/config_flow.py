"""Config flow for the FMD integration."""

import logging
from typing import Any, override

from fmd_api import AuthenticationError, FmdApiException, FmdClient
import probatio
from yarl import URL

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
        probatio.Required(CONF_ID): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


def _canonical_url(url: str) -> str | None:
    """Normalize a server URL for identity purposes.

    yarl lowercases the scheme/host and drops default ports, so spelling
    variants (https://FMD.EXAMPLE.COM:443 == https://fmd.example.com)
    produce one identity. Query strings and fragments are dropped: they
    are never sent to the server but would otherwise split one server
    across multiple entry identities. Returns None for input the identity
    must never carry: non-HTTP(S) schemes, URLs with embedded credentials
    (userinfo would otherwise be persisted in entry, entity, and device
    registry identifiers), or unparsable/non-absolute URLs.
    """
    try:
        parsed = URL(url)
    except ValueError:
        return None
    if (
        not parsed.is_absolute()
        or parsed.scheme not in ("http", "https")
        or parsed.user is not None
    ):
        return None
    return str(parsed.with_query(None).with_fragment(None)).rstrip("/")


async def validate_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials and return auth artifacts for the config entry."""
    api = await FmdClient.create(
        user_input[CONF_URL], user_input[CONF_ID], user_input[CONF_PASSWORD]
    )
    try:
        locations = await api.get_locations(1)
        if not [loc for loc in locations if loc]:
            _LOGGER.debug("No locations returned during validation")
        artifacts = await api.export_auth_artifacts()
    finally:
        await api.close()
    return dict(artifacts)


class FMDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FMD."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            canonical_url = _canonical_url(user_input[CONF_URL])
            if canonical_url is None:
                errors[CONF_URL] = "invalid_url"
            else:
                # Canonical URL once: entry unique_id, stored data, and
                # derived entity/device identities must all agree.
                user_input[CONF_URL] = canonical_url
                # Account IDs are scoped per server.
                server_url = user_input[CONF_URL]
                await self.async_set_unique_id(f"{server_url}/{user_input[CONF_ID]}")
                self._abort_if_unique_id_configured()
                try:
                    artifacts = await validate_input(user_input)
                except AuthenticationError:
                    errors["base"] = "invalid_auth"
                except FmdApiException:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error connecting to FMD server")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_ID],
                        data={
                            CONF_URL: user_input[CONF_URL],
                            CONF_ID: user_input[CONF_ID],
                            "artifacts": artifacts,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )
