"""Diagnostics support for the Mastodon integration."""

from __future__ import annotations

from typing import Any

from mastodon.Mastodon import Account, Instance, InstanceV2, MastodonNotFoundError

from homeassistant.core import HomeAssistant

from .coordinator import MastodonConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MastodonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    instance, account = await hass.async_add_executor_job(
        get_diagnostics,
        config_entry,
    )

    return {
        "instance": instance,
        "account": account,
    }


def get_diagnostics(
    config_entry: MastodonConfigEntry,
) -> tuple[InstanceV2 | Instance, Account]:
    """Get mastodon diagnostics."""
    client = config_entry.runtime_data.client

    try:
        instance = client.instance_v2()
    except MastodonNotFoundError:
        instance = client.instance_v1()
    account = client.account_verify_credentials()

    return instance, account
