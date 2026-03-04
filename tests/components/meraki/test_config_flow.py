"""Test the Meraki config flow."""

from homeassistant.components.meraki.const import CONF_SECRET, CONF_VALIDATOR, DOMAIN
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(hass) -> None:
    """Test the full user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_VALIDATOR: "validator", CONF_SECRET: "secret"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Meraki"
    assert result2["data"] == {CONF_VALIDATOR: "validator", CONF_SECRET: "secret"}


async def test_single_instance(hass) -> None:
    """Test only one instance is allowed."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
