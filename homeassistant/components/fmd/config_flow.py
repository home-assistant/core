"""Config flow for FMD integration."""

import logging
from typing import Any

from fmd_api import FmdClient
import probatio

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_USE_IMPERIAL, DEFAULT_POLLING_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def authenticate_and_get_artifacts(
    url: str, fmd_id: str, password: str
) -> dict[str, Any]:
    """Create FMD API instance, validate connection, and export auth artifacts.

    Returns auth artifacts dictionary that can be used for password-free resume.
    """
    api = await FmdClient.create(url, fmd_id, password, drop_password=True)

    # Validate connection by fetching one location
    locations = await api.get_locations(1)
    locations = [loc for loc in locations if loc]

    # Export authentication artifacts (password-free)
    artifacts = await api.export_auth_artifacts()

    # Close the temporary client (caller will recreate from artifacts)
    await api.close()

    return artifacts


def _normalize_artifacts(artifacts: Any) -> dict[str, Any]:
    """Ensure artifacts are stored as a plain serializable dict.

    Some tests or callers may pass in MagicMock/dict-like objects that implement
    only `.get`. Home Assistant persists config entry data to JSON; ensure we
    convert any mapping-like object into a real dict with expected keys to avoid
    serialization errors (e.g., TypeError on MagicMock).
    """
    if isinstance(artifacts, dict):
        return artifacts

    # Best-effort extraction using .get for known keys returned by FMD API
    required_keys = (
        "base_url",
        "fmd_id",
        "access_token",
        "private_key",
        "password_hash",
    )
    try:
        get = getattr(artifacts, "get", None)
        if callable(get):
            return {k: get(k, None) for k in required_keys}
    except Exception:  # noqa: BLE001  # pragma: no cover - defensive
        pass

    # Fallback: try to coerce via dict() for mapping types
    try:
        return dict(artifacts)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001  # pragma: no cover - defensive
        _LOGGER.debug("Unable to normalize artifacts of type %s", type(artifacts))
        return {}


class FMDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FMD."""

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with new credentials."""
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        entry_data = entry.data if entry else {}

        if user_input is not None:
            try:
                # Authenticate and get artifacts (password-free storage)
                artifacts = await authenticate_and_get_artifacts(
                    user_input["url"],
                    user_input["id"],
                    user_input["password"],
                )

                artifacts = _normalize_artifacts(artifacts)

                # Build new entry data with artifacts
                new_data = {
                    "url": user_input["url"],
                    "id": user_input["id"],
                    "artifacts": artifacts,
                    # Preserve other config values
                    "polling_interval": entry_data.get(
                        "polling_interval", DEFAULT_POLLING_INTERVAL
                    ),
                    "allow_inaccurate_locations": entry_data.get(
                        "allow_inaccurate_locations", False
                    ),
                    CONF_USE_IMPERIAL: entry_data.get(CONF_USE_IMPERIAL, False),
                }

                # Update the config entry with new artifacts (password removed)
                if entry:
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                return self.async_abort(reason="reauth_successful")
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

        data_schema = probatio.Schema(
            {
                probatio.Required("url", default=entry_data.get("url", "")): str,
                probatio.Required("id", default=entry_data.get("id", "")): str,
                probatio.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="reauth",
            data_schema=data_schema,
            errors=errors,
        )

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.async_set_unique_id(user_input["id"])
                self._abort_if_unique_id_configured()

                # Authenticate and get artifacts (password-free storage)
                artifacts = await authenticate_and_get_artifacts(
                    user_input["url"],
                    user_input["id"],
                    user_input["password"],
                )

                artifacts = _normalize_artifacts(artifacts)

                # Build entry data with artifacts (no raw password stored)
                entry_data = {
                    "url": user_input["url"],
                    "id": user_input["id"],
                    "artifacts": artifacts,
                    "polling_interval": user_input.get(
                        "polling_interval", DEFAULT_POLLING_INTERVAL
                    ),
                    "allow_inaccurate_locations": user_input.get(
                        "allow_inaccurate_locations", False
                    ),
                    CONF_USE_IMPERIAL: user_input.get(CONF_USE_IMPERIAL, False),
                }

                return self.async_create_entry(title=user_input["id"], data=entry_data)
            except Exception:
                _LOGGER.exception("Failed to connect to FMD server")
                errors["base"] = "cannot_connect"

        data_schema = probatio.Schema(
            {
                probatio.Required("url"): str,
                probatio.Required("id"): str,
                probatio.Required("password"): str,
                probatio.Optional(
                    "polling_interval", default=DEFAULT_POLLING_INTERVAL
                ): int,
                probatio.Optional("allow_inaccurate_locations", default=False): bool,
                probatio.Optional(CONF_USE_IMPERIAL, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )
