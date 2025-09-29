"""Test the Ubiquiti airOS config flow."""

from typing import Any
from unittest.mock import AsyncMock

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSDeviceConnectionError,
    AirOSKeyDataMissingError,
)
import pytest

from homeassistant.components.airos.const import DOMAIN, SECTION_ADVANCED_SETTINGS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

NEW_PASSWORD = "new_password"
REAUTH_STEP = "reauth_confirm"

MOCK_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    SECTION_ADVANCED_SETTINGS: {
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    },
}
MOCK_CONFIG_REAUTH = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "wrong-password",
}


async def test_form_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    ap_fixture: dict[str, Any],
) -> None:
    """Test we get the form and create the appropriate entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["result"].unique_id == "01:23:45:67:89:AB"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_entry(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the form does not allow duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AirOSDeviceConnectionError, "cannot_connect"),
        (AirOSKeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
)
async def test_form_exception_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle exceptions."""
    mock_airos_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_airos_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_scenario(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == REAUTH_STEP

    mock_airos_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    # Always test resolution
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD


@pytest.mark.parametrize(
    ("reauth_exception", "expected_error"),
    [
        (None, None),
        (AirOSConnectionAuthenticationError, "invalid_auth"),
        (AirOSDeviceConnectionError, "cannot_connect"),
        (AirOSKeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
    ids=[
        "reauth_succes",
        "invalid_auth",
        "cannot_connect",
        "key_data_missing",
        "unknown",
    ],
)
async def test_reauth_flow_scenarios(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reauth_exception: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication from start (failure) to finish (success)."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == REAUTH_STEP

    mock_airos_client.login.side_effect = reauth_exception

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    if expected_error:
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == REAUTH_STEP
        assert result["errors"] == {"base": expected_error}

        # Retry
        mock_airos_client.login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            user_input={CONF_PASSWORD: NEW_PASSWORD},
        )

    # Always test resolution
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD


async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication failure when the unique ID changes."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    flow = flows[0]

    mock_airos_client.login.side_effect = None
    mock_airos_client.status.return_value.derived.mac = "FF:23:45:67:89:AB"

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] != NEW_PASSWORD
