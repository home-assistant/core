"""Test Simplepush config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from simplepush import ApiError
from simplepush.legacy import UnknownError

from homeassistant import config_entries
from homeassistant.components.simplepush.const import CONF_DEVICE_KEY, CONF_SALT, DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry

MOCK_CONFIG = {CONF_API_TOKEN: "token"}

LEGACY_CONFIG = {
    CONF_DEVICE_KEY: "abc",
    CONF_NAME: "simplepush",
    CONF_PASSWORD: "password",
    CONF_SALT: "salt",
}


@pytest.fixture(autouse=True)
def simplepush_setup_fixture() -> Generator[None]:
    """Patch simplepush setup entry."""
    with patch(
        "homeassistant.components.simplepush.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture(autouse=True)
def mock_client() -> Generator[MagicMock]:
    """Patch the simplepush client."""
    with patch("homeassistant.components.simplepush.config_flow.Client") as mock:
        yield mock


@pytest.fixture
def mock_legacy_send() -> Generator[MagicMock]:
    """Patch the send of the old app."""
    with patch("homeassistant.components.simplepush.config_flow.send") as mock:
        yield mock


async def start_flow(hass: HomeAssistant, app: str) -> FlowResult:
    """Start a user flow and pick the app in the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["app", "legacy"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": app}
    )


async def test_flow_successful(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test setting up the current app with an API token."""
    result = await start_flow(hass, "app")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "app"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Simplepush"
    assert result["data"] == MOCK_CONFIG
    mock_client.assert_called_once_with(api_token="token")
    mock_client.return_value.send_task.assert_called_once()


async def test_flow_api_token_already_configured(hass: HomeAssistant) -> None:
    """Test setting up the current app with a configured API token."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG).add_to_hass(hass)

    result = await start_flow(hass, "app")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(ApiError(401, ""), "invalid_auth", id="invalid_auth"),
        pytest.param(ApiError(500, ""), "cannot_connect", id="server_error"),
        pytest.param(OSError, "cannot_connect", id="network_error"),
    ],
)
async def test_flow_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    error: str,
) -> None:
    """Test a failing test message and recovering from it."""
    mock_client.return_value.send_task.side_effect = side_effect
    result = await start_flow(hass, "app")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.return_value.send_task.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {CONF_DEVICE_KEY: "abc", CONF_NAME: "simplepush"}, id="unencrypted"
        ),
        pytest.param(LEGACY_CONFIG, id="encrypted"),
    ],
)
async def test_legacy_flow_successful(
    hass: HomeAssistant, mock_legacy_send: MagicMock, user_input: dict[str, str]
) -> None:
    """Test setting up the old app with a device key."""
    result = await start_flow(hass, "legacy")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "simplepush"
    assert result["data"] == user_input
    assert result["result"].unique_id == "abc"
    mock_legacy_send.assert_called_once()


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param({**LEGACY_CONFIG, CONF_NAME: "other"}, id="device_key"),
        pytest.param({**LEGACY_CONFIG, CONF_DEVICE_KEY: "other"}, id="name"),
    ],
)
@pytest.mark.usefixtures("mock_legacy_send")
async def test_legacy_flow_already_configured(
    hass: HomeAssistant, existing: dict[str, str]
) -> None:
    """Test setting up the old app with a configured device key or name."""
    MockConfigEntry(
        domain=DOMAIN, data=existing, unique_id=existing[CONF_DEVICE_KEY]
    ).add_to_hass(hass)

    result = await start_flow(hass, "legacy")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=LEGACY_CONFIG,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_legacy_flow_cannot_connect(
    hass: HomeAssistant, mock_legacy_send: MagicMock
) -> None:
    """Test a failing test message to the old app and recovering from it."""
    mock_legacy_send.side_effect = UnknownError
    result = await start_flow(hass, "legacy")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=LEGACY_CONFIG,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_legacy_send.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=LEGACY_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
