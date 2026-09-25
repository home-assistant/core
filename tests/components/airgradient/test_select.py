"""Tests for the AirGradient select platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from airgradient import (
    AirGradientBusyError,
    AirGradientConnectionError,
    AirGradientError,
    AirGradientForbiddenError,
    AirGradientNotSupportedError,
    ApiVersion,
    LedBarMode,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import async_load_config_fixture, load_config_fixture, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    airgradient_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setting_value(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.airgradient_configuration_source",
            ATTR_OPTION: "local",
        },
        blocking=True,
    )
    mock_airgradient_client.set_configuration_control.assert_called_once_with("local")
    assert mock_airgradient_client.get_config.call_count == 2


async def test_cloud_creates_no_number(
    hass: HomeAssistant,
    mock_cloud_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cloud configuration control."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 1

    mock_cloud_airgradient_client.get_config.return_value = (
        await async_load_config_fixture(hass, "get_config_local.json")
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 7

    mock_cloud_airgradient_client.get_config.return_value = (
        await async_load_config_fixture(hass, "get_config_cloud.json")
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1


async def test_v1_config_omission_removes_entity(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test omitted V1 fields remove their corresponding entities."""
    mock_v1_airgradient_client.get_config.return_value = load_config_fixture(
        "config_v1_local.json", ApiVersion.V1
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.airgradient_co2_automatic_baseline_duration")
    mock_v1_airgradient_client.get_config.return_value = replace(
        mock_v1_airgradient_client.get_config.return_value,
        co2_automatic_baseline_calibration_days=None,
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("select.airgradient_co2_automatic_baseline_duration") is None


@pytest.mark.parametrize(
    ("model", "entity_exists"),
    [
        pytest.param("P-1PSG", False, id="known"),
        pytest.param("P-UNKNOWN", True, id="unknown"),
    ],
)
async def test_v1_config_capabilities(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    model: str,
    entity_exists: bool,
) -> None:
    """Test known models use declarations and unknown models use payload fields."""
    mock_v1_airgradient_client.get_current_measures.return_value.model = model
    mock_v1_airgradient_client.get_config.return_value = replace(
        load_config_fixture("config_v1_local.json", ApiVersion.V1),
        led_bar_mode=LedBarMode.CO2,
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("select.airgradient_led_bar_mode") is not None
    ) is entity_exists


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_v1_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test V1 select entities."""
    mock_v1_airgradient_client.get_config.return_value = load_config_fixture(
        "config_v1_local.json", ApiVersion.V1
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.airgradient_co2_automatic_baseline_duration")
    assert state is not None
    assert state.state == "7"
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "option", "method", "expected"),
    [
        ("select.airgradient_gps_mode", "always", "set_gps_mode", "always"),
        (
            "select.airgradient_front_led_brightness",
            "bright",
            "set_front_led_brightness",
            3,
        ),
        (
            "select.airgradient_back_led_brightness",
            "dim",
            "set_back_led_brightness",
            1,
        ),
        (
            "select.airgradient_touch_led_intensity",
            "bright",
            "set_touch_led_intensity",
            2,
        ),
        (
            "select.airgradient_co2_automatic_baseline_duration",
            "0",
            "set_co2_automatic_baseline_calibration",
            0,
        ),
    ],
)
async def test_v1_select_writes(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    option: str,
    method: str,
    expected: int | str,
) -> None:
    """Test V1 select values use the documented wire values."""
    mock_v1_airgradient_client.get_config.return_value = load_config_fixture(
        "config_v1_local.json", ApiVersion.V1
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    getattr(mock_v1_airgradient_client, method).assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            AirGradientConnectionError("Something happened"),
            "An error occurred while communicating with the"
            " Airgradient device: Something happened",
        ),
        (
            AirGradientError("Something else happened"),
            "An unknown error occurred while communicating"
            " with the Airgradient device:"
            " Something else happened",
        ),
        (
            AirGradientForbiddenError(status=403, message="forbidden"),
            "The Airgradient device currently rejects local changes: forbidden",
        ),
        (
            AirGradientBusyError(status=503, message="busy"),
            "The Airgradient device is busy. Retry the operation later: busy",
        ),
        (
            AirGradientNotSupportedError(status=404, message="unsupported"),
            "The Airgradient device does not support this operation: unsupported",
        ),
    ],
)
async def test_exception_handling(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling."""
    await setup_integration(hass, mock_config_entry)

    mock_airgradient_client.set_configuration_control.side_effect = exception
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.airgradient_configuration_source",
                ATTR_OPTION: "local",
            },
            blocking=True,
        )
