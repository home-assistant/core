"""Test Volvo sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import (
    VolvoCarsErrorResult,
    VolvoCarsValue,
    VolvoCarsValueField,
)

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    [
        "ex30_2024",
        "s90_diesel_2018",
        "xc40_electric_2024",
        "xc60_phev_2020",
        "xc90_petrol_2019",
        "xc90_phev_2024",
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


@pytest.mark.usefixtures("mock_api", "full_model")
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


@pytest.mark.usefixtures("mock_api", "full_model")
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


@pytest.mark.usefixtures("mock_api", "full_model")
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


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    [
        "ex30_2024",
        "s90_diesel_2018",
        "xc40_electric_2024",
        "xc60_phev_2020",
        "xc90_petrol_2019",
        "xc90_phev_2024",
    ],
)
async def test_unique_ids(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sensor for unique id's."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    assert f"Platform {DOMAIN} does not generate unique IDs" not in caplog.text


async def test_availability_status_reason(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test availability_status entity returns unavailable reason."""

    mock_method: AsyncMock = mock_api.async_get_command_accessibility
    mock_method.return_value["availabilityStatus"] = VolvoCarsValue(
        value="UNAVAILABLE", extra_data={"unavailable_reason": "no_internet"}
    )

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    state = hass.states.get("sensor.volvo_xc40_car_connection")
    assert state.state == "no_internet"


async def test_time_to_service_non_value_field(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test time_to_service entity with non-VolvoCarsValueField returns 0."""

    mock_method: AsyncMock = mock_api.async_get_diagnostics
    mock_method.return_value["timeToService"] = VolvoCarsErrorResult(message="invalid")

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    state = hass.states.get("sensor.volvo_xc40_time_to_service")
    assert state.state == "0"


async def test_time_to_service_months_conversion(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test time_to_service entity converts months to days."""

    mock_method: AsyncMock = mock_api.async_get_diagnostics
    mock_method.return_value["timeToService"] = VolvoCarsValueField(
        value=3, unit="months"
    )

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    state = hass.states.get("sensor.volvo_xc40_time_to_service")
    assert state.state == "90"


async def test_charging_power_value_fallback(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test charging_power entity returns 0 for invalid field types."""

    mock_method: AsyncMock = mock_api.async_get_energy_state
    mock_method.return_value["chargingPower"] = VolvoCarsErrorResult(message="invalid")

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    state = hass.states.get("sensor.volvo_xc40_charging_power")
    assert state.state == "0"


async def test_charging_power_status_unknown_value(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test charging_power_status entity with unknown status logs warning."""

    mock_method: AsyncMock = mock_api.async_get_energy_state
    mock_method.return_value["chargerPowerStatus"] = VolvoCarsValue(
        value="unknown_status"
    )

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await setup_integration()

    state = hass.states.get("sensor.volvo_xc40_charging_power_status")
    assert state.state == STATE_UNKNOWN
    assert "Unknown value 'unknown_status' for charging_power_status" in caplog.text
