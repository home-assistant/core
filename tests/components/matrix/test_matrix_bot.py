"""Configure and test MatrixBot."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.components.matrix.const import (
    DOMAIN,
    SERVICE_REACT,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_CONFIG_DATA_ACCESS_TOKEN,
    TEST_NOTIFIER_NAME,
    TEST_PASSWORD,
    TEST_TOKEN,
    config_with_credentials,
)


async def test_services(hass: HomeAssistant, matrix_bot: MatrixBot) -> None:
    """Test hass/MatrixBot state."""

    services = hass.services.async_services()

    # Verify that the matrix service is registered
    assert (matrix_service := services.get(DOMAIN))
    assert SERVICE_SEND_MESSAGE in matrix_service
    assert SERVICE_REACT in matrix_service

    # Verify that the matrix notifier is registered
    assert (notify_service := services.get(NOTIFY_DOMAIN))
    assert TEST_NOTIFIER_NAME in notify_service


@pytest.mark.usefixtures("mock_client", "mock_allowed_path")
async def test_setup_with_access_token(
    hass: HomeAssistant, mock_save_json: MagicMock
) -> None:
    """Test setting up with an access_token instead of a password."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG_DATA_ACCESS_TOKEN)
    await hass.async_block_till_done()

    assert isinstance(matrix_bot := hass.data[DOMAIN], MatrixBot)
    assert matrix_bot._password is None
    assert matrix_bot._configured_access_token == TEST_TOKEN

    await hass.async_start()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert matrix_bot._client.logged_in
    # A user-managed access token is not copied into the session file.
    mock_save_json.assert_not_called()


@pytest.mark.parametrize(
    "credentials",
    [
        pytest.param({}, id="no_credentials"),
        pytest.param(
            {CONF_PASSWORD: TEST_PASSWORD, CONF_ACCESS_TOKEN: TEST_TOKEN},
            id="both_credentials",
        ),
    ],
)
@pytest.mark.usefixtures("mock_client", "mock_save_json")
async def test_invalid_credentials_config(
    hass: HomeAssistant, credentials: dict[str, str]
) -> None:
    """Test that exactly one of password and access_token is required."""
    assert not await async_setup_component(
        hass, DOMAIN, config_with_credentials(credentials)
    )
    assert DOMAIN not in hass.data
