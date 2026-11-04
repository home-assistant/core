"""Tests for the Atomberg config flow."""

from unittest.mock import AsyncMock

from atomberg_api import AtombergAuthError, AtombergConnectionError, AtombergDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_array_fixture

from homeassistant.components.atomberg.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import API_KEY, REFRESH_TOKEN

USER_INPUT = {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: REFRESH_TOKEN}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Atomberg"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == API_KEY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AtombergAuthError, "invalid_auth"),
        (AtombergConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_flow_errors_then_recovery(
    hass: HomeAssistant, mock_client: AsyncMock, exception: type[Exception], error: str
) -> None:
    """Test errors are shown and the flow can then succeed."""
    mock_client.async_get_devices.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.async_get_devices.side_effect = None
    mock_client.async_get_devices.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_duplicate_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same API key cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_reauth(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test reauthentication updates the refresh token."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: "new-token"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_duplicate_account_after_api_key_rotation(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same account cannot be added again with a rotated API key."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "rotated-key", CONF_REFRESH_TOKEN: "rotated-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AtombergAuthError, "invalid_auth"),
        (AtombergConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_errors_then_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test reauth shows each error and can then finish successfully."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    new_input = {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: "new-token"}

    mock_client.async_get_devices.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_client.async_get_devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_reauth_new_api_key_same_account(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth accepts a new API key when the account's devices match."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-key", CONF_REFRESH_TOKEN: "new-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "new-key",
        CONF_REFRESH_TOKEN: "new-token",
    }
    assert mock_config_entry.unique_id == "new-key"


async def test_reauth_wrong_account(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth aborts when the new credentials show different devices."""
    await setup_integration(hass, mock_config_entry)
    other_devices = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    for index, device in enumerate(other_devices):
        device["device_id"] = f"other{index}"
    mock_client.async_get_devices.return_value = [
        AtombergDevice.from_api(device) for device in other_devices
    ]
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "other-key", CONF_REFRESH_TOKEN: "other-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_API_KEY] == API_KEY


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_reauth_api_key_used_by_other_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth aborts when the new API key belongs to another entry."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "taken-key", CONF_REFRESH_TOKEN: "t"},
        unique_id="taken-key",
    ).add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "taken-key", CONF_REFRESH_TOKEN: "new-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_same_api_key_with_changed_devices(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth with the same API key succeeds even if the devices changed."""
    await setup_integration(hass, mock_config_entry)
    other_devices = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    for index, device in enumerate(other_devices):
        device["device_id"] = f"new{index}"
    mock_client.async_get_devices.return_value = [
        AtombergDevice.from_api(device) for device in other_devices
    ]
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: "new-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_reauth_changed_api_key_without_known_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a changed API key cannot be verified without known devices."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new-key", CONF_REFRESH_TOKEN: "new-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_API_KEY] == API_KEY
