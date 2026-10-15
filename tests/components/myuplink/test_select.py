"""Tests for myuplink select module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize("platforms", [(Platform.SELECT,)])

ENTITY_ID = "select.gotham_city_comfort_mode"
ENTITY_FRIENDLY_NAME = "Gotham City comfort mode"
ENTITY_UID = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-47041"
DEVICE_ID = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff"


async def test_selecting(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test select option service."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Economy"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_myuplink_client.async_set_device_points.assert_called_once()

    # Test handling of exception from API.

    mock_myuplink_client.async_set_device_points.side_effect = ClientError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Economy"},
            blocking=True,
        )
    assert mock_myuplink_client.async_set_device_points.call_count == 2


@pytest.mark.parametrize(
    "load_device_points_file",
    ["device_points_nibe_smo20.json"],
)
async def test_entity_registry_smo20(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that the entities are registered in the entity registry."""

    entry = entity_registry.async_get("select.gotham_city_all")
    assert entry.unique_id == "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff-47660"


@pytest.mark.parametrize(
    "load_device_points_file",
    ["device_points_ctc_i555.json"],
)
async def test_decimal_enum_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test select entities for enum values with decimals, as a CTC i555 reports."""
    lower_heater = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{DEVICE_ID}-61590"
    )
    upper_heater = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{DEVICE_ID}-61591"
    )
    assert lower_heater is not None
    assert upper_heater is not None

    lower_state = hass.states.get(lower_heater)
    assert lower_state.state == "3.0"
    assert lower_state.attributes[ATTR_OPTIONS] == ["0.0", "3.0"]
    assert hass.states.get(upper_heater).state == "8.7"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: upper_heater, ATTR_OPTION: "0.3"},
        blocking=True,
    )
    mock_myuplink_client.async_set_device_points.assert_called_once_with(
        DEVICE_ID, data={"61591": "0.3"}
    )


async def test_select_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test select entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
