"""Test Simplepush config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from simplepush import ApiError
from simplepush.legacy import UnknownError

from homeassistant import config_entries
from homeassistant.components.simplepush.const import (
    CONF_DEVICE_KEY,
    CONF_SALT,
    CONF_TOPIC,
    DOMAIN,
)
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

# sha256("token")[:16], the unique id of an entry with MOCK_CONFIG
TOKEN_UNIQUE_ID = "3c469e9d6c5875d3"


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
    """Test user initialized flow."""
    result = await start_flow(hass, "app")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Simplepush"
    assert result["data"] == MOCK_CONFIG
    assert result["result"].unique_id == TOKEN_UNIQUE_ID
    mock_client.assert_called_once_with(api_token="token")
    mock_client.return_value.send_task.assert_called_once_with(
        topic=None, title="HA test", content="Message delivered successfully"
    )


async def test_flow_user_api_token_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate API token."""
    MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=TOKEN_UNIQUE_ID,
    ).add_to_hass(hass)

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
        pytest.param(ApiError(403, ""), "cannot_connect", id="forbidden"),
        pytest.param(ApiError(500, ""), "cannot_connect", id="server_error"),
        pytest.param(OSError, "cannot_connect", id="network_error"),
    ],
)
async def test_flow_user_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    error: str,
) -> None:
    """Test a failing test notification and recovering from it."""
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


@pytest.mark.parametrize(
    ("data", "unique_id", "expected_data", "expected_unique_id", "topic"),
    [
        pytest.param(
            LEGACY_CONFIG,
            "abc",
            {CONF_API_TOKEN: "token", CONF_NAME: "simplepush", CONF_TOPIC: "abc"},
            "abc",
            "abc",
            id="old_app_entry",
        ),
        pytest.param(
            {CONF_API_TOKEN: "old", CONF_NAME: "simplepush", CONF_TOPIC: "abc"},
            "abc",
            {CONF_API_TOKEN: "token", CONF_NAME: "simplepush", CONF_TOPIC: "abc"},
            "abc",
            "abc",
            id="moved_entry",
        ),
        pytest.param(
            {CONF_API_TOKEN: "old"},
            "old-unique-id",
            MOCK_CONFIG,
            TOKEN_UNIQUE_ID,
            None,
            id="own_devices_entry",
        ),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    data: dict[str, Any],
    unique_id: str,
    expected_data: dict[str, Any],
    expected_unique_id: str,
    topic: str | None,
) -> None:
    """Test setting a new API token, which moves an old app entry to the topic."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="simplepush", data=data, unique_id=unique_id
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == expected_data
    assert entry.unique_id == expected_unique_id
    mock_client.return_value.send_task.assert_called_once_with(
        topic=topic, title="HA test", content="Message delivered successfully"
    )


async def test_reconfigure_error(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test moving an old app entry before the app imported its device key."""
    entry = MockConfigEntry(domain=DOMAIN, data=LEGACY_CONFIG, unique_id="abc")
    entry.add_to_hass(hass)
    mock_client.return_value.send_task.side_effect = ApiError(403, "")

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "topic_not_joined"}

    mock_client.return_value.send_task.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_already_configured(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test reconfiguring with the API token of another entry."""
    MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=TOKEN_UNIQUE_ID,
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "old"},
        unique_id="old-unique-id",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.return_value.send_task.assert_not_called()
