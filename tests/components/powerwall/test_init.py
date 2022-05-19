"""Tests for the PowerwallDataManager."""

from unittest.mock import MagicMock, patch

import pytest
from tesla_powerwall import AccessDeniedError, LoginResponse

from homeassistant.components.powerwall.const import DOMAIN, POWERWALL_COORDINATOR
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .mocks import _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry


async def test_update_data_reauthenticate_on_access_denied(hass: HomeAssistant):
    """Test if _update_data of PowerwallDataManager reauthenticates on AccessDeniedError."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    # login responses for the different tests:
    # 1. login success on entry setup
    # 2. login success after reauthentication
    # 3. login failure after reauthentication
    mock_powerwall.login = MagicMock(name="login", return_value=LoginResponse({}))
    mock_powerwall.get_charge = MagicMock(name="get_charge", return_value=90.0)
    mock_powerwall.is_authenticated = MagicMock(
        name="is_authenticated", return_value=True
    )
    mock_powerwall.logout = MagicMock(name="logout")

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4", CONF_PASSWORD: "password"}
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_powerwall.login.reset_mock(return_value=True)
        mock_powerwall.get_charge.side_effect = [AccessDeniedError("test"), 90.0]

        await hass.data[DOMAIN][config_entry.entry_id][
            POWERWALL_COORDINATOR
        ]._async_update_data()
        mock_powerwall.login.assert_called_once()

        mock_powerwall.login.reset_mock()
        mock_powerwall.login.side_effect = AccessDeniedError("test")
        mock_powerwall.get_charge.side_effect = [AccessDeniedError("test"), 90.0]

        with pytest.raises(ConfigEntryAuthFailed):
            await hass.data[DOMAIN][config_entry.entry_id][
                POWERWALL_COORDINATOR
            ]._async_update_data()
        mock_powerwall.login.assert_called_once()
