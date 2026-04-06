"""Tests for the Compit select platform."""

from typing import Any
from unittest.mock import MagicMock

from compit_inext_api.consts import CompitParameter
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_select_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for select entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize(
    "mock_return_value",
    [
        None,
        1,
        "invalid",
    ],
)
async def test_select_unknown_device_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any,
) -> None:
    """Test that select entity shows unknown when get_current_option returns various invalid values."""
    mock_connector.get_current_option.side_effect = lambda device_id, parameter_code: (
        mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.nano_color_2_language")
    assert state is not None
    assert state.state == "unknown"


async def test_select_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test selecting an option."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.nano_color_2_language", "option": "polish"},
        blocking=True,
    )

    mock_connector.select_device_option.assert_called_once()
    assert mock_connector.get_current_option(2, CompitParameter.LANGUAGE) == "polish"


async def test_select_invalid_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test selecting an invalid option."""

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match=r"Option invalid is not valid for entity select\.nano_color_2_language",
    ):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.nano_color_2_language", "option": "invalid"},
            blocking=True,
        )

    mock_connector.select_device_option.assert_not_called()
