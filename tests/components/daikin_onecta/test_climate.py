"""Tests for the Daikin Onecta climate platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    HVACMode,
)
from homeassistant.components.daikin_onecta.climate import (
    DaikinClimate,
    async_setup_entry,
)
from homeassistant.components.daikin_onecta.const import FANMODE_FIXED
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import DOMAIN

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("last_update_success", "device_available", "management_point_exists", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_climate_availability(
    last_update_success: bool,
    device_available: bool,
    management_point_exists: bool,
    expected: bool,
) -> None:
    """Climate entities require a successful update and present management point."""
    entity = object.__new__(DaikinClimate)
    entity.coordinator = MagicMock(last_update_success=last_update_success)
    entity._device = MagicMock(available=device_available)
    entity._device.management_point.return_value = (
        MagicMock() if management_point_exists else None
    )
    entity._embedded_id = "zone"

    assert entity.available is expected


async def test_setup_adds_entities_once() -> None:
    """Add climate entities from all devices in a single call."""
    first_device = MagicMock()
    second_device = MagicMock()
    first_entities = [MagicMock()]
    second_entities = [MagicMock(), MagicMock()]
    coordinator = MagicMock(data={"first": first_device, "second": second_device})
    config_entry = MagicMock(runtime_data=coordinator)
    async_add_entities = MagicMock()

    with patch(
        "homeassistant.components.daikin_onecta.climate._create_climate_entities",
        side_effect=[first_entities, second_entities],
    ):
        await async_setup_entry(MagicMock(), config_entry, async_add_entities)

    async_add_entities.assert_called_once_with(
        [*first_entities, *second_entities], update_before_add=False
    )


async def test_set_temperature_updates_cached_setpoint_and_siblings() -> None:
    """Update the cached setpoint and notify sibling climates after a write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    coordinator = MagicMock()
    device.patch = AsyncMock(return_value=True)
    setpoint = MagicMock(value=20)
    object.__setattr__(entity, "_device", device)
    entity.coordinator = coordinator
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_target_temperature", 20)
    entity._operation_mode = MagicMock(return_value=MagicMock(value="heating"))
    entity._get_setpoint = MagicMock(return_value=setpoint)
    await entity.async_set_temperature(temperature=21)

    assert setpoint.value == 21
    entity._get_setpoint.assert_called_once_with("heating")
    coordinator.async_update_listeners.assert_called_once_with()


async def test_set_temperature_rejects_unsupported_hvac_mode() -> None:
    """Reject an unsupported HVAC mode before changing the temperature."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock()
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_modes", [HVACMode.OFF, HVACMode.COOL])
    object.__setattr__(entity, "_attr_target_temperature", 20)

    with pytest.raises(ServiceValidationError):
        await entity.async_set_temperature(hvac_mode=HVACMode.HEAT, temperature=21)

    device.patch.assert_not_awaited()


async def test_enable_boost_stops_after_failed_turn_on() -> None:
    """Do not enable boost when the prerequisite turn-on fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    device.patch = AsyncMock(return_value=True)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.async_turn_on = AsyncMock()

    assert not await entity._async_enable_preset_mode(PRESET_BOOST)

    entity.async_turn_on.assert_awaited_once()
    device.patch.assert_not_awaited()


async def test_set_hvac_mode_publishes_successful_power_write() -> None:
    """Publish a successful power write before a failed mode write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    device.patch = AsyncMock(side_effect=[True, False])
    coordinator = MagicMock()
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off"),
        operation_mode=SimpleNamespace(
            value="cooling", settable=True, values=["cooling", "heating"]
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._update_state = MagicMock()

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert err.value.translation_key == "command_failed"

    assert climate_control.on_off_mode.value == "on"
    assert climate_control.operation_mode.value == "cooling"
    entity._update_state.assert_called_once_with()
    coordinator.async_update_listeners.assert_called_once_with()


async def test_set_hvac_mode_updates_replaced_management_point() -> None:
    """Update the current model when polling replaces it during a command."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    device.patch = AsyncMock(return_value=True)
    coordinator = MagicMock()
    previous_management_point = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off"),
        operation_mode=SimpleNamespace(
            value="heating", settable=True, values=["heating", "cooling"]
        ),
    )
    current_management_point = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off"),
        operation_mode=SimpleNamespace(
            value="heating", settable=True, values=["heating", "cooling"]
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            current_management_point,
            current_management_point,
            current_management_point,
        ]
    )
    entity._update_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.COOL)

    assert previous_management_point.on_off_mode.value == "off"
    assert previous_management_point.operation_mode.value == "heating"
    assert current_management_point.on_off_mode.value == "on"
    assert current_management_point.operation_mode.value == "cooling"
    assert coordinator.async_update_listeners.call_count == 2


