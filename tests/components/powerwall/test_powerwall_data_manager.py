"""Tests for the PowerwalLDataManager."""

from unittest.mock import MagicMock, patch

import pytest
from tesla_powerwall import AccessDeniedError, Powerwall

from homeassistant.components.powerwall import PowerwallDataManager
from homeassistant.components.powerwall.models import PowerwallRuntimeData
from homeassistant.exceptions import ConfigEntryAuthFailed


def test_update_data_reauthenticate_on_access_denied(hass):
    """Test of _update_data of PowerwallDataManager reauthenticates on AccessDeniedError."""
    runtime_data = PowerwallRuntimeData(
        api_changed=False,
        base_info=None,
        http_session=None,
        coordinator=None,
    )
    manager = PowerwallDataManager(
        hass, Powerwall("example.com"), "example.com", "password", runtime_data
    )
    manager._recreate_powerwall_login = MagicMock(name="_recreate_powerwall_login")

    _fetch_powerwall_data_reauth_success = MagicMock(
        side_effect=[AccessDeniedError("test", None), {}]
    )
    _fetch_powerwall_data_reauth_failure = MagicMock(
        side_effect=[AccessDeniedError("test", None), AccessDeniedError("test", None)]
    )

    # test reauthentication when the first call to _fetch_powerwall_data raised an AccessDeniedError
    with patch(
        "homeassistant.components.powerwall._fetch_powerwall_data",
        new=_fetch_powerwall_data_reauth_success,
    ):
        assert manager._update_data() == {}
        manager._recreate_powerwall_login.assert_called_once()
        assert _fetch_powerwall_data_reauth_success.call_count == 2

    manager._recreate_powerwall_login.reset_mock()

    with patch(
        "homeassistant.components.powerwall._fetch_powerwall_data",
        new=_fetch_powerwall_data_reauth_failure,
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            manager._update_data()
        manager._recreate_powerwall_login.assert_called_once()
        assert _fetch_powerwall_data_reauth_failure.call_count == 2
