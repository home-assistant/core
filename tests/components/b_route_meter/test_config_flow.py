"""Test the B-Route Meter config flow."""

from homeassistant import config_entries
from homeassistant.components.b_route_meter.const import (
    CONF_RETRY_COUNT,
    CONF_ROUTE_B_ID,
    CONF_ROUTE_B_PWD,
    CONF_SERIAL_PORT,
    DEFAULT_SERIAL_PORT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_CONFIG = {
    CONF_ROUTE_B_ID: "00000000000000000000000000000000",
    CONF_ROUTE_B_PWD: "XXXXXXXXXXXX",
    CONF_SERIAL_PORT: DEFAULT_SERIAL_PORT,
    CONF_RETRY_COUNT: "3",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"B-Route Meter ({MOCK_CONFIG[CONF_ROUTE_B_ID]})"
    assert result2["data"] == {
        **MOCK_CONFIG,
        CONF_RETRY_COUNT: int(MOCK_CONFIG[CONF_RETRY_COUNT]),
    }


async def test_form_invalid_retry_count(hass: HomeAssistant) -> None:
    """Test we handle invalid retry count."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    invalid_config = {
        **MOCK_CONFIG,
        CONF_RETRY_COUNT: "11",  # Invalid retry count
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        invalid_config,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"retry_count": "invalid_retry_count"}

    invalid_config = {
        **MOCK_CONFIG,
        CONF_RETRY_COUNT: "abc",  # Invalid number
    }
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        invalid_config,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"retry_count": "invalid_retry_count"}


async def test_form_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    # First setup
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONFIG
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = await _setup_config_entry(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        **MOCK_CONFIG,
        CONF_RETRY_COUNT: int(MOCK_CONFIG[CONF_RETRY_COUNT]),
    }


async def test_options_flow_invalid_retry(hass: HomeAssistant) -> None:
    """Test config flow options with invalid retry count."""
    config_entry = await _setup_config_entry(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    invalid_config = {
        **MOCK_CONFIG,
        CONF_RETRY_COUNT: "11",  # Invalid retry count
    }
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=invalid_config,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"retry_count": "invalid_retry_count"}


async def _setup_config_entry(hass: HomeAssistant):
    """Set up the config entry."""
    config_entry = config_entries.ConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            **MOCK_CONFIG,
            CONF_RETRY_COUNT: int(MOCK_CONFIG[CONF_RETRY_COUNT]),
        },
        source=config_entries.SOURCE_USER,
        options={},
        entry_id="test",
        version=1,
        minor_version=1,
        unique_id=MOCK_CONFIG[CONF_ROUTE_B_ID],
        discovery_keys=[],
    )
    await hass.config_entries.async_add(config_entry)
    await hass.async_block_till_done()
    return config_entry