@pytest.mark.parametrize(
    ("native_mode", "hvac_mode"),
    [("heatingDay", HVACMode.HEAT), ("auto", HVACMode.HEAT_COOL)],
)
async def test_set_hvac_mode_preserves_matching_native_mode(
    native_mode: str, hvac_mode: HVACMode
) -> None:
    """Keep the current native mode when it already maps to the requested mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock()
    operation_mode = SimpleNamespace(
        value=native_mode, settable=True, values=[native_mode]
    )
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="on"), operation_mode=operation_mode
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", hvac_mode)
    entity._climate_control = MagicMock(return_value=climate_control)

    await entity.async_set_hvac_mode(hvac_mode)

    assert entity._get_hvac_modes() == [HVACMode.OFF, hvac_mode]
    device.patch.assert_not_awaited()


async def test_set_hvac_mode_uses_advertised_native_mode() -> None:
    """Use an advertised native mode instead of a generic Daikin value."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock(return_value=True)
    coordinator = MagicMock()
    operation_mode = SimpleNamespace(
        value="cooling", settable=True, values=["cooling", "heatingNight"]
    )
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="on"), operation_mode=operation_mode
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.COOL)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._update_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    device.patch.assert_awaited_once_with(
        "device", "zone", "operationMode", "", "heatingNight"
    )
    assert operation_mode.value == "heatingNight"


async def test_set_hvac_mode_ignores_unknown_native_mode() -> None:
    """Do not expose or overwrite a native mode without a HA equivalent."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock()
    operation_mode = SimpleNamespace(
        value="vendorMode", settable=True, values=["vendorMode"]
    )
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="on"), operation_mode=operation_mode
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_hvac_mode", None)
    entity._climate_control = MagicMock(return_value=climate_control)

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert entity._get_hvac_mode() is None
    assert entity._get_hvac_modes() == [HVACMode.OFF]
    device.patch.assert_not_awaited()


async def test_set_fan_mode_publishes_successful_fixed_mode_write() -> None:
    """Publish fixed mode when the following fan-speed write fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    device.patch = AsyncMock(side_effect=[True, False])
    coordinator = MagicMock()
    fan_speed = SimpleNamespace(
        current_mode=SimpleNamespace(value="auto"),
        modes={FANMODE_FIXED: SimpleNamespace(value=1)},
    )
    climate_control = SimpleNamespace(operation_mode=SimpleNamespace(value="heating"))
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._fan_operation = MagicMock(return_value=SimpleNamespace(fan_speed=fan_speed))
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._resolve_homekit_fan_mode_alias = MagicMock(return_value="3")
    entity._get_fan_mode = MagicMock(return_value="1")

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_fan_mode("3")

    assert err.value.translation_key == "command_failed"

    assert fan_speed.current_mode.value == FANMODE_FIXED
    assert fan_speed.modes[FANMODE_FIXED].value == 1
    coordinator.async_update_listeners.assert_called_once_with()


async def test_set_fan_mode_updates_captured_operation_mode() -> None:
    """Update the targeted fan mode when polling replaces the active mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock(return_value=True)
    coordinator = MagicMock()
    previous_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(current_mode=SimpleNamespace(value="auto"), modes={})
    )
    captured_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(current_mode=SimpleNamespace(value="auto"), modes={})
    )
    active_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(current_mode=SimpleNamespace(value="auto"), modes={})
    )
    previous_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="heating"),
        fan_control=SimpleNamespace(
            value=SimpleNamespace(operation_modes={"heating": previous_fan})
        ),
    )
    current_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="cooling"),
        fan_control=SimpleNamespace(
            value=SimpleNamespace(
                operation_modes={"heating": captured_fan, "cooling": active_fan}
            )
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            previous_management_point,
            current_management_point,
        ]
    )
    entity._resolve_homekit_fan_mode_alias = MagicMock(return_value="quiet")
    entity._get_fan_mode = MagicMock(return_value="auto")

    await entity.async_set_fan_mode("quiet")

    assert captured_fan.fan_speed.current_mode.value == "quiet"
    assert active_fan.fan_speed.current_mode.value == "auto"
    device.patch.assert_awaited_once_with(
        "device",
        "zone",
        "fanControl",
        "/operationModes/heating/fanSpeed/currentMode",
        "quiet",
    )


async def test_set_swing_mode_updates_captured_operation_mode() -> None:
    """Update the targeted swing mode when polling replaces the active mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.patch = AsyncMock(return_value=True)
    previous_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(value="stop", values=["stop", "swing"])
            )
        )
    )
    captured_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(value="stop", values=["stop", "swing"])
            )
        )
    )
    active_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(value="stop", values=["stop", "swing"])
            )
        )
    )
    previous_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="heating"),
        fan_control=SimpleNamespace(
            value=SimpleNamespace(operation_modes={"heating": previous_fan})
        ),
    )
    current_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="cooling"),
        fan_control=SimpleNamespace(
            value=SimpleNamespace(
                operation_modes={"heating": captured_fan, "cooling": active_fan}
            )
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            previous_management_point,
            current_management_point,
        ]
    )

    assert await entity._async_set_swing("vertical", "swing")

    assert captured_fan.fan_direction.vertical.current_mode.value == "swing"
    assert active_fan.fan_direction.vertical.current_mode.value == "stop"
    device.patch.assert_awaited_once_with(
        "device",
        "zone",
        "fanControl",
        "/operationModes/heating/fanDirection/vertical/currentMode",
        "swing",
    )


