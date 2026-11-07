"""Tests for the SmartThings app ledger."""

from typing import Any

import pytest

from homeassistant.components.smartthings.app_ledger import (
    STORAGE_KEY,
    async_get_app_ledger,
)
from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.core import HomeAssistant

REDIRECT_URI = "https://example.com/auth/external/callback"
OTHER_REDIRECT_URI = "https://other.example.com/auth/external/callback"


async def test_record(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test recording app ids persists correctly."""
    ledger = await async_get_app_ledger(hass)

    await ledger.async_record("app-1", REDIRECT_URI)
    assert hass_storage[STORAGE_KEY]["data"]["apps"] == {"app-1": REDIRECT_URI}

    await ledger.async_record("app-2", REDIRECT_URI)
    assert hass_storage[STORAGE_KEY]["data"]["apps"] == {
        "app-1": REDIRECT_URI,
        "app-2": REDIRECT_URI,
    }

    await ledger.async_record("app-1", OTHER_REDIRECT_URI)
    assert hass_storage[STORAGE_KEY]["data"]["apps"] == {
        "app-1": OTHER_REDIRECT_URI,
        "app-2": REDIRECT_URI,
    }


@pytest.mark.parametrize(
    ("app_id", "redirect_uri", "expected"),
    [
        pytest.param("app-1", REDIRECT_URI, True, id="owned"),
        pytest.param("app-2", REDIRECT_URI, False, id="not_owned"),
        pytest.param("app-1", OTHER_REDIRECT_URI, False, id="redirect_uri_changed"),
    ],
)
async def test_is_reusable(
    hass: HomeAssistant, app_id: str, redirect_uri: str, expected: bool
) -> None:
    """Test only apps provisioned for the current redirect URI are reusable."""
    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("app-1", REDIRECT_URI)

    assert ledger.is_reusable(app_id, redirect_uri) is expected


async def test_migrate_app_ids(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test app ids from the first storage format are migrated as not reusable."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"app_ids": ["app-1"]},
    }

    ledger = await async_get_app_ledger(hass)

    assert ledger.is_provisioned_auth_domain(f"{DOMAIN}_app-1")
    assert not ledger.is_reusable("app-1", REDIRECT_URI)


async def test_get_app_ledger_is_a_singleton(hass: HomeAssistant) -> None:
    """Test the same ledger instance is returned for a given hass."""
    ledger1 = await async_get_app_ledger(hass)
    ledger2 = await async_get_app_ledger(hass)
    assert ledger1 is ledger2
