"""Test the Advantage Air Climate Platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from advantage_air import ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.advantage_air.climate import ADVANTAGE_AIR_MYAUTO
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import add_mock_config

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.advantage_air.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.usefixtures("mock_get")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""

    config_entry = await add_mock_config(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_get")
@pytest.mark.parametrize(
    ("entity_id", "hvac_mode"),
    [
        pytest.param("climate.myzone", HVACMode.COOL, id="main-cool"),
        pytest.param("climate.myzone", HVACMode.FAN_ONLY, id="main-fan_only"),
        pytest.param("climate.myzone", HVACMode.OFF, id="main-off"),
        pytest.param(
            "climate.myzone_zone_open_with_sensor",
            HVACMode.HEAT_COOL,
            id="zone-heat_cool",
        ),
        pytest.param(
            "climate.myzone_zone_open_with_sensor", HVACMode.OFF, id="zone-off"
        ),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_update: AsyncMock,
    entity_id: str,
    hvac_mode: HVACMode,
) -> None:
    """Test setting the HVAC mode."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    mock_update.assert_called_once()


@pytest.mark.usefixtures("mock_get")
@pytest.mark.parametrize(
    "entity_id", ["climate.myzone", "climate.myzone_zone_open_with_sensor"]
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_update: AsyncMock,
    entity_id: str,
) -> None:
    """Test setting the target temperature."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_update.assert_called_once()


@pytest.mark.usefixtures("mock_get")
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_update: AsyncMock,
    service: str,
) -> None:
    """Test turning the main entity on and off."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ["climate.myzone"]},
        blocking=True,
    )
    mock_update.assert_called_once()


@pytest.mark.usefixtures("mock_get")
async def test_set_fan_mode(hass: HomeAssistant, mock_update: AsyncMock) -> None:
    """Test setting the fan mode."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ["climate.myzone"], ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
    mock_update.assert_called_once()


@pytest.mark.usefixtures("mock_get")
async def test_set_preset_mode(
    hass: HomeAssistant, mock_update: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test setting the preset mode."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ["climate.myzone"], ATTR_PRESET_MODE: ADVANTAGE_AIR_MYAUTO},
        blocking=True,
    )
    mock_update.assert_called_once()
    assert mock_update.call_args[0][0] == snapshot


@pytest.mark.usefixtures("mock_get")
async def test_set_hvac_mode_unsupported(
    hass: HomeAssistant, mock_update: AsyncMock
) -> None:
    """Test setting an HVAC mode the main entity does not support."""

    await add_mock_config(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ["climate.myzone"], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_get")
async def test_myauto_set_temperature_range(
    hass: HomeAssistant, mock_update: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test setting the target temperature range on a MyAuto entity."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ["climate.myauto"],
            ATTR_TARGET_TEMP_LOW: 21,
            ATTR_TARGET_TEMP_HIGH: 23,
        },
        blocking=True,
    )
    mock_update.assert_called_once()
    assert mock_update.call_args[0][0] == snapshot


@pytest.mark.usefixtures("mock_get")
async def test_myauto_set_fan_mode(
    hass: HomeAssistant, mock_update: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test setting the fan mode on a MyAuto entity."""

    await add_mock_config(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ["climate.myauto"], ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )
    mock_update.assert_called_once()
    assert mock_update.call_args[0][0] == snapshot


@pytest.mark.usefixtures("mock_get")
async def test_climate_async_failed_update(
    hass: HomeAssistant,
    mock_update: AsyncMock,
) -> None:
    """Test climate change failure."""

    mock_update.side_effect = ApiError
    await add_mock_config(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ["climate.myzone"], ATTR_TEMPERATURE: 25},
            blocking=True,
        )

    mock_update.assert_called_once()