async def test_set_preset_mode_stops_after_failed_disable() -> None:
    """Do not enable a replacement preset when disabling the old one fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(name="Device")
    coordinator = MagicMock()
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_attr_preset_mode", PRESET_BOOST)
    entity.coordinator = coordinator
    entity._update_state = MagicMock()
    entity._async_disable_preset_mode = AsyncMock(return_value=False)
    entity._async_enable_preset_mode = AsyncMock()

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_preset_mode(PRESET_COMFORT)

    assert err.value.translation_key == "command_failed"

    entity._async_disable_preset_mode.assert_awaited_once_with(PRESET_BOOST)
    entity._async_enable_preset_mode.assert_not_awaited()
    entity._update_state.assert_not_called()
    coordinator.async_update_listeners.assert_not_called()


async def test_set_preset_mode_publishes_successful_disable() -> None:
    """Publish a successful preset disable before a replacement fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(name="Device")
    coordinator = MagicMock()
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_attr_preset_mode", PRESET_BOOST)
    entity.coordinator = coordinator
    entity._update_state = MagicMock()
    entity._async_disable_preset_mode = AsyncMock(return_value=True)
    entity._async_enable_preset_mode = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_preset_mode(PRESET_COMFORT)

    assert err.value.translation_key == "command_failed"

    entity._async_disable_preset_mode.assert_awaited_once_with(PRESET_BOOST)
    entity._async_enable_preset_mode.assert_awaited_once_with(PRESET_COMFORT)
    entity._update_state.assert_called_once_with()
    coordinator.async_update_listeners.assert_called_once_with()


@pytest.mark.parametrize("patch_result", [True, False])
async def test_climate_service_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    patch_result: bool,
) -> None:
    """Test climate services through the Home Assistant integration API."""
    setpoint = SimpleNamespace(
        value=20, min_value=7, max_value=30, step_value=1, settable=True
    )
    operation_mode = SimpleNamespace(value="heating", values=["heating"], settable=True)
    climate_control = MagicMock(embedded_id="zone")
    climate_control.temperature_control = SimpleNamespace(
        value=SimpleNamespace(
            operation_modes={
                "heating": SimpleNamespace(setpoints={"roomTemperature": setpoint})
            }
        )
    )
    climate_control.operation_mode = operation_mode
    climate_control.on_off_mode = SimpleNamespace(value="on")
    climate_control.fan_control = None
    climate_control.holiday_mode = None
    climate_control.sensory_data = None
    climate_control.characteristic.return_value = None

    device = MagicMock(id="gateway", available=True)
    device.name = "Daikin"
    device.device = SimpleNamespace(
        device_model="Daikin",
        management_points_by_type=lambda _: (climate_control,),
    )
    device.management_point.return_value = climate_control
    device.patch = AsyncMock(return_value=patch_result)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, device.id)},
        manufacturer="Daikin",
        name=device.name,
    )

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.data = {device.id: device}
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_zone_roomTemperature"
    )
    assert entity_id == "climate.daikin_room_temperature"

    service_call = hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )
    if patch_result:
        await service_call
        assert hass.states.get(entity_id).attributes[ATTR_TEMPERATURE] == 21
    else:
        with pytest.raises(HomeAssistantError, match="Failed to set the temperature"):
            await service_call

    device.patch.assert_awaited_once_with(
        "gateway",
        "zone",
        "temperatureControl",
        "/operationModes/heating/setpoints/roomTemperature",
        21,
    )


