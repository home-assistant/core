"""Tests for the Lektrico Charging Station config flow."""
from homeassistant.components.lektrico.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_FRIENDLY_NAME: "test"},
    )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "test"
    assert result2.get("data") == {CONF_HOST: "127.0.0.1", CONF_FRIENDLY_NAME: "test"}
    assert "result" in result2
