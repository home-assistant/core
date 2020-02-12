"""The tests for the august platform."""
from unittest.mock import MagicMock, PropertyMock

from homeassistant.components import august


def _mock_august_authenticator():
    authenticator = MagicMock(name="august.authenticator")
    authenticator.should_refresh = MagicMock(
        name="august.authenticator.should_refresh", return_value=0
    )
    authenticator.refresh_access_token = MagicMock(
        name="august.authenticator.refresh_access_token"
    )
    return authenticator


def _mock_august_authentication(token_text, token_timestamp):
    authentication = MagicMock(name="august.authentication")
    type(authentication).access_token = PropertyMock(return_value=token_text)
    type(authentication).access_token_expires = PropertyMock(
        return_value=token_timestamp
    )
    return authentication


def test__refresh_access_token():
    """Set up things to be run when tests are started."""
    authentication = _mock_august_authentication("original_token", 1234)
    authenticator = _mock_august_authenticator()
    data = august.AugustData(
        MagicMock(name="hass"), MagicMock(name="api"), authentication, authenticator
    )
    data._refresh_access_token_if_needed()
    authenticator.refresh_access_token.assert_not_called()

    authenticator.should_refresh.return_value = 1
    authenticator.refresh_access_token.return_value = _mock_august_authentication(
        "new_token", 5678
    )
    data._refresh_access_token_if_needed()
    authenticator.refresh_access_token.assert_called()
    assert data._access_token == "new_token"
    assert data._access_token_expires == 5678
