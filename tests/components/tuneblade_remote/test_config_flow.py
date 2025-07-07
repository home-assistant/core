"""Test suite for the TuneBlade Remote config flow integration."""

from homeassistant import config_entries
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_user_config_flow(hass: HomeAssistant, mock_tuneblade_api) -> None:
    """Test a successful user-initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Submit the form with default data
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"host": "192.168.1.123"},
    )

    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "TuneBlade (192.168.1.123)"
    assert result2["data"] == {"host": "192.168.1.123"}
