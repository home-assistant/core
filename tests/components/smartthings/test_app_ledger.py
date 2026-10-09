"""Tests for the SmartThings app ledger."""

from typing import Any
from unittest.mock import AsyncMock

from pysmartthings import SmartThingsConnectionError, SmartThingsNotFoundError
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.smartthings.app_ledger import (
    STORAGE_KEY,
    async_get_app_ledger,
)
from homeassistant.components.smartthings.const import (
    CONF_APP_ID,
    DOMAIN,
    app_auth_domain,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_record_and_forget(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test recording and forgetting app ids persists correctly."""
    ledger = await async_get_app_ledger(hass)

    await ledger.async_record("app-1")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1"]

    # Recording the same id again is a no-op, not a duplicate.
    await ledger.async_record("app-1")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1"]

    await ledger.async_record("app-2")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1", "app-2"]

    await ledger.async_forget("app-1")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-2"]

    # Forgetting an id that isn't there is a no-op, not an error.
    await ledger.async_forget("does-not-exist")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-2"]


async def test_get_app_ledger_is_a_singleton(hass: HomeAssistant) -> None:
    """Test the same ledger instance is returned for a given hass."""
    ledger1 = await async_get_app_ledger(hass)
    ledger2 = await async_get_app_ledger(hass)
    assert ledger1 is ledger2


@pytest.mark.usefixtures("mock_smartthings")
async def test_reconcile_deletes_orphaned_apps(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
) -> None:
    """Test reconcile deletes app ids with no matching live config entry."""
    live_entry = MockConfigEntry(domain=DOMAIN, data={CONF_APP_ID: "live-app"})
    live_entry.add_to_hass(hass)

    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("live-app")
    await ledger.async_record("orphaned-app")

    await ledger.async_reconcile(mock_smartthings)

    mock_smartthings.delete_app.assert_called_once_with("orphaned-app")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["live-app"]


@pytest.mark.usefixtures("mock_smartthings")
async def test_reconcile_no_orphans_does_not_call_delete(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
) -> None:
    """Test reconcile is a no-op when every ledgered id has a live entry."""
    live_entry = MockConfigEntry(domain=DOMAIN, data={CONF_APP_ID: "live-app"})
    live_entry.add_to_hass(hass)

    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("live-app")

    await ledger.async_reconcile(mock_smartthings)

    mock_smartthings.delete_app.assert_not_called()


@pytest.mark.usefixtures("mock_smartthings")
async def test_reconcile_already_deleted_is_forgotten(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
) -> None:
    """Test an already-gone app is dropped from the ledger, not retried forever."""
    mock_smartthings.delete_app.side_effect = SmartThingsNotFoundError

    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("already-gone")

    await ledger.async_reconcile(mock_smartthings)

    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == []


@pytest.mark.usefixtures("mock_smartthings")
async def test_reconcile_skips_kept_credential(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
) -> None:
    """Test reconcile leaves an orphaned app alone if its credential is kept.

    Mirrors choosing "Keep" in the Application Credentials removal dialog --
    the app is never deleted while its credential survives, so the config
    flow can offer it back for reuse later.
    """
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("kept-client-id", "kept-client-secret"),
        auth_domain=app_auth_domain("kept-app"),
    )

    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("kept-app")

    await ledger.async_reconcile(mock_smartthings)

    mock_smartthings.delete_app.assert_not_called()
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["kept-app"]


@pytest.mark.usefixtures("mock_smartthings")
async def test_reconcile_connection_error_retries_later(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
) -> None:
    """Test a transient failure leaves the id in the ledger for a later attempt."""
    mock_smartthings.delete_app.side_effect = SmartThingsConnectionError

    ledger = await async_get_app_ledger(hass)
    await ledger.async_record("orphaned-app")

    await ledger.async_reconcile(mock_smartthings)

    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["orphaned-app"]
