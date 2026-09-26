"""Tests for the MELCloud Home water heater platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aiomelcloudhome import UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.components.water_heater import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)

ENTITY_ID = "water_heater.heat_pump_hot_water"
ATW_UNIT_ID = "atw-unit-uuid-1"


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all water heater entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.WATER_HEATER],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_set_temperature(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the target tank water temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 55},
        blocking=True,
    )

    mock_melcloud_client.control_atw_unit.assert_called_once_with(
        ATW_UNIT_ID, set_tank_water_temperature=55
    )


@pytest.mark.parametrize(
    ("operation_mode", "forced_hot_water_mode"),
    [
        pytest.param(STATE_HIGH_DEMAND, True, id="high_demand"),
        pytest.param(STATE_HEAT_PUMP, False, id="heat_pump"),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    forced_hot_water_mode: bool,
) -> None:
    """Test the operation mode turns forced hot water on or off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: operation_mode},
        blocking=True,
    )

    mock_melcloud_client.control_atw_unit.assert_called_once_with(
        ATW_UNIT_ID, forced_hot_water_mode=forced_hot_water_mode
    )


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(
            SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 55}, id="set_temperature"
        ),
        pytest.param(
            SERVICE_SET_OPERATION_MODE,
            {ATTR_OPERATION_MODE: STATE_HIGH_DEMAND},
            id="set_operation_mode",
        ),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        MelCloudHomeAuthenticationError,
        MelCloudHomeConnectionError,
        MelCloudHomeTimeoutError,
    ],
)
async def test_action_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
    exception: type[Exception],
) -> None:
    """Test water heater actions raise HomeAssistantError on client errors."""
    await setup_integration(hass, mock_config_entry)
    mock_melcloud_client.control_atw_unit.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )


async def test_no_water_heater_without_hot_water(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ATW units without a hot water tank get no water heater."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    context["buildings"][0]["airToWaterUnits"][0]["capabilities"]["hasHotWater"] = False
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_capabilities_without_tank_limits(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the default limits and a half degree step from the unit capabilities."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    capabilities = context["buildings"][0]["airToWaterUnits"][0]["capabilities"]
    capabilities["minSetTankTemperature"] = None
    capabilities["maxSetTankTemperature"] = None
    capabilities["hasHalfDegrees"] = True
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_MIN_TEMP] == 43.3
    assert state.attributes[ATTR_MAX_TEMP] == 60.0
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.5


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        pytest.param("Power", "False", id="powered_off"),
        pytest.param("InStandbyMode", "True", id="standby"),
    ],
)
async def test_state_off_when_unit_off(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    setting: str,
    value: str,
) -> None:
    """Test the water heater is off when the unit is powered off or in standby."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    settings = {
        unit_setting["name"]: unit_setting
        for unit_setting in context["buildings"][0]["airToWaterUnits"][0]["settings"]
    }
    settings[setting]["value"] = value
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
