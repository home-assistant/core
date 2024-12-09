"""Tests for the config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.ohme.config_flow import OhmeConfigFlow, OhmeOptionsFlow
from homeassistant.components.ohme.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_session")
async def test_config_flow(hass: HomeAssistant) -> None:
    """Test config flow."""

    # Initial form load
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    # Failed login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter1"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}

    # Successful login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter2"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_session")
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""

    # Initial form load
    entry = MockConfigEntry(
        domain=DOMAIN, data={"email": "test@example.com", "password": "hunter2"}
    )

    flow = OhmeConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, OhmeOptionsFlow)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Failed login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter1"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}

    # Successful login
    with patch("ohme.OhmeApiClient.async_refresh_session", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"email": "test@example.com", "password": "hunter2"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
