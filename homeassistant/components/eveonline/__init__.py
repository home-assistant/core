"""The Eve Online integration."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any

from eveonline import EveOnlineClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, SCOPES
from .coordinator import EveOnlineConfigEntry, EveOnlineCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Set up Eve Online from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    auth = AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    client = EveOnlineClient(auth=auth)

    character_id: int = entry.data["character_id"]
    character_name: str = entry.data["character_name"]

    coordinator = EveOnlineCoordinator(
        hass, entry, client, character_id, character_name
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Check if the granted OAuth scopes cover all required scopes.
    _check_scopes(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Release server entity ownership so another entry can claim it on reload.
    if unload_ok:
        if domain_data := hass.data.get(DOMAIN):
            if domain_data.get("server_sensor_entry") == entry.entry_id:
                domain_data.pop("server_sensor_entry")

    return unload_ok


def _get_token_scopes(token_data: dict[str, Any]) -> set[str]:
    """Extract granted scopes from the Eve SSO JWT access token.

    Eve SSO access tokens are JWTs containing a ``scp`` claim with the
    granted scopes as either a single string or a list of strings.
    Returns an empty set when the token cannot be parsed.
    """
    access_token = token_data.get("access_token", "")
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return set()
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        scp = decoded.get("scp", [])
        if isinstance(scp, str):
            return {scp}
        return set(scp)
    except ValueError, binascii.Error:
        return set()


def _check_scopes(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> None:
    """Create a repair issue when required OAuth scopes are missing.

    If the granted scopes cannot be determined (e.g. the token is not a
    valid JWT), the check is skipped to avoid false positives.
    """
    granted_scopes = _get_token_scopes(entry.data.get("token", {}))
    if not granted_scopes:
        # Cannot determine scopes; skip check.
        return

    required_scopes = set(SCOPES)
    missing_scopes = required_scopes - granted_scopes
    issue_id = f"missing_scopes_{entry.entry_id}"

    if missing_scopes:
        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key="missing_scopes",
            translation_placeholders={
                "character": entry.title,
                "scopes": ", ".join(sorted(missing_scopes)),
            },
            data={
                "entry_id": entry.entry_id,
                "scopes": ", ".join(sorted(missing_scopes)),
            },
        )
    else:
        from homeassistant.helpers.issue_registry import (  # noqa: PLC0415
            async_delete_issue,
        )

        async_delete_issue(hass, DOMAIN, issue_id)
