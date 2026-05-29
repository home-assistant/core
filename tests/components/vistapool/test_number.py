"""Tests for the Vistapool number platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def _only_number_platform() -> Generator[None]:
    """Restrict integration setup to the number platform for these tests."""
    with patch("homeassistant.components.vistapool.PLATFORMS", [Platform.NUMBER]):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test number entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_scales_ph_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test pH numbers divide the stored hundredths by 100 on read."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fixture stores low/high pH as the strings "650" / "751" (hundredths).
    assert hass.states.get("number.my_pool_ph_minimum").state == "6.5"
    assert hass.states.get("number.my_pool_ph_maximum").state == "7.51"


async def test_number_scales_electrolysis_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test electrolysis setpoint divides the stored tenths by 10 on read."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"level": 50, "maxAllowedValue": 220},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.my_pool_electrolysis_setpoint").state == "5.0"


async def test_number_heating_requires_has_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test heating min/max are only created when filtration.hasHeat is set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"hasHeat": 1, "heating": {"temp": 18, "tempHi": 28}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.my_pool_heating_minimum_temperature") is not None
    assert hass.states.get("number.my_pool_heating_maximum_temperature") is not None
    assert hass.states.get("number.my_pool_smart_minimum_temperature") is None


async def test_number_smart_requires_has_smart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test smart min/max are only created when filtration.hasSmart is set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"hasSmart": 1, "smart": {"tempMin": 18, "tempHigh": 28}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.my_pool_smart_minimum_temperature") is not None
    assert hass.states.get("number.my_pool_smart_maximum_temperature") is not None
    assert hass.states.get("number.my_pool_heating_minimum_temperature") is None


@pytest.mark.parametrize(
    ("entity_id", "user_value", "expected_raw"),
    [
        pytest.param("number.my_pool_redox_setpoint", 720, 720, id="redox_unscaled"),
        pytest.param(
            "number.my_pool_ph_minimum", 7.2, 720, id="ph_minimum_scaled_x100"
        ),
        pytest.param(
            "number.my_pool_ph_maximum", 7.45, 745, id="ph_maximum_scaled_x100"
        ),
        pytest.param(
            "number.my_pool_intel_temperature", 24, 24, id="intel_temp_unscaled"
        ),
    ],
)
async def test_number_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
    entity_id: str,
    user_value: float,
    expected_raw: int,
) -> None:
    """Test set_value writes the scaled raw value to the library."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: user_value},
        blocking=True,
    )

    assert mock_vistapool_client.set_value.await_count == 1
    pool_id_arg, _path_arg, value_arg = mock_vistapool_client.set_value.await_args.args
    assert pool_id_arg == "ABCDEF1234567890"
    assert value_arg == expected_raw


async def test_number_set_value_raises_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test set_value re-raises as HomeAssistantError when the library fails."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_vistapool_client.set_value.side_effect = AquariteError("boom")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.my_pool_redox_setpoint", ATTR_VALUE: 700},
            blocking=True,
        )
