"""Tests for the Hinen number platform."""

from unittest.mock import patch

from homeassistant.components.hinen.const import LOAD_FIRST_STOP_SOC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_numbers_added_correctly(hass: HomeAssistant, setup_integration) -> None:
    """Test numbers are added correctly."""

    await setup_integration()
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)

    load_first_stop_soc_entity = entity_registry.async_get(
        "number.test_hinen_device_load_first_stop_soc"
    )
    assert load_first_stop_soc_entity is not None
    assert (
        load_first_stop_soc_entity.unique_id
        == f"{load_first_stop_soc_entity.config_entry_id}_device_12345_load_first_stop_soc"
    )

    load_first_stop_soc_state = hass.states.get(
        "number.test_hinen_device_load_first_stop_soc"
    )
    assert load_first_stop_soc_state is not None
    assert load_first_stop_soc_state.state == "80"
    assert load_first_stop_soc_state.attributes.get("unit_of_measurement") == "%"


async def test_number_set_value(hass: HomeAssistant, setup_integration) -> None:
    """Test setting number values."""
    mock_hinen = await setup_integration()
    await hass.async_block_till_done()
    with patch.object(mock_hinen, "set_property") as mock_set_property:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.test_hinen_device_load_first_stop_soc", "value": 85},
            blocking=True,
        )

        mock_set_property.assert_called_once_with(
            85, "device_12345", LOAD_FIRST_STOP_SOC
        )
