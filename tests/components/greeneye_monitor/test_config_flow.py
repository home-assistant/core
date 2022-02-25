"""Tests for greeneye_monitor config_flow."""

from homeassistant import config_entries
from homeassistant.components.greeneye_monitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .common import make_new_config_entry


async def test_new_config_entry(hass: HomeAssistant) -> None:
    """Test that the config flow for a newly added integration creates an entry of the expected format."""
    expected = make_new_config_entry()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**expected.data}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == expected.data
    assert result["options"] == expected.options
    assert result["version"] == expected.version


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test that we only allow a single instance of the integration."""

    config_entry = make_new_config_entry()
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_ABORT