async def test_climate_platform_services_and_management_points(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test platform services with real entities for two management points."""

    def climate_control(embedded_id: str, target_temperature: int) -> SimpleNamespace:
        setpoint = SimpleNamespace(
            value=target_temperature,
            min_value=7,
            max_value=30,
            step_value=1,
            settable=True,
        )
        fan_operation = SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value="auto", values=["auto", "quiet"]),
                modes={},
            ),
            fan_direction=SimpleNamespace(
                vertical=SimpleNamespace(
                    current_mode=SimpleNamespace(value="stop", values=["stop", "swing"])
                ),
                horizontal=None,
            ),
        )
        presets = {
            "powerfulMode": SimpleNamespace(value="off"),
            "comfortMode": SimpleNamespace(value="off"),
            "econoMode": SimpleNamespace(value="off"),
        }
        return SimpleNamespace(
            embedded_id=embedded_id,
            temperature_control=SimpleNamespace(
                value=SimpleNamespace(
                    operation_modes={
                        mode: SimpleNamespace(setpoints={"roomTemperature": setpoint})
                        for mode in ("heating", "cooling")
                    }
                )
            ),
            operation_mode=SimpleNamespace(
                value="heating", values=["heating", "cooling"], settable=True
            ),
            on_off_mode=SimpleNamespace(value="on"),
            fan_control=SimpleNamespace(
                value=SimpleNamespace(
                    operation_modes={
                        "heating": fan_operation,
                        "cooling": fan_operation,
                    }
                )
            ),
            holiday_mode=SimpleNamespace(value=SimpleNamespace(enabled=False)),
            sensory_data=None,
            characteristic=presets.get,
        )

    climate_controls = {
        "living_room": climate_control("living_room", 20),
        "bedroom": climate_control("bedroom", 18),
    }
    device = MagicMock(id="gateway", available=True)
    device.name = "Daikin"
    device.device = SimpleNamespace(
        device_model="Daikin",
        management_points_by_type=lambda _: tuple(climate_controls.values()),
    )
    device.management_point.side_effect = climate_controls.get
    device.patch = AsyncMock(return_value=True)

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.data = {device.id: device}
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    living_room_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_living_room_roomTemperature"
    )
    bedroom_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_bedroom_roomTemperature"
    )
    assert living_room_entity_id is not None
    assert bedroom_entity_id is not None

    async def call_service(service: str, **service_data: str | int | HVACMode) -> None:
        """Call a climate service for the living room entity."""
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: living_room_entity_id, **service_data},
            blocking=True,
        )

    await call_service(SERVICE_SET_TEMPERATURE, temperature=21)
    await call_service(SERVICE_SET_HVAC_MODE, hvac_mode=HVACMode.COOL)
    await call_service(SERVICE_SET_FAN_MODE, fan_mode="quiet")
    await call_service(SERVICE_SET_SWING_MODE, swing_mode="swing")
    await call_service(SERVICE_SET_PRESET_MODE, preset_mode=PRESET_ECO)

    living_room_state = hass.states.get(living_room_entity_id)
    bedroom_state = hass.states.get(bedroom_entity_id)
    assert living_room_state is not None
    assert bedroom_state is not None
    assert living_room_state.state == HVACMode.COOL
    assert living_room_state.attributes[ATTR_TEMPERATURE] == 21
    assert living_room_state.attributes[ATTR_FAN_MODE] == "quiet"
    assert living_room_state.attributes[ATTR_SWING_MODE] == "swing"
    assert living_room_state.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert bedroom_state.state == HVACMode.HEAT
    assert bedroom_state.attributes[ATTR_TEMPERATURE] == 18


async def test_setup_creates_entities_per_management_point(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a separate climate entity for each climate-control zone."""
    coordinator = MagicMock()
    gateway = MagicMock(id="device", device_model="Daikin")
    onecta_device = MagicMock(id="device", device=gateway)
    coordinator.data = {"device": onecta_device}
    first_zone = MagicMock(embedded_id="first_zone")
    first_zone.temperature_control.value.operation_modes = {
        "heating": MagicMock(setpoints={"roomTemperature": MagicMock()}),
    }
    second_zone = MagicMock(embedded_id="second_zone")
    second_zone.temperature_control.value.operation_modes = {
        "cooling": MagicMock(setpoints={"roomTemperature": MagicMock()}),
    }
    gateway.management_points_by_type.return_value = (first_zone, second_zone)
    coordinator.async_config_entry_first_refresh = AsyncMock()

    class TestClimateEntity(ClimateEntity):
        """Minimal climate entity used to observe platform setup."""

        def __init__(
            self,
            device: MagicMock,
            setpoint: str,
            coordinator: MagicMock,
            embedded_id: str,
        ) -> None:
            """Initialize the test entity."""
            self._attr_unique_id = f"{device.id}_{embedded_id}_{setpoint}"
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_modes = [HVACMode.OFF]

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.daikin_onecta.climate.DaikinClimate",
            TestClimateEntity,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_first_zone_roomTemperature"
    )
    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_second_zone_roomTemperature"
    )
