"""Test the identify button for HomeWizard."""
from unittest.mock import patch

from homewizard_energy.errors import DisabledError, RequestError
import pytest

from homeassistant.components import button
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .generator import get_mock_device


async def test_identify_button_entity_not_loaded_when_not_available(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Does not load button when device has no support for it."""

    api = get_mock_device(product_type="SDM230-WIFI")

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
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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


async def test_identify_press(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test button press is handled correctly."""

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

    assert (
        hass.states.get("button.product_name_aabbccddeeff_identify").state
        == STATE_UNKNOWN
    )

    assert api.identify.call_count == 0
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {"entity_id": "button.product_name_aabbccddeeff_identify"},
        blocking=True,
    )
    assert api.identify.call_count == 1


async def test_identify_press_catches_requesterror(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test button press is handled RequestError correctly."""

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

    assert (
        hass.states.get("button.product_name_aabbccddeeff_identify").state
        == STATE_UNKNOWN
    )

    # Raise RequestError when identify is called
    api.identify.side_effect = RequestError()

    assert api.identify.call_count == 0

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            button.DOMAIN,
            button.SERVICE_PRESS,
            {"entity_id": "button.product_name_aabbccddeeff_identify"},
            blocking=True,
        )
    assert api.identify.call_count == 1


async def test_identify_press_catches_disablederror(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test button press is handled DisabledError correctly."""

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

    assert (
        hass.states.get("button.product_name_aabbccddeeff_identify").state
        == STATE_UNKNOWN
    )

    # Raise RequestError when identify is called
    api.identify.side_effect = DisabledError()

    assert api.identify.call_count == 0

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            button.DOMAIN,
            button.SERVICE_PRESS,
            {"entity_id": "button.product_name_aabbccddeeff_identify"},
            blocking=True,
        )
    assert api.identify.call_count == 1
