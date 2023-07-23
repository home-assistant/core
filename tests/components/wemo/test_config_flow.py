"""Tests for Wemo config flow."""

from dataclasses import asdict

from homeassistant import data_entry_flow
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.components.wemo.wemo_device import Options
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, patch


async def test_not_discovered(hass: HomeAssistant) -> None:
    """Test setting up with no devices discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch("homeassistant.components.wemo.config_flow.pywemo") as mock_pywemo:
        mock_pywemo.discover_devices.return_value = []
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_options(hass: HomeAssistant) -> None:
    """Test updating options."""
    options = Options(enable_subscription=False, enable_long_press=False)
    entry = MockConfigEntry(domain=DOMAIN, title="Wemo")
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=asdict(options)
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert Options(**result["data"]) == options


async def test_invalid_options(hass: HomeAssistant) -> None:
    """Test invalid option combinations."""
    entry = MockConfigEntry(domain=DOMAIN, title="Wemo")
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # enable_subscription must be True if enable_long_press is True (default).
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"enable_subscription": False}
    )
    assert result["errors"] == {
        "enable_subscription": "long_press_requires_subscription"
    }
