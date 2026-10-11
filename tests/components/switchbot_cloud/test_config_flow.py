"""Test the SwitchBot via API config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switchbot_cloud.config_flow import (
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)
from homeassistant.components.switchbot_cloud.const import DOMAIN, ENTRY_TITLE
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

OLD_CREDENTIALS = {CONF_API_TOKEN: "old-token", CONF_API_KEY: "old-secret-key"}
NEW_CREDENTIALS = {CONF_API_TOKEN: "new-token", CONF_API_KEY: "new-secret-key"}


async def _fill_out_form_and_assert_entry_created(
    hass: HomeAssistant, flow_id: str, mock_setup_entry: AsyncMock
) -> None:
    """Util function to fill out a form and assert that a config entry is created."""
    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=[],
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )
        await hass.async_block_till_done()

        assert result_configure["type"] is FlowResultType.CREATE_ENTRY
        assert result_configure["title"] == ENTRY_TITLE
        assert result_configure["data"] == {
            CONF_API_TOKEN: "test-token",
            CONF_API_KEY: "test-secret-key",
        }
        mock_setup_entry.assert_called_once()


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] is FlowResultType.FORM
    assert not result_init["errors"]

    await _fill_out_form_and_assert_entry_created(
        hass, result_init["flow_id"], mock_setup_entry
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (SwitchBotAuthenticationError, "invalid_auth"),
        (SwitchBotConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_fails(
    hass: HomeAssistant, error: Exception, message: str, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle error cases."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=error,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )

        assert result_configure["type"] is FlowResultType.FORM
        assert result_configure["errors"] == {"base": message}
        await hass.async_block_till_done()

    await _fill_out_form_and_assert_entry_created(
        hass, result_init["flow_id"], mock_setup_entry
    )


async def test_reauth(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test reauth updates the credentials and unique ID."""
    entry = MockConfigEntry(domain=DOMAIN, data=OLD_CREDENTIALS, unique_id="old-token")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], NEW_CREDENTIALS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == NEW_CREDENTIALS
    assert entry.unique_id == "new-token"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (SwitchBotAuthenticationError, "invalid_auth"),
        (SwitchBotConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_fails(
    hass: HomeAssistant, error: Exception, message: str, mock_setup_entry: AsyncMock
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(domain=DOMAIN, data=OLD_CREDENTIALS, unique_id="old-token")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], NEW_CREDENTIALS
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": message}

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], NEW_CREDENTIALS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == NEW_CREDENTIALS


async def test_reauth_token_used_by_other_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reauth aborts when the new token belongs to another entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=OLD_CREDENTIALS, unique_id="old-token")
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, data=NEW_CREDENTIALS, unique_id="new-token"
    ).add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], NEW_CREDENTIALS
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == OLD_CREDENTIALS
    assert entry.unique_id == "old-token"
