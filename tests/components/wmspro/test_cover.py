"""Test the wmspro diagnostics."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.wmspro.const import DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_cover_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
) -> None:
    """Test that a cover device is created correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) == 2

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "WebControlProAwning_58717")}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == MANUFACTURER
    assert device_entry.name == "Markise"
    assert device_entry.serial_number == 58717


async def test_cover_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
) -> None:
    """Test that a cover entity is created and updated correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) == 2

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.name == "Markise"

    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity.entity_id}, blocking=True
    )

    assert len(mock_hub_status_prod_awning.mock_calls) == 3


async def test_cover_close_and_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is opened and closed correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == "open"
    assert entity.attributes["current_position"] == 100

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await async_setup_component(hass, "cover", {})
        await hass.services.async_call(
            "cover", "close_cover", {"entity_id": entity.entity_id}, blocking=True
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == "closed"
        assert entity.attributes["current_position"] == 0
        assert len(mock_hub_status_prod_awning.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await async_setup_component(hass, "cover", {})
        await hass.services.async_call(
            "cover", "open_cover", {"entity_id": entity.entity_id}, blocking=True
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == "open"
        assert entity.attributes["current_position"] == 100
        assert len(mock_hub_status_prod_awning.mock_calls) == before


async def test_cover_move(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is moved and closed correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == "open"
    assert entity.attributes["current_position"] == 100

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await async_setup_component(hass, "cover", {})
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": entity.entity_id, "position": 50},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == "open"
        assert entity.attributes["current_position"] == 50
        assert len(mock_hub_status_prod_awning.mock_calls) == before


async def test_cover_move_and_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is moved and closed correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == "open"
    assert entity.attributes["current_position"] == 100

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await async_setup_component(hass, "cover", {})
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": entity.entity_id, "position": 80},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == "open"
        assert entity.attributes["current_position"] == 80
        assert len(mock_hub_status_prod_awning.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await async_setup_component(hass, "cover", {})
        await hass.services.async_call(
            "cover", "stop_cover", {"entity_id": entity.entity_id}, blocking=True
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == "open"
        assert entity.attributes["current_position"] == 80
        assert len(mock_hub_status_prod_awning.mock_calls) == before
