"""Test the Teslemetry number platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import InvalidCommand
from teslemetry_stream import Signal

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.components.teslemetry.const import (
    DOMAIN,
    LABS_CHARGE_ON_SOLAR_FEATURE,
)
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_ERRORS, COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


async def _async_enable_charge_on_solar_preview_feature(hass: HomeAssistant) -> None:
    """Enable the Teslemetry charge-on-solar preview feature."""
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE, True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the number entities are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_services(
    hass: HomeAssistant, mock_vehicle_data: AsyncMock
) -> None:
    """Tests that the number services work."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.NUMBER])

    entity_id = "number.test_charge_current"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_charging_amps",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 16},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "16"
        call.assert_called_once()

    entity_id = "number.test_charge_limit"
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.set_charge_limit",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 60},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "60"
        call.assert_called_once()

    entity_id = "number.energy_site_backup_reserve"
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.backup",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 80,
            },
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "80"
        call.assert_called_once()

    entity_id = "number.energy_site_off_grid_reserve"
    with patch(
        "tesla_fleet_api.teslemetry.EnergySite.off_grid_vehicle_charging_reserve",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 88},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == "88"
        call.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("response", COMMAND_ERRORS)
async def test_number_command_errors(
    hass: HomeAssistant, mock_vehicle_data: AsyncMock, response: dict
) -> None:
    """Tests that vehicle command failures raise HomeAssistantError."""
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.NUMBER])

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.set_charging_amps",
            return_value=response,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_charge_current", ATTR_VALUE: 16},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_command_exception(hass: HomeAssistant) -> None:
    """Tests that an energy command SDK exception raises HomeAssistantError."""
    await setup_platform(hass, [Platform.NUMBER])

    with (
        patch(
            "tesla_fleet_api.teslemetry.EnergySite.backup",
            side_effect=InvalidCommand,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.energy_site_backup_reserve", ATTR_VALUE: 80},
            blocking=True,
        )


async def test_number_streaming(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the number entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.NUMBER])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.CHARGE_CURRENT_REQUEST: 24,
                Signal.CHARGE_CURRENT_REQUEST_MAX: 32,
                Signal.CHARGE_LIMIT_SOC: 99,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.NUMBER])

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("number.test_charge_current").state == "24"
    assert hass.states.get("number.test_charge_limit").state == "99"


async def test_charge_on_solar_lower_limit_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    """Test charge-on-solar lower limit is disabled by default."""
    await setup_platform(hass, [Platform.NUMBER])

    assert hass.states.get("number.test_charge_on_solar_lower_limit") is None


async def test_charge_on_solar_lower_limit_enabled_by_labs(
    hass: HomeAssistant,
) -> None:
    """Test charge-on-solar lower limit appears when Labs feature is enabled."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    await setup_platform(hass, [Platform.NUMBER])

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.state == "20"
    assert state.attributes["assumed_state"] is True


async def test_charge_on_solar_lower_limit_capped_by_charge_limit(
    hass: HomeAssistant,
) -> None:
    """Test the lower limit's max value tracks the current charge limit SOC."""
    await _async_enable_charge_on_solar_preview_feature(hass)

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc"
    ) as listener:
        listener.return_value = lambda: None
        await setup_platform(hass, [Platform.NUMBER])

        for call in listener.call_args_list:
            call.args[0](70)
        await hass.async_block_till_done()

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 70

    # A subsequent drop below the stored value clamps it down too
    for call in listener.call_args_list:
        call.args[0](10)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 10
    assert state.state == "10"


async def test_charge_on_solar_lower_limit_capped_by_charge_limit_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Test the polling lower limit's max value tracks the coordinator charge limit."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    await setup_platform(hass, [Platform.NUMBER])

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 80

    lowered_data = deepcopy(VEHICLE_DATA)
    lowered_data["response"]["charge_state"]["charge_limit_soc"] = 10
    mock_vehicle_data.return_value = lowered_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 10
    assert state.state == "10"


async def test_charge_on_solar_lower_limit_restores_max_value(
    hass: HomeAssistant,
) -> None:
    """Test the lower limit's max value survives a reload without new telemetry."""
    await _async_enable_charge_on_solar_preview_feature(hass)

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc"
    ) as listener:
        listener.return_value = lambda: None
        entry = await setup_platform(hass, [Platform.NUMBER])

        for call in listener.call_args_list:
            call.args[0](70)
        await hass.async_block_till_done()

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 70

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc",
        return_value=lambda: None,
    ):
        await reload_platform(hass, entry, [Platform.NUMBER])

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.attributes["max"] == 70


async def test_charge_on_solar_lower_limit_set_value_while_disabled(
    hass: HomeAssistant,
) -> None:
    """Test setting the lower limit while charge-on-solar is off updates state only."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    await setup_platform(hass, [Platform.NUMBER])

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_charge_on_solar_lower_limit", ATTR_VALUE: 35},
            blocking=True,
        )
        command.assert_not_called()

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.state == "35"


async def test_charge_on_solar_lower_limit_set_value_while_enabled(
    hass: HomeAssistant,
) -> None:
    """Test setting the lower limit while charge-on-solar is on sends the command."""
    await _async_enable_charge_on_solar_preview_feature(hass)

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc"
    ) as listener:
        listener.return_value = lambda: None
        await setup_platform(hass, [Platform.SWITCH, Platform.NUMBER])

        for call in listener.call_args_list:
            call.args[0](91)
        await hass.async_block_till_done()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
        return_value=COMMAND_OK,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_charge_on_solar"},
            blocking=True,
        )

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_charge_on_solar_lower_limit", ATTR_VALUE: 35},
            blocking=True,
        )
        command.assert_called_once_with(
            enabled=True,
            lower_charge_limit=35,
            upper_charge_limit=91,
        )

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.state == "35"


async def test_charge_on_solar_lower_limit_set_value_command_failure(
    hass: HomeAssistant,
) -> None:
    """Test a failed command leaves the previous value intact, not the optimistic one."""
    await _async_enable_charge_on_solar_preview_feature(hass)

    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.listen_ChargeLimitSoc"
    ) as listener:
        listener.return_value = lambda: None
        await setup_platform(hass, [Platform.SWITCH, Platform.NUMBER])

        for call in listener.call_args_list:
            call.args[0](91)
        await hass.async_block_till_done()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
        return_value=COMMAND_OK,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_charge_on_solar"},
            blocking=True,
        )

    with (
        patch(
            "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
            side_effect=InvalidCommand,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_charge_on_solar_lower_limit", ATTR_VALUE: 35},
            blocking=True,
        )

    state = hass.states.get("number.test_charge_on_solar_lower_limit")
    assert state is not None
    assert state.state == "20"


async def test_disable_charge_on_solar_preview_removes_lower_limit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling preview removes the lower limit from entity registry."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    entry = await setup_platform(hass, [Platform.NUMBER])

    assert (
        entity_registry.async_get("number.test_charge_on_solar_lower_limit") is not None
    )

    with patch.object(hass.config_entries, "async_schedule_reload"):
        await async_update_preview_feature(
            hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE, False
        )
        await hass.async_block_till_done()

    await reload_platform(hass, entry, [Platform.NUMBER])

    assert entity_registry.async_get("number.test_charge_on_solar_lower_limit") is None
