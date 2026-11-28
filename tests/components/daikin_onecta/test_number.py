"""Tests for Daikin Onecta number entities."""

from daikin_onecta.exceptions import OnectaConnectionError
from daikin_onecta.models import GatewayDevice, ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN, LEAVING_WATER_OFFSET
from homeassistant.components.daikin_onecta.number import DaikinLeavingWaterOffsetNumber
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
    NumberDeviceClass,
    NumberServiceArgument,
)
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import MockOnectaClient
from .platform_helpers import (
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


def _gateway_offset_point(
    gateways: list[GatewayDevice],
) -> tuple[GatewayDevice, ManagementPoint]:
    """Return a fixture gateway and point that advertise the offset."""
    return next(
        (gateway, point)
        for gateway in gateways
        for point in gateway.management_points_by_type("climateControl")
        if point.climate_control is not None
        and LEAVING_WATER_OFFSET in point.climate_control.setpoint_types
    )


def _set_offset_operation_mode_to_heating(gateways: list[GatewayDevice]) -> None:
    """Select a fixture operation mode that advertises the offset."""
    _, point = _gateway_offset_point(gateways)
    assert point.operation_mode is not None
    point.operation_mode.value = "heating"


def _set_offset_value(gateways: list[GatewayDevice], value: int) -> None:
    """Set the current heating offset before integration setup."""
    _, point = _gateway_offset_point(gateways)
    assert point.temperature_control is not None
    point.temperature_control.value.operation_modes["heating"].setpoints[
        LEAVING_WATER_OFFSET
    ].value = value


async def _async_setup_offset_number(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    *,
    initial_value: int | None = None,
) -> tuple[str, DaikinLeavingWaterOffsetNumber]:
    """Set up a fixture and return its offset number and model."""
    gateways = _load_gateway_devices(fixture)
    _set_offset_operation_mode_to_heating(gateways)
    if initial_value is not None:
        _set_offset_value(gateways, initial_value)
    gateway, point = _gateway_offset_point(gateways)
    await _async_setup_fixture(hass, config_entry, fixture, gateway_devices=gateways)
    entity_id = entity_registry.async_get_entity_id(
        NUMBER_DOMAIN,
        DOMAIN,
        f"{gateway.id}_{point.embedded_id}_{LEAVING_WATER_OFFSET}",
    )
    assert entity_id is not None
    entity = hass.data[NUMBER_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinLeavingWaterOffsetNumber)
    return entity_id, entity


@pytest.mark.parametrize(
    ("fixture", "expected_value"),
    [
        pytest.param("altherma", 0, id="altherma"),
        pytest.param("mc80z", -3, id="mc80z"),
    ],
)
async def test_leaving_water_offset_number_uses_current_setpoint_metadata(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    expected_value: int,
) -> None:
    """Expose the current operation mode's offset value, range, and unit."""
    _, entity = await _async_setup_offset_number(
        hass, config_entry, entity_registry, fixture
    )

    assert entity.native_value == expected_value
    assert entity.native_min_value == -10
    assert entity.native_max_value == 10
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert entity.device_class is NumberDeviceClass.TEMPERATURE_DELTA


async def test_leaving_water_offset_number_writes_current_mode_and_updates_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Write a rounded offset through the climate-control client."""
    entity_id, entity = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z"
    )

    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            NumberServiceArgument.VALUE: -4.2,
        },
        blocking=True,
    )

    gateway = config_entry.runtime_data.data[entity._device_id]
    point = gateway.management_point(entity._embedded_id)
    assert point is not None
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        -4,
        path="/operationModes/heating/setpoints/leavingWaterOffset",
    )
    assert entity.native_value == -4
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "-4.0"


@pytest.mark.parametrize(
    ("requested_value", "expected_value"),
    [
        pytest.param(2.5, 3, id="round-to-step"),
        pytest.param(70, 10, id="clamp-to-maximum"),
        pytest.param(-70, -10, id="clamp-to-minimum"),
    ],
)
async def test_leaving_water_offset_number_rounds_and_clamps(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    requested_value: float,
    expected_value: int,
) -> None:
    """Round offset writes to the step and clamp them to Daikin's range."""
    _, entity = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z"
    )
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await entity.async_set_native_value(requested_value)

    assert mock_onecta_client.patch_characteristic.await_args.args[3] == expected_value
    assert isinstance(mock_onecta_client.patch_characteristic.await_args.args[3], int)


async def test_leaving_water_offset_number_skips_unchanged_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Avoid a cloud request when the current offset already matches."""
    entity_id, _ = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z", initial_value=-3
    )
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, NumberServiceArgument.VALUE: -3},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_leaving_water_offset_number_is_unavailable_when_read_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not make a read-only current-mode offset writable from Home Assistant."""
    entity_id, entity = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z"
    )
    gateway = config_entry.runtime_data.data[entity._device_id]
    point = gateway.management_point(entity._embedded_id)
    assert point is not None and point.temperature_control is not None
    point.temperature_control.value.operation_modes["heating"].setpoints[
        LEAVING_WATER_OFFSET
    ].settable = False
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None and state.state == "unavailable"
    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_native_value(2)

    assert err.value.translation_key == "climate_temperature_unavailable"
    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_leaving_water_offset_number_handles_missing_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Publish an unknown offset when Daikin omits its current value."""
    entity_id, entity = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z"
    )
    gateway = config_entry.runtime_data.data[entity._device_id]
    point = gateway.management_point(entity._embedded_id)
    assert point is not None and point.temperature_control is not None
    point.temperature_control.value.operation_modes["heating"].setpoints[
        LEAVING_WATER_OFFSET
    ].value = None
    mock_onecta_client.get_gateway_devices.return_value = [gateway.device]

    await config_entry.runtime_data.async_refresh()

    assert entity.native_value is None
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "unknown"


async def test_leaving_water_offset_number_translates_cloud_write_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Translate an API failure while changing the offset."""
    entity_id, _ = await _async_setup_offset_number(
        hass, config_entry, entity_registry, "mc80z"
    )
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure",
        method="PATCH",
        path="/v1/gateway-devices/gateway/management-points/point/characteristics/temperatureControl",
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, NumberServiceArgument.VALUE: 2},
            blocking=True,
        )

    assert err.value.translation_key == "set_temperature_failed"
