"""Test the Sky Remote config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.sky_remote.const import CONF_LEGACY_CONTROL_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, sample_config, mock_remote_control
) -> None:
    """Test we can setup an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        sample_config,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["data"] == sample_config
    assert result["title"] == "Living Room Sky Box"

    assert len(mock_setup_entry.mock_calls) == 1


def get_suggested_value(schema, key):
    """Get suggested value for key in voluptuous schema."""
    return next(x for x in schema.schema if x == key).description["suggested_value"]


async def test_reconfigure_flow(
    hass: HomeAssistant, sample_config, mock_remote_control
) -> None:
    """Test we can reconfigure an entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=sample_config,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM

    for k, v in sample_config.items():
        assert get_suggested_value(result["data_schema"], k) == v

    new_data = {
        CONF_HOST: "new.com",
        CONF_NAME: "New Name",
        CONF_LEGACY_CONTROL_PORT: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_data,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert entry.data == new_data
