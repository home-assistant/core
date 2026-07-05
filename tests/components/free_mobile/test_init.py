"""Tests for the Free Mobile integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_send_sms() -> Generator[MagicMock]:
    """Mock the Free Mobile SMS client."""
    with patch("freesms.FreeClient.send_sms") as mock_send_sms:
        yield mock_send_sms


@pytest.fixture
def mock_free_client() -> Generator[MagicMock]:
    """Mock the FreeClient constructor to capture its arguments."""
    with patch(
        "homeassistant.components.free_mobile.notify.FreeClient"
    ) as mock_free_client:
        yield mock_free_client


async def test_entry_setup_unload(hass: HomeAssistant) -> None:
    """Test integration setup and unload."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_removes_notify_service(hass: HomeAssistant) -> None:
    """Test unloading an entry removes its own notify service.

    The legacy notify platform skips re-registering a service that already
    exists, so unloading must remove it explicitly for a subsequent reload
    (e.g. after reconfigure/reauth) to pick up fresh data such as a new
    access token.
    """
    entry = MockConfigEntry(domain=DOMAIN, title="Maman", data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(NOTIFY_DOMAIN, "maman")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "maman")


async def test_reconfigure_reloads_with_new_token(
    hass: HomeAssistant, mock_free_client: MagicMock
) -> None:
    """Test the new access token is used to build the client without a restart."""
    entry = MockConfigEntry(domain=DOMAIN, title="Maman", data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_free_client.assert_called_with(
        MOCK_CONFIG[CONF_USERNAME], MOCK_CONFIG[CONF_ACCESS_TOKEN]
    )

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == {**MOCK_CONFIG, CONF_ACCESS_TOKEN: "new-token"}
    mock_free_client.assert_called_with(MOCK_CONFIG[CONF_USERNAME], "new-token")


async def test_import(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Test yaml import creates an entry and the deprecation issue."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "notifier_name",
                    **MOCK_CONFIG,
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(entries := hass.config_entries.async_entries(DOMAIN)) == 1
    assert entries[0].title == "notifier_name"
    assert entries[0].data == MOCK_CONFIG

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


async def test_import_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test yaml import aborts if already configured, but still warns."""
    MockConfigEntry(
        domain=DOMAIN,
        title="notifier_name",
        data=MOCK_CONFIG,
    ).add_to_hass(hass)

    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "notifier_name",
                    **MOCK_CONFIG,
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )
