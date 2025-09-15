"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "full_model",
    [
        "ex30_2024",
        "s90_diesel_2018",
        "xc40_electric_2024",
        "xc60_phev_2020",
        "xc90_petrol_2019",
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "full_model",
    ["xc40_electric_2024"],
)
async def test_distance_to_empty_battery(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test using `distanceToEmptyBattery` instead of `electricRange`."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    assert hass.states.get("sensor.volvo_xc40_distance_to_empty_battery").state == "250"


@pytest.mark.parametrize(
    ("full_model", "short_model"),
    [("ex30_2024", "ex30"), ("xc60_phev_2020", "xc60")],
)
async def test_skip_invalid_api_fields(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    short_model: str,
) -> None:
    """Test if invalid values are not creating a sensor."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    assert not hass.states.get(f"sensor.volvo_{short_model}_charging_current_limit")


@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024"],
)
async def test_charging_power_value(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test if charging_power_value is zero if supported, but not charging."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    assert hass.states.get("sensor.volvo_ex30_charging_power").state == "0"
