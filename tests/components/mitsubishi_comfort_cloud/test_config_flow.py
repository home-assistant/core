"""Tests for Mitsubishi Comfort Cloud configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.mitsubishi_comfort_cloud.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_PASSWORD, MOCK_USERNAME

USER_INPUT = {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Isolate configuration from platform setup."""
    with patch(
        "homeassistant.components.mitsubishi_comfort_cloud.async_setup_entry",
        return_value=None,
    ) as mock:
        yield mock


async def test_user(
    hass: HomeAssistant, mock_cloud_account: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """An account needs no local credentials or addresses."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Mitsubishi Comfort Cloud ({MOCK_USERNAME})"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == mock_cloud_account.user_id
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(AuthenticationError("bad credentials"), "invalid_auth", id="auth"),
        pytest.param(
            DeviceConnectionError("offline"), "cannot_connect", id="connection"
        ),
        pytest.param(RuntimeError("unexpected"), "unknown", id="unexpected"),
    ],
)
@pytest.mark.parametrize("method", ["login", "get_zones"])
async def test_errors(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    error: Exception,
    expected: str,
    method: str,
) -> None:
    """Login and discovery failures leave a retryable form."""
    getattr(mock_cloud_account, method).side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    getattr(mock_cloud_account, method).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == mock_cloud_account.user_id


@pytest.mark.parametrize(
    "zones",
    [
        pytest.param([], id="empty"),
        pytest.param(
            [{"adapter": {"deviceSerial": "STATION", "isHeadless": True}}],
            id="station-only",
        ),
        pytest.param([{"name": "No adapter"}, {"adapter": {}}], id="no-serial"),
    ],
)
async def test_no_devices(
    hass: HomeAssistant, mock_cloud_account: AsyncMock, zones: list[dict]
) -> None:
    """Only supported indoor units permit setup."""
    supported_zones = mock_cloud_account.get_zones.return_value
    mock_cloud_account.get_zones.return_value = zones
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}
    mock_cloud_account.get_zones.return_value = supported_zones
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == mock_cloud_account.user_id


async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reject duplicate cloud accounts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_account_does_not_block_cloud(
    hass: HomeAssistant, mock_cloud_account: AsyncMock
) -> None:
    """The same account can be explicitly configured for both integrations."""
    MockConfigEntry(
        domain="mitsubishi_comfort", unique_id="user-12345", data=USER_INPUT
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == mock_cloud_account.user_id


async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Reauthentication updates and reloads the original entry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    mock_cloud_account.login.side_effect = AuthenticationError("expired")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "reauth_confirm"
    mock_cloud_account.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**USER_INPUT, CONF_PASSWORD: "new-password"}
    mock_setup_entry.assert_awaited_once()


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Reauthentication cannot replace the account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    mock_cloud_account.user_id = "other-user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == USER_INPUT
