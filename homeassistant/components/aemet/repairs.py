"""Repairs for the AEMET OpenData integration."""

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import API_KEY_EXPIRATION_WARNING_DAYS, API_KEY_URL, DOMAIN
from .util import API_KEY_SCHEMA, async_validate_api_key, get_api_key_expiration

ISSUE_API_KEY_EXPIRING = "api_key_expiring"


def _issue_id(entry: ConfigEntry) -> str:
    """Return the repair issue ID for an entry."""
    return f"{ISSUE_API_KEY_EXPIRING}_{entry.entry_id}"


@callback
def async_delete_api_key_expiration_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Delete the API key expiration repair issue for an entry."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))


@callback
def _async_create_api_key_expiration_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    expiration: datetime,
    _now: datetime | None = None,
) -> None:
    """Create the API key expiration repair issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry),
        is_fixable=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_API_KEY_EXPIRING,
        translation_placeholders={
            "name": entry.title,
            "expiration_date": dt_util.as_local(expiration).date().isoformat(),
        },
        config_entry_id=entry.entry_id,
        data={"entry_id": entry.entry_id},
    )


@callback
def async_schedule_api_key_expiration_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> Callable[[], None] | None:
    """Schedule the API key expiration repair issue.

    Return a callback that cancels the scheduled callback, if any.
    """
    async_delete_api_key_expiration_issue(hass, entry)

    api_key = entry.data.get(CONF_API_KEY)
    if not isinstance(api_key, str):
        return None

    expiration = get_api_key_expiration(api_key)
    if expiration is None:
        return None

    warning_start = expiration - timedelta(days=API_KEY_EXPIRATION_WARNING_DAYS)
    if dt_util.utcnow() >= warning_start:
        _async_create_api_key_expiration_issue(hass, entry, expiration)
        return None

    return async_track_point_in_utc_time(
        hass,
        partial(_async_create_api_key_expiration_issue, hass, entry, expiration),
        warning_start,
    )


class AemetApiKeyExpiringRepairFlow(RepairsFlow):
    """Repair flow for an expiring AEMET API key."""

    def __init__(self, entry_id: str, issue_id: str) -> None:
        """Initialize the repair flow."""
        self._entry_id = entry_id
        self._issue_id = issue_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the repair flow."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_known_entry(self._entry_id)

        if user_input is not None:
            error = await async_validate_api_key(
                self.hass,
                user_input[CONF_API_KEY],
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
            )
            if error is not None:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for an AEMET repair issue."""
    if not issue_id.startswith(ISSUE_API_KEY_EXPIRING) or not data:
        raise ValueError(f"Unknown repair issue {issue_id}")

    entry_id = data.get("entry_id")
    if not isinstance(entry_id, str):
        raise TypeError(f"Invalid entry ID for repair issue {issue_id}")

    return AemetApiKeyExpiringRepairFlow(entry_id, issue_id)
