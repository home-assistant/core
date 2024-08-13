"""The gateway tests for the yale platform."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from yalexs.authenticator_common import AuthenticationState

from homeassistant.components.yale.const import DOMAIN
from homeassistant.components.yale.gateway import YaleGateway
from homeassistant.core import HomeAssistant

from .mocks import _mock_get_config, _mock_yale_authentication


async def test_refresh_access_token(hass: HomeAssistant) -> None:
    """Test token refreshes."""
    await _patched_refresh_access_token(hass, "new_token", 5678)


@patch("yalexs.manager.gateway.ApiAsync.async_get_operable_locks")
@patch("yalexs.manager.gateway.AuthenticatorAsync.async_authenticate")
@patch("yalexs.manager.gateway.AuthenticatorAsync.should_refresh")
@patch("yalexs.manager.gateway.AuthenticatorAsync.async_refresh_access_token")
async def _patched_refresh_access_token(
    hass,
    new_token,
    new_token_expire_time,
    refresh_access_token_mock,
    should_refresh_mock,
    authenticate_mock,
    async_get_operable_locks_mock,
):
    authenticate_mock.side_effect = MagicMock(
        return_value=_mock_yale_authentication(
            "original_token", 1234, AuthenticationState.AUTHENTICATED
        )
    )
    yale_gateway = YaleGateway(Path(hass.config.config_dir), MagicMock())
    mocked_config = _mock_get_config()
    await yale_gateway.async_setup(mocked_config[DOMAIN])
    await yale_gateway.async_authenticate()

    should_refresh_mock.return_value = False
    await yale_gateway.async_refresh_access_token_if_needed()
    refresh_access_token_mock.assert_not_called()

    should_refresh_mock.return_value = True
    refresh_access_token_mock.return_value = _mock_yale_authentication(
        new_token, new_token_expire_time, AuthenticationState.AUTHENTICATED
    )
    await yale_gateway.async_refresh_access_token_if_needed()
    refresh_access_token_mock.assert_called()
    assert await yale_gateway.async_get_access_token() == new_token
    assert yale_gateway.authentication.access_token_expires == new_token_expire_time
