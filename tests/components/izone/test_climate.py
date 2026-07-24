"""Tests for iZone climate platform."""

import logging
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from pizone import Controller, ControllerCommandError, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.izone.const import DOMAIN
from homeassistant.components.izone.coordinator import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .conftest import create_mock_controller, create_mock_zone

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CONTROLLER_ENTITY = "climate.izone_controller_000000001"
ZONE_ENTITY = "climate.living_room"


@pytest.mark.usefixtures("init_integration")
async def test_climate_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Controller and zone climate entities are created from the coordinator."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Snapshot covers registry + state payloads; also assert the stable entity_ids
    # used by the rest of this module still resolve after setup.
    assert hass.states.get(CONTROLLER_ENTITY) is not None
    assert hass.states.get(ZONE_ENTITY) is not None


@pytest.mark.parametrize(
    "mock_controller",
    [create_mock_controller(ras_mode="RAS", zones_total=1)],
)
async def test_set_controller_temperature_ras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """RAS-mode controller accepts target temperature commands."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )

    mock_controller.set_temp_setpoint.assert_awaited_once_with(23.5)


@pytest.mark.usefixtures("init_integration")
async def test_set_controller_hvac_and_fan(
    hass: HomeAssistant,
    mock_controller: Mock,
) -> None:
    """HVAC and fan mode services call through to the controller."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_controller.set_mode.assert_awaited_once_with(Controller.Mode.HEAT)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    mock_controller.set_fan.assert_awaited_once_with(Controller.Fan.HIGH)


@pytest.mark.usefixtures("init_integration")
async def test_set_zone_mode(
    hass: HomeAssistant,
    mock_zones: list[Mock],
) -> None:
    """Zone HVAC mode changes call the zone library API."""
    zone = mock_zones[0]
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ZONE_ENTITY, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    zone.set_mode.assert_awaited_once_with(Zone.Mode.CLOSE)


@pytest.mark.parametrize(
    "mock_controller",
    [create_mock_controller(ras_mode="RAS")],
)
async def test_target_temperature_feature_ras_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """TARGET_TEMPERATURE is enabled in RAS mode."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    entity = hass.states.get(CONTROLLER_ENTITY)
    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    ("mock_controller", "mock_zones"),
    [
        (
            create_mock_controller(zone_ctrl=1, zones_total=2),
            [
                create_mock_zone(index=0, name="Living Room", temp_current=22.5),
                create_mock_zone(index=1, name="Bedroom", temp_current=None),
            ],
        )
    ],
)
async def test_target_temperature_when_zone_missing_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """TARGET_TEMPERATURE is enabled when any zone lacks a temperature sensor."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    entity = hass.states.get(CONTROLLER_ENTITY)
    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.usefixtures("init_integration")
async def test_refresh_failure_makes_entities_unavailable(
    hass: HomeAssistant,
    mock_controller: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Coordinator refresh failure marks controller and zone unavailable."""
    mock_controller.refresh_all = AsyncMock(side_effect=ConnectionError("offline"))
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(ZONE_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_soft_fault_marks_entities_unavailable_until_reconnect(
    hass: HomeAssistant,
    mock_controller: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Successful refresh with connected=False marks entities unavailable."""
    assert hass.states.get(CONTROLLER_ENTITY).state == HVACMode.COOL
    assert hass.states.get(ZONE_ENTITY).state == HVACMode.HEAT_COOL

    mock_controller.connected = False
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(ZONE_ENTITY).state == STATE_UNAVAILABLE

    mock_controller.connected = True
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTROLLER_ENTITY).state == HVACMode.COOL
    assert hass.states.get(ZONE_ENTITY).state == HVACMode.HEAT_COOL


