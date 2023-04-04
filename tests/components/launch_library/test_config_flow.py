"""Test launch_library config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.launch_library.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    with patch(
        "homeassistant.components.launch_library.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result.get("result").data == {}


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"
