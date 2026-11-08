"""Test Synology SRM configuration."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import ConnectionError
from synology_srm.http import SynologyApiError, SynologyHttpException

from homeassistant.components.synology_srm.const import CONF_TRACKED_DEVICES, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import CLIENT, CONFIG, MAC


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test setup with defaults and duplicate prevention."""
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "host": CONFIG["host"],
                "username": "admin",
                "password": "password",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"
        assert result["data_schema"]({}) == {CONF_TRACKED_DEVICES: []}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: []}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices_selected"}
        assert not hass.config_entries.async_entries(DOMAIN)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {**CONFIG, CONF_TRACKED_DEVICES: [MAC]}
        assert result["title"] == CONFIG["host"]
        mock_client.http.disable_https_verify.assert_called_once()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ConnectionError(), "cannot_connect", id="connection"),
        pytest.param(SynologyHttpException(), "cannot_connect", id="http"),
        pytest.param(SynologyApiError(400, "Invalid login"), "invalid_auth", id="auth"),
        pytest.param(SynologyApiError(500, "API failure"), "cannot_connect", id="api"),
        pytest.param(RuntimeError(), "unknown", id="unexpected"),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """Test errors and recovery in the same flow."""
    mock_client.core.get_network_nsm_device.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["errors"] == {"base": expected}
    mock_client.core.get_network_nsm_device.side_effect = None
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_verify_ssl(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test certificate verification stays enabled when requested."""
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**CONFIG, "verify_ssl": True}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "devices"
    mock_client.http.disable_https_verify.assert_not_called()


async def test_no_devices(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Allow retrying when the router has no known devices."""
    mock_client.core.get_network_nsm_device.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_devices_found"}
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_client.core.get_network_nsm_device.return_value = [CLIENT]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["step_id"] == "devices"
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("devices", [[CLIENT], []], ids=["clients", "no-clients"])
async def test_reauth(
    hass: HomeAssistant,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    devices: list[dict[str, object]],
) -> None:
    """Update credentials and reload the existing entry without losing selection."""
    entry = MockConfigEntry(domain=DOMAIN, data={**CONFIG, CONF_TRACKED_DEVICES: [MAC]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
    original = entity_registry.async_get(entity_id)
    mock_client.core.get_network_nsm_device.side_effect = SynologyApiError(
        400, "Invalid login"
    )
    assert not await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    mock_client.core.get_network_nsm_device.side_effect = None
    mock_client.core.get_network_nsm_device.return_value = devices
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == {
        **CONFIG,
        CONF_TRACKED_DEVICES: [MAC],
        CONF_USERNAME: "new-user",
        CONF_PASSWORD: "new-password",
    }
    updated = entity_registry.async_get(entity_id)
    assert updated.id == original.id
    assert updated.device_id == original.device_id
    assert updated.config_entry_id == original.config_entry_id
    assert updated.disabled_by == original.disabled_by


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ConnectionError(), "cannot_connect", id="connection"),
        pytest.param(SynologyApiError(400, "Invalid login"), "invalid_auth", id="auth"),
        pytest.param(SynologyApiError(500, "API failure"), "cannot_connect", id="api"),
        pytest.param(RuntimeError(), "unknown", id="unexpected"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected: str,
) -> None:
    """Keep the credentials unchanged until a successful reauthentication."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    mock_client.core.get_network_nsm_device.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected}
    assert mock_config_entry.data == CONFIG
    mock_client.core.get_network_nsm_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
