"""The tests for the demo update platform."""
from unittest.mock import patch

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_TITLE,
)
from homeassistant.const import (
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .generator import get_mock_device


async def test_setup_params(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test the initial parameters."""

    api = get_mock_device()
    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("update.product_name_aabbccddeeff_firmware")
    assert state

    assert state.state == STATE_ON
    assert state.attributes[ATTR_TITLE] is None
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.00"
    assert state.attributes[ATTR_LATEST_VERSION] == "4.18"
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
