"""Tests for the TelldusLive config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tellduslive import APPLICATION_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_DISCOVERY, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent setting up the integration when an entry is created."""
    with patch(
        "homeassistant.components.tellduslive.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def supports_local_api():
    """Set TelldusLive supports_local_api."""
    return True


@pytest.fixture
def authorize():
    """Set TelldusLive authorize."""
    return True


@pytest.fixture
def mock_tellduslive(supports_local_api, authorize):
    """Mock tellduslive."""
    with (
        patch("homeassistant.components.tellduslive.config_flow.Session") as Session,
        patch(
            "homeassistant.components.tellduslive.config_flow.supports_local_api"
        ) as tellduslive_supports_local_api,
    ):
        tellduslive_supports_local_api.return_value = supports_local_api
        Session().authorize.return_value = authorize
        Session().access_token = "token"
        Session().access_token_secret = "token_secret"
        Session().authorize_url = "https://example.com"
        yield Session, tellduslive_supports_local_api


# The "already_setup" abort reason has no translation in strings.json
@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.tellduslive.config.abort.already_setup"],
)
async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if TelldusLive is already setup."""
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_setup"


async def test_full_flow_implementation(hass: HomeAssistant, mock_tellduslive) -> None:
    """Test registering an implementation and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data=["localhost", "tellstick"],
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "localhost"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["description_placeholders"] == {
        "auth_url": "https://example.com",
        "app_name": APPLICATION_NAME,
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"]["host"] == "localhost"
    assert result["data"]["scan_interval"] == 60
    assert result["data"]["session"] == {"token": "token", "host": "localhost"}


@pytest.mark.parametrize("supports_local_api", [False])
async def test_step_disco_no_local_api(hass: HomeAssistant, mock_tellduslive) -> None:
    """Test configuring from discovery, not supporting local api."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data=["localhost", "tellstick"],
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud API"


async def test_step_auth(hass: HomeAssistant, mock_tellduslive) -> None:
    """Test that create cloud entity from auth, without picking a host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud API"
    assert result["data"]["host"] == "Cloud API"
    assert result["data"]["scan_interval"] == 60
    assert result["data"]["session"] == {
        "token": "token",
        "token_secret": "token_secret",
    }


@pytest.mark.parametrize("authorize", [False])
async def test_wrong_auth_flow_implementation(
    hass: HomeAssistant, mock_tellduslive: tuple[MagicMock, MagicMock]
) -> None:
    """Test wrong auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == "invalid_auth"

    session_cls, _ = mock_tellduslive
    session_cls.return_value.authorize.return_value = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (TimeoutError, "authorize_url_timeout"),
        (ValueError, "unknown_authorize_url_generation"),
    ],
)
async def test_abort_if_error_generating_auth_url(
    hass: HomeAssistant,
    mock_tellduslive: tuple[MagicMock, MagicMock],
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test abort if generating authorize url times out or blows up."""
    session_cls, _ = mock_tellduslive
    session_cls.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_abort_no_auth_url(
    hass: HomeAssistant, mock_tellduslive: tuple[MagicMock, MagicMock]
) -> None:
    """Test abort if generating authorize url returns none."""
    session_cls, _ = mock_tellduslive
    session_cls.return_value.authorize_url = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_authorize_url_generation"


async def test_discovery_already_configured(
    hass: HomeAssistant, mock_tellduslive
) -> None:
    """Test abort if already configured fires from discovery."""
    MockConfigEntry(domain=DOMAIN, data={"host": "some-host"}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data=["some-host", ""],
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
