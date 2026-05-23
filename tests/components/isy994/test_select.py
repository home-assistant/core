"""Test the ISY994 select platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.isy994.const import UOM_INDEX
from homeassistant.components.isy994.select import (
    ISYAuxControlIndexSelectEntity,
    async_setup_entry,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def test_setup_entry_index_uom_creates_entity_with_options(
    hass: HomeAssistant,
) -> None:
    """Test that an aux control with UOM_INDEX creates an entity with correct options."""
    control = "ST"
    fake_options = {"0": "Off", "1": "On"}

    mock_prop = MagicMock()
    mock_prop.uom = UOM_INDEX

    node = MagicMock()
    node.address = "test_addr"
    node.primary_node = "test_addr"
    node.name = "Test Node"
    node.uom = UOM_INDEX
    node.aux_properties = {control: mock_prop}

    mock_isy_data = MagicMock()
    mock_isy_data.aux_properties = {Platform.SELECT: [(node, control)]}
    mock_isy_data.devices = {}
    mock_isy_data.uid_base.return_value = "uuid_test_addr"

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_isy_data

    add_entities = MagicMock()

    with patch(
        "homeassistant.components.isy994.select.UOM_TO_STATES",
        {UOM_INDEX: fake_options},
    ):
        await async_setup_entry(hass, mock_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], ISYAuxControlIndexSelectEntity)
    assert entities[0].entity_description.options == list(fake_options.values())
