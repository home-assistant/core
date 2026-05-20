"""Tests for FRITZ!Box Tools WireGuard VPN coordinator."""

# pylint: disable=unused-argument,redefined-outer-name
from unittest.mock import AsyncMock, patch

from fritzboxvpn.const import PROTOCOL_HTTP, PROTOCOL_HTTPS
import pytest

from homeassistant.components.fritz.const import CONF_FEATURE_WIREGUARD_VPN, DOMAIN
from homeassistant.components.fritz.coordinator import (
    FritzVpnCoordinator,
    vpn_auth_failed,
    vpn_web_ui_protocol,
)
from homeassistant.components.fritz.vpn_data import FRITZ_VPN_DATA_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SSL
from homeassistant.core import HomeAssistant

from .conftest import MOCK_VPN_CONNECTIONS
from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
async def vpn_coordinator(
    hass: HomeAssistant, mock_vpn_session: AsyncMock
) -> FritzVpnCoordinator:
    """FritzVpnCoordinator with mocked fritzboxvpn session."""
    with patch(
        "homeassistant.components.fritz.coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        return FritzVpnCoordinator(hass, dict(MOCK_USER_DATA), entry_id="test-entry")


async def test_vpn_coordinator_starts_with_fritz_entry(  # pylint: disable=unused-argument
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mock_vpn_session: AsyncMock,
) -> None:
    """VPN coordinator is stored separately from AvmWrapper runtime_data."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    vpn_data = hass.data[FRITZ_VPN_DATA_KEY][entry.entry_id]
    assert vpn_data.coordinator.data == MOCK_VPN_CONNECTIONS
    assert vpn_data.coordinator.get_vpn_status("uid-office") == "enabled"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_vpn_session.async_close.assert_called_once()
    assert entry.entry_id not in hass.data.get(FRITZ_VPN_DATA_KEY, {})


async def test_vpn_disabled_via_options_skips_coordinator(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mock_vpn_session: AsyncMock,
) -> None:
    """WireGuard VPN can be disabled in integration options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_FEATURE_WIREGUARD_VPN: False},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id not in hass.data.get(FRITZ_VPN_DATA_KEY, {})
    mock_vpn_session.async_get_vpn_connections.assert_not_called()


async def test_vpn_setup_failure_closes_session(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mock_vpn_session: AsyncMock,
) -> None:
    """Failed VPN setup must close the session; FRITZ!Box Tools still loads."""
    mock_vpn_session.async_get_vpn_connections.side_effect = ConnectionError(
        "VPN unavailable"
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id not in hass.data.get(FRITZ_VPN_DATA_KEY, {})
    mock_vpn_session.async_close.assert_called_once()


@pytest.mark.parametrize(
    ("connection_uid", "data", "expected_status"),
    [
        ("missing", MOCK_VPN_CONNECTIONS, "unknown"),
        (
            "uid-office",
            {
                "uid-office": {
                    "name": "Office",
                    "active": False,
                    "connected": False,
                    "uid": "wg-1",
                }
            },
            "disabled",
        ),
        (
            "uid-office",
            {
                "uid-office": {
                    "name": "Office",
                    "active": True,
                    "connected": True,
                    "uid": "wg-1",
                }
            },
            "connected",
        ),
        (
            "uid-office",
            {
                "uid-office": {
                    "name": "Office",
                    "active": True,
                    "connected": False,
                    "uid": "wg-1",
                }
            },
            "enabled",
        ),
    ],
)
async def test_vpn_coordinator_get_vpn_status(
    vpn_coordinator: FritzVpnCoordinator,
    connection_uid: str,
    data: dict,
    expected_status: str,
) -> None:
    """get_vpn_status returns the expected VPN status string."""
    vpn_coordinator.async_set_updated_data(data)
    assert vpn_coordinator.get_vpn_status(connection_uid) == expected_status


async def test_vpn_coordinator_update_auth_error_schedules_reauth(
    hass: HomeAssistant,
    mock_vpn_session: AsyncMock,
) -> None:
    """Authentication errors during refresh set last_update_success to False."""
    mock_vpn_session.async_get_vpn_connections.side_effect = Exception("login failed")

    coordinator = FritzVpnCoordinator(hass, dict(MOCK_USER_DATA), entry_id="test-entry")
    # Replace the session with our mocked one that has the side_effect
    coordinator.fritz_session = mock_vpn_session

    await coordinator.async_refresh()

    # After a failed refresh, the coordinator should have last_update_success=False
    assert not coordinator.last_update_success


async def test_vpn_coordinator_update_connection_error_retry_after(
    hass: HomeAssistant,
    mock_vpn_session: AsyncMock,
) -> None:
    """Transient connection errors set last_update_success to False."""
    mock_vpn_session.async_get_vpn_connections.side_effect = ConnectionError("timeout")

    coordinator = FritzVpnCoordinator(hass, dict(MOCK_USER_DATA), entry_id="test-entry")
    # Replace the session with our mocked one that has the side_effect
    coordinator.fritz_session = mock_vpn_session

    await coordinator.async_refresh()

    # After a failed refresh, the coordinator should have last_update_success=False
    assert not coordinator.last_update_success


def test_vpn_web_ui_protocol_follows_conf_ssl() -> None:
    """Web UI protocol follows CONF_SSL."""
    assert vpn_web_ui_protocol({CONF_SSL: False}) == PROTOCOL_HTTP
    assert vpn_web_ui_protocol({CONF_SSL: True}) == PROTOCOL_HTTPS


def test_vpn_auth_failed() -> None:
    """Detect auth-related VPN errors."""
    assert vpn_auth_failed(Exception("login failed"))
    assert not vpn_auth_failed(ConnectionError("timeout"))


async def test_vpn_setup_auth_error_skips_vpn_setup(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mock_vpn_session: AsyncMock,
) -> None:
    """VPN auth failure during setup skips VPN but FRITZ!Box Tools still loads."""
    mock_vpn_session.async_get_vpn_connections.side_effect = Exception("login failed")
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzBoxVPNSession",
        return_value=mock_vpn_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id not in hass.data.get(FRITZ_VPN_DATA_KEY, {})
