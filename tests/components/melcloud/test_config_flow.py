"""Test the MELCloud config flow."""

from http import HTTPStatus
from unittest.mock import patch

from aiohttp import ClientError, ClientResponseError
import pymelcloud
import pytest

from homeassistant import config_entries
from homeassistant.components.melcloud.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_login():
    """Mock pymelcloud login."""
    with patch(
        "homeassistant.components.melcloud.config_flow.pymelcloud.login"
    ) as mock:
        mock.return_value = "test-token"
        yield mock


@pytest.fixture
def mock_get_devices():
    """Mock pymelcloud get_devices."""
    with patch(
        "homeassistant.components.melcloud.config_flow.pymelcloud.get_devices"
    ) as mock:
        mock.return_value = {
            pymelcloud.DEVICE_TYPE_ATA: [],
            pymelcloud.DEVICE_TYPE_ATW: [],
        }
        yield mock


@pytest.fixture
def mock_request_info():
    """Mock RequestInfo to create ClientResponseErrors."""
    with patch("aiohttp.RequestInfo") as mock_ri:
        mock_ri.return_value.real_url.return_value = ""
        yield mock_ri


async def test_form(hass: HomeAssistant, mock_login, mock_get_devices) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.melcloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-email@test-domain.com"
    assert result2["data"] == {
        "username": "test-email@test-domain.com",
        "token": "test-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "reason"),
    [(ClientError(), "cannot_connect"), (TimeoutError(), "cannot_connect")],
)
async def test_form_errors(
    hass: HomeAssistant, mock_login, mock_get_devices, error, reason
) -> None:
    """Test we handle cannot connect error."""
    mock_login.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"username": "test-email@test-domain.com", "password": "test-password"},
    )

    assert len(mock_login.mock_calls) == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (HTTPStatus.FORBIDDEN, "invalid_auth"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
    ],
)
async def test_form_response_errors(
    hass: HomeAssistant, mock_login, mock_get_devices, mock_request_info, error, message
) -> None:
    """Test we handle response errors."""
    mock_login.side_effect = ClientResponseError(mock_request_info(), (), status=error)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"username": "test-email@test-domain.com", "password": "test-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == message


async def test_token_refresh(hass: HomeAssistant, mock_login, mock_get_devices) -> None:
    """Re-configuration with existing username should refresh token."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-email@test-domain.com", "token": "test-original-token"},
        unique_id="test-email@test-domain.com",
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.melcloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "username": "test-email@test-domain.com",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 0

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.data["username"] == "test-email@test-domain.com"
    assert entry.data["token"] == "test-token"


async def test_token_reauthentication(
    hass: HomeAssistant,
    mock_login,
    mock_get_devices,
) -> None:
    """Re-configuration with existing username should refresh token, if made invalid."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-email@test-domain.com", "token": "test-original-token"},
        unique_id="test-email@test-domain.com",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TimeoutError(), "cannot_connect"),
        (AttributeError(name="get"), "invalid_auth"),
    ],
)
async def test_form_errors_reauthentication(
    hass: HomeAssistant, mock_login, error, reason
) -> None:
    """Test we handle cannot connect error."""
    mock_login.side_effect = error
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-email@test-domain.com", "token": "test-original-token"},
        unique_id="test-email@test-domain.com",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    with patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == reason

    mock_login.side_effect = None
    with patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (HTTPStatus.FORBIDDEN, "invalid_auth"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
    ],
)
async def test_client_errors_reauthentication(
    hass: HomeAssistant, mock_login, mock_request_info, error, reason
) -> None:
    """Test we handle cannot connect error."""
    mock_login.side_effect = ClientResponseError(mock_request_info(), (), status=error)
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-email@test-domain.com", "token": "test-original-token"},
        unique_id="test-email@test-domain.com",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    with patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["errors"]["base"] == reason
    assert result["type"] is FlowResultType.FORM

    mock_login.side_effect = None
    with patch(
        "homeassistant.components.melcloud.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-email@test-domain.com", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
