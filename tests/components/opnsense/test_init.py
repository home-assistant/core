"""Tests for OPNsense integration setup."""

from __future__ import annotations

from unittest import mock

from pyopnsense.exceptions import APIException
import pytest
from requests import RequestException

from homeassistant.components import opnsense
from homeassistant.components.opnsense import CONF_API_SECRET, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_URL: "https://fake-host/api",
    CONF_API_KEY: "fake_key",
    CONF_API_SECRET: "fake_secret",
    CONF_VERIFY_SSL: False,
}


@pytest.fixture(name="mocked_opnsense")
def mocked_opnsense_fixture() -> mock.MagicMock:
    """Mock pyopnsense diagnostics module in OPNsense integration."""
    with mock.patch.object(opnsense, "diagnostics") as mocked_opn:
        yield mocked_opn


@pytest.mark.parametrize("status_code", [401, 403])
async def test_setup_entry_api_auth_error(
    hass: HomeAssistant, mocked_opnsense: mock.MagicMock, status_code: int
) -> None:
    """Test auth API errors raise ConfigEntryAuthFailed during setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    interface_client = mock.MagicMock()
    interface_client.get_arp.side_effect = APIException(
        status_code=status_code, resp_body="Unauthorized"
    )
    mocked_opnsense.InterfaceClient.return_value = interface_client

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_api_non_auth_error(
    hass: HomeAssistant, mocked_opnsense: mock.MagicMock
) -> None:
    """Test non-auth API errors avoid ConfigEntryNotReady retry loops."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    interface_client = mock.MagicMock()
    interface_client.get_arp.side_effect = APIException(
        status_code=500, resp_body="Internal Server Error"
    )
    mocked_opnsense.InterfaceClient.return_value = interface_client

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connectivity_error(
    hass: HomeAssistant, mocked_opnsense: mock.MagicMock
) -> None:
    """Test transient connectivity errors are retried."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    interface_client = mock.MagicMock()
    interface_client.get_arp.side_effect = RequestException("Connection failed")
    mocked_opnsense.InterfaceClient.return_value = interface_client

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_tracker_interface(
    hass: HomeAssistant, mocked_opnsense: mock.MagicMock
) -> None:
    """Test invalid tracker interface is treated as config error (no retry)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ENTRY_CONFIG, opnsense.CONF_TRACKER_INTERFACES: ["INVALID_IF"]},
    )
    entry.add_to_hass(hass)

    interface_client = mock.MagicMock()
    interface_client.get_arp.return_value = []
    mocked_opnsense.InterfaceClient.return_value = interface_client

    network_insight_client = mock.MagicMock()
    network_insight_client.get_interfaces.return_value = {"igb0": "WAN", "igb1": "LAN"}
    mocked_opnsense.NetworkInsightClient.return_value = network_insight_client

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
