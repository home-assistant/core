"""Test MatrixBot._login."""

import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from tests.components.matrix.conftest import TEST_MXID, TEST_TOKEN


async def test_login(matrix_bot: MatrixBot, mock_client):
    """Test various good and bad login paths.

    "Good" test password is configured by default from config.
    """

    # Test good login using good password and missing access token.
    await matrix_bot._login()
    assert matrix_bot._client.logged_in

    # Test good login using a good password and bad stored access_token.
    matrix_bot._access_tokens = {TEST_MXID: "WrongToken"}
    await matrix_bot._login()
    assert matrix_bot._client.logged_in

    # Test good login using a good access_token and bad password.
    matrix_bot._access_tokens = {TEST_MXID: TEST_TOKEN}
    await matrix_bot._login()
    assert matrix_bot._client.logged_in

    # Test bad login using a bad password and bad stored access_token.
    matrix_bot._password = "WrongPassword"
    matrix_bot._access_tokens = {TEST_MXID: "WrongToken"}
    with pytest.raises(ConfigEntryAuthFailed):
        await matrix_bot._login()
    assert not matrix_bot._client.logged_in

    # Test bad login using bad password and missing access token.
    matrix_bot._access_tokens = {}
    with pytest.raises(ConfigEntryAuthFailed):
        await matrix_bot._login()
    assert not matrix_bot._client.logged_in


async def test_get_auth_tokens(matrix_bot: MatrixBot, mock_load_json):
    """Test loading access_tokens from a mocked file."""

    # Test loading good tokens.
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {TEST_MXID: TEST_TOKEN}

    # Test miscellaneous error from hass.
    mock_load_json.side_effect = HomeAssistantError()
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {}
