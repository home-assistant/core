"""Test the identify button for HomeWizard."""
from unittest.mock import patch

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers import entity_registry as er

from .generator import get_mock_device


async def test_identify_button_entity_not_loaded_when_not_available(
    hass, mock_config_entry_data, mock_config_entry
):
    """Does not load button when device has no support for it."""

    api = get_mock_device(product_type="HWE-P1")

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("button.product_name_aabbccddeeff_identify") is None


async def test_identify_button_is_loaded(
    hass, mock_config_entry_data, mock_config_entry
):
    """Loads button when device has support."""

    api = get_mock_device(product_type="HWE-SKT", firmware_version="3.02")

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("button.product_name_aabbccddeeff_identify")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Identify"
    )

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("button.product_name_aabbccddeeff_identify")
    assert entry
    assert entry.unique_id == "aabbccddeeff_identify"
