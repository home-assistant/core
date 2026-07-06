"""Test the Free Mobile notify platform."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def mock_send_sms() -> Generator[MagicMock]:
    """Mock the Free Mobile SMS client's send_sms call."""
    with patch("freesms.FreeClient.send_sms") as mock_send_sms:
        yield mock_send_sms


@pytest.fixture
async def config_entry(
    hass: HomeAssistant, mock_send_sms: MagicMock
) -> MockConfigEntry:
    """Set up a loaded config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Maman", data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


@pytest.mark.usefixtures("config_entry")
async def test_send_message(hass: HomeAssistant, mock_send_sms: MagicMock) -> None:
    """Test sending a message successfully."""
    mock_send_sms.return_value = MagicMock(status_code=HTTPStatus.OK)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "maman",
        {"message": "Hello World"},
        blocking=True,
    )

    mock_send_sms.assert_called_once_with("Hello World")


@pytest.mark.parametrize(
    ("status_code", "translation_key"),
    [
        pytest.param(
            HTTPStatus.BAD_REQUEST, "missing_parameter", id="missing_parameter"
        ),
        pytest.param(
            HTTPStatus.PAYMENT_REQUIRED, "rate_limit_exceeded", id="rate_limit"
        ),
        pytest.param(HTTPStatus.FORBIDDEN, "invalid_auth", id="invalid_auth"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR, "server_error", id="server_error"
        ),
    ],
)
@pytest.mark.usefixtures("config_entry")
async def test_send_message_errors(
    hass: HomeAssistant,
    mock_send_sms: MagicMock,
    status_code: HTTPStatus,
    translation_key: str,
) -> None:
    """Test send_message raises the translated error matching the status code."""
    mock_send_sms.return_value = MagicMock(status_code=status_code)

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "maman",
            {"message": "Hello World"},
            blocking=True,
        )

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == translation_key
