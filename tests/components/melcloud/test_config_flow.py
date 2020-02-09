"""Test the MELCloud config flow."""
import asyncio

from aiohttp import ClientError, ClientResponseError
from asynctest import patch as async_patch
import pymelcloud
import pytest

from homeassistant import config_entries
from homeassistant.components.melcloud.const import DOMAIN

from tests.common import mock_coro


@pytest.fixture
def mock_login():
    """Mock pymelcloud login."""
    with async_patch("pymelcloud.login") as mock:
        mock.return_value = mock_coro("test-token")
        yield mock


@pytest.fixture
def mock_get_devices():
    """Mock pymelcloud get_devices."""
    with async_patch("pymelcloud.get_devices") as mock:
        mock.return_value = mock_coro(
            {pymelcloud.DEVICE_TYPE_ATA: [], pymelcloud.DEVICE_TYPE_ATW: []}
        )
        yield mock


@pytest.fixture
def mock_request_info():
    """Mock RequestInfo to create ClientResposenErrors."""
    with async_patch("aiohttp.RequestInfo") as mock_ri:
        mock_ri.return_value.real_url.return_value = ""
        yield mock_ri


async def test_form(hass, mock_login, mock_get_devices):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with async_patch(
        "homeassistant.components.melcloud.async_setup", return_value=mock_coro(True)
    ) as mock_setup, async_patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email@test-domain.com"
    assert result2["data"] == {
        "username": "test-email@test-domain.com",
        "token": "test-token",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "error,reason",
    [(ClientError(), "cannot_connect"), (asyncio.TimeoutError(), "cannot_connect")],
)
async def test_form_errors(hass, mock_login, mock_get_devices, error, reason):
    """Test we handle cannot connect error."""
    mock_login.return_value = mock_coro(exception=error)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with async_patch(
        "homeassistant.components.melcloud.async_setup", return_value=mock_coro(True)
    ), async_patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=mock_coro(True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )

    assert len(mock_login.mock_calls) == 1
    assert result2["type"] == "abort"
    assert result2["reason"] == reason


@pytest.mark.parametrize(
    "error,message",
    [(401, "invalid_auth"), (403, "invalid_auth"), (500, "cannot_connect")],
)
async def test_form_response_errors(
    hass, mock_login, mock_get_devices, mock_request_info, error, message
):
    """Test we handle response errors."""
    mock_login.return_value = mock_coro(
        exception=ClientResponseError(mock_request_info(), (), status=error),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with async_patch(
        "homeassistant.components.melcloud.async_setup", return_value=mock_coro(True)
    ), async_patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=mock_coro(True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == message


async def test_import_with_token(hass, mock_login, mock_get_devices):
    """Test successful import."""
    with async_patch(
        "homeassistant.components.melcloud.async_setup", return_value=mock_coro(True)
    ) as mock_setup, async_patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"username": "test-email@test-domain.com", "token": "test-token"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "test-email@test-domain.com"
    assert result["data"] == {
        "username": "test-email@test-domain.com",
        "token": "test-token",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_token_refresh(hass, mock_login, mock_get_devices):
    """Re-configuration with existing username should refresh token."""
    await hass.config_entries.async_add(
        config_entries.ConfigEntry(
            1,
            DOMAIN,
            "",
            {"username": "test-email@test-domain.com", "token": "test-original-token"},
            config_entries.SOURCE_USER,
            config_entries.CONN_CLASS_CLOUD_POLL,
            {},
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with async_patch(
        "homeassistant.components.melcloud.async_setup", return_value=mock_coro(True)
    ) as mock_setup, async_patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.data["username"] == "test-email@test-domain.com"
    assert entry.data["token"] == "test-token"