@pytest.mark.parametrize(
    ("command_error", "expect_unavailable", "translation_key"),
    [
        pytest.param(
            ControllerCommandError("rejected"),
            False,
            "command_rejected",
            id="command_error_stays_available",
        ),
        pytest.param(
            ConnectionError("disconnected"),
            True,
            "unable_to_connect",
            id="connection_error_marks_unavailable",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_controller_command_error_handling(
    hass: HomeAssistant,
    mock_controller: Mock,
    command_error: Exception,
    expect_unavailable: bool,
    translation_key: str,
) -> None:
    """Rejected and transport failures raise HomeAssistantError; only transport clears availability."""
    assert hass.states.get(CONTROLLER_ENTITY).state == HVACMode.COOL

    mock_controller.set_fan = AsyncMock(side_effect=command_error)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    is_unavailable = hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE
    assert is_unavailable is expect_unavailable


@pytest.mark.usefixtures("init_integration")
async def test_controller_rejected_command_does_not_log_warning(
    hass: HomeAssistant,
    mock_controller: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected commands raise HomeAssistantError without a duplicate warning log."""
    mock_controller.set_fan = AsyncMock(side_effect=ControllerCommandError("rejected"))
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    assert err.value.translation_key == "command_rejected"
    assert not any(
        record.name.startswith("homeassistant.components.izone")
        for record in caplog.records
    )


@pytest.mark.parametrize(
    ("command_error", "expect_unavailable", "translation_key"),
    [
        pytest.param(
            ControllerCommandError("rejected"),
            False,
            "command_rejected",
            id="command_error_stays_available",
        ),
        pytest.param(
            ConnectionError("disconnected"),
            True,
            "unable_to_connect",
            id="connection_error_marks_unavailable",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_zone_command_error_handling(
    hass: HomeAssistant,
    mock_zones: list[Mock],
    command_error: Exception,
    expect_unavailable: bool,
    translation_key: str,
) -> None:
    """Zone command errors raise HomeAssistantError; only transport clears availability."""
    assert hass.states.get(CONTROLLER_ENTITY).state == HVACMode.COOL
    assert hass.states.get(ZONE_ENTITY) is not None

    mock_zones[0].set_mode = AsyncMock(side_effect=command_error)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ZONE_ENTITY, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert (
        hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE
    ) is expect_unavailable
    assert (
        hass.states.get(ZONE_ENTITY).state == STATE_UNAVAILABLE
    ) is expect_unavailable


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            free_air_enabled=True,
            free_air=True,
            zone_ctrl=1,
            zones_total=1,
        )
    ],
)
async def test_set_hvac_mode_free_air_noop_when_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """Free-air fan_only does not send commands when the system is already on."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    mock_controller.set_mode = AsyncMock()
    mock_controller.set_on = AsyncMock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )

    mock_controller.set_mode.assert_not_called()
    mock_controller.set_on.assert_not_called()


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            free_air_enabled=True,
            free_air=True,
            zone_ctrl=1,
            zones_total=1,
        )
    ],
)
async def test_set_hvac_mode_free_air_noop_when_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """Free-air fan_only while unavailable must not restore availability."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    mock_controller.set_fan = AsyncMock(side_effect=ConnectionError("disconnected"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_FAN_MODE: "low"},
            blocking=True,
        )
    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE

    mock_controller.set_mode = AsyncMock()
    mock_controller.set_on = AsyncMock()

    # Service calls are rejected for unavailable entities; call the entity method
    # directly so the free-air early-return path is still covered.
    entity = hass.data[CLIMATE_DOMAIN].get_entity(CONTROLLER_ENTITY)
    assert entity is not None
    await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

    mock_controller.set_mode.assert_not_called()
    mock_controller.set_on.assert_not_called()
    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            free_air_enabled=True,
            free_air=True,
            is_on=False,
            zone_ctrl=1,
            zones_total=1,
        )
    ],
)
async def test_set_hvac_mode_free_air_turns_on_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """Free-air fan_only turns the system on before skipping the mode change."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    mock_controller.set_on = AsyncMock()
    mock_controller.set_mode = AsyncMock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )

    mock_controller.set_on.assert_awaited_once_with(True)
    mock_controller.set_mode.assert_not_called()


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            free_air_enabled=True,
            free_air=True,
            zone_ctrl=1,
            zones_total=1,
        )
    ],
)
async def test_set_hvac_mode_off_while_free_air(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """Off is sent before the free-air early return."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    mock_controller.set_on = AsyncMock()
    mock_controller.set_mode = AsyncMock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    mock_controller.set_on.assert_awaited_once_with(False)
    mock_controller.set_mode.assert_not_called()


@pytest.mark.parametrize(
    "mock_controller",
    [create_mock_controller(is_on=False, zone_ctrl=1, zones_total=1)],
)
async def test_set_hvac_mode_connection_error_on_turn_on_skips_set_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    mock_controller: Mock,
    mock_zones: list[Mock],
) -> None:
    """A transport failure turning on does not continue to set_mode."""
    mock_controller.zones = mock_zones
    await setup_integration(hass, mock_config_entry)

    mock_controller.set_on = AsyncMock(side_effect=ConnectionError("disconnected"))
    mock_controller.set_mode = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    mock_controller.set_on.assert_awaited_once_with(True)
    mock_controller.set_mode.assert_not_called()
    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_command_connection_error_recovers_on_coordinator_refresh(
    hass: HomeAssistant,
    mock_controller: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities recover when a later coordinator refresh succeeds after a transport failure."""
    mock_controller.set_fan = AsyncMock(side_effect=ConnectionError("disconnected"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: CONTROLLER_ENTITY, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    assert hass.states.get(CONTROLLER_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(ZONE_ENTITY).state == STATE_UNAVAILABLE

    mock_controller.refresh_all = AsyncMock()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTROLLER_ENTITY).state == HVACMode.COOL
    assert hass.states.get(ZONE_ENTITY).state == HVACMode.HEAT_COOL
