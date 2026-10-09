"""Tests for the Vistapool switch platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def _only_switch_platform() -> Generator[None]:
    """Restrict integration setup to the switch platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test switch entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_relay_status_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test relay switches report on when the read-only status is set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "relays": {
            "relay1": {"info": {"onoff": 0, "status": 1}},
            "relay2": {"info": {"onoff": 1, "status": 0}},
            "relay3": {"info": {"onoff": 0, "status": 0}},
            "relay4": {"info": {"onoff": 0, "status": 0}},
        },
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.my_pool_relay_1").state == STATE_ON
    assert hass.states.get("switch.my_pool_relay_2").state == STATE_ON
    assert hass.states.get("switch.my_pool_relay_3").state == STATE_OFF


async def test_switch_heating_climate_requires_has_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test heating_climate is only created when filtration.hasHeat is set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"hasHeat": 1, "heating": {"clima": 0}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.my_pool_heating_climate") is not None
    assert hass.states.get("switch.my_pool_smart_mode_freeze") is None


async def test_switch_smart_mode_freeze_requires_has_smart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test smart_mode_freeze is only created when filtration.hasSmart is set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"hasSmart": 1, "smart": {"freeze": 1}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.my_pool_smart_mode_freeze").state == STATE_ON
    assert hass.states.get("switch.my_pool_heating_climate") is None


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        pytest.param(SERVICE_TURN_ON, 1, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, 0, id="turn_off"),
    ],
)
async def test_switch_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    service: str,
    expected_value: int,
) -> None:
    """Test turn_on / turn_off call the library's set_value with the right args."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.my_pool_filtration"},
        blocking=True,
    )

    mock_vistapool_client.set_value.assert_awaited_once_with(
        "ABCDEF1234567890", "filtration.status", expected_value
    )


async def test_switch_set_value_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test action raises HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.my_pool_filtration"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "set_failed"
