"""Test the Tesla Fleet climate platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import InvalidCommand, VehicleOffline

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import (
    COMMAND_ERRORS,
    COMMAND_IGNORED_REASON,
    VEHICLE_ASLEEP,
    VEHICLE_DATA_ALT,
    VEHICLE_ONLINE,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the climate entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_climate_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
    mock_request: AsyncMock,
) -> None:
    """Tests that the climate services work."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_climate"

    # Turn On and Set Temp
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TEMPERATURE: 20,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.state == HVACMode.HEAT_COOL

    # Set Temp
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TEMPERATURE: 21,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 21

    # Set Preset
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: "keep"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == "keep"

    # Set Preset
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: "off"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == "off"

    # Turn Off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_overheat_protection_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
    mock_request: AsyncMock,
) -> None:
    """Tests that the climate overheat protection services work."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_cabin_overheat_protection"

    # Turn On and Set Low
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TEMPERATURE: 30,
            ATTR_HVAC_MODE: HVACMode.FAN_ONLY,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 30
    assert state.state == HVACMode.FAN_ONLY

    # Set Temp Medium
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TEMPERATURE: 35,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 35

    # Set Temp High
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TEMPERATURE: 40,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 40

    # Turn Off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    # Turn On
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.COOL

    # Call set temp with invalid temperature
    with pytest.raises(
        ServiceValidationError,
        match="Cabin overheat protection does not support that temperature",
    ):
        # Invalid Temp
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 34},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the climate entity is correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_offline(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the climate entity is correct."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_invalid_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests service error is handled."""

    await setup_platform(hass, normal_config_entry, platforms=[Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with (
        patch(
            "homeassistant.components.tesla_fleet.VehicleSpecific.auto_conditioning_start",
            side_effect=InvalidCommand,
        ) as mock_on,
        pytest.raises(
            HomeAssistantError,
            match="Command failed: The data request or command is unknown.",
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_on.assert_called_once()


@pytest.mark.parametrize("response", COMMAND_ERRORS)
async def test_errors(
    hass: HomeAssistant, response: str, normal_config_entry: MockConfigEntry
) -> None:
    """Tests service reason is handled."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with (
        patch(
            "homeassistant.components.tesla_fleet.VehicleSpecific.auto_conditioning_start",
            return_value=response,
        ) as mock_on,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_on.assert_called_once()


async def test_ignored_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests ignored error is handled."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_climate"
    with patch(
        "homeassistant.components.tesla_fleet.VehicleSpecific.auto_conditioning_start",
        return_value=COMMAND_IGNORED_REASON,
    ) as mock_on:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_on.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_asleep_or_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_wake_up: AsyncMock,
    mock_vehicle_state: AsyncMock,
    freezer: FrozenDateTimeFactory,
    normal_config_entry: MockConfigEntry,
    mock_request: AsyncMock,
) -> None:
    """Tests asleep is handled."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_climate"
    mock_vehicle_data.assert_called_once()

    # Put the vehicle alseep
    mock_vehicle_data.reset_mock()
    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_vehicle_data.assert_called_once()
    mock_wake_up.reset_mock()

    # Run a command but fail trying to wake up the vehicle
    mock_wake_up.side_effect = InvalidCommand
    with pytest.raises(
        HomeAssistantError, match="The data request or command is unknown."
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_wake_up.assert_called_once()

    mock_wake_up.side_effect = None
    mock_wake_up.reset_mock()

    # Run a command but timeout trying to wake up the vehicle
    mock_wake_up.return_value = VEHICLE_ASLEEP
    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    with (
        patch("homeassistant.components.tesla_fleet.helpers.asyncio.sleep"),
        pytest.raises(HomeAssistantError, match="Could not wake up vehicle"),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_wake_up.assert_called_once()
    mock_vehicle_state.assert_called()

    mock_wake_up.reset_mock()
    mock_vehicle_state.reset_mock()
    mock_wake_up.return_value = VEHICLE_ONLINE
    mock_vehicle_state.return_value = VEHICLE_ONLINE

    # Run a command and wake up the vehicle immediately
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: [entity_id]}, blocking=True
    )
    await hass.async_block_till_done()
    mock_wake_up.assert_called_once()


async def test_climate_noscope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests with no command scopes."""
    await setup_platform(hass, readonly_config_entry, [Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with pytest.raises(
        ServiceValidationError, match="Climate mode off is not supported"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="Entity climate.test_climate does not support this service.",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 20},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "low", "high"),
    [
        ("climate.test_climate", 16, 28),
        ("climate.test_cabin_overheat_protection", 30, 40),
    ],
)
async def test_climate_notemp(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_id: str,
    high: int,
    low: int,
) -> None:
    """Tests that set temp fails without a temp attribute."""

    await setup_platform(hass, normal_config_entry, [Platform.CLIMATE])

    with pytest.raises(
        ServiceValidationError,
        match="Set temperature action was used with the target temperature low/high parameter but the entity does not support it",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: [entity_id],
                ATTR_TARGET_TEMP_HIGH: high,
                ATTR_TARGET_TEMP_LOW: low,
            },
            blocking=True,
        )
