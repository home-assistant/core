"""The tests for the august platform."""
from unittest.mock import MagicMock

from homeassistant.components import august

from tests.components.august.mocks import (
    _mock_august_authentication,
    _mock_august_authenticator,
)


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
