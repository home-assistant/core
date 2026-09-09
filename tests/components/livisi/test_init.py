"""Test the LIVISI Smart Home integration setup."""

import asyncio
from dataclasses import replace
from unittest.mock import MagicMock, call, patch

from livisi import (
    LIVISI_EVENT_STATE_CHANGED,
    LivisiConnection,
    LivisiController,
    LivisiDevice,
    LivisiException,
    LivisiWebsocketEvent,
)
import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.livisi.const import DOMAIN, ON_STATE
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import CONTROLLER, VALID_CONFIG

from tests.common import MockConfigEntry


def _device(
    device_id: str,
    device_type: str,
    name: str,
    capabilities: dict[str, str],
    *,
    tags: dict[str, str] | None = None,
    capability_config: dict[str, dict] | None = None,
) -> LivisiDevice:
    """Create a LIVISI device."""
    return LivisiDevice(
        id=device_id,
        type=device_type,
        tags=tags or {},
        config={"name": name},
        state={},
        manufacturer="LIVISI",
        version="1.0",
        cls="",
        product="",
        desc="",
        capabilities=capabilities,
        capability_config=capability_config or {},
        room="Living room",
        battery_low=False,
        update_available=False,
        updated=False,
        unreachable=False,
    )


DEVICES = [
    _device(
        "window-device",
        "WDS",
        "Window",
        {"WindowDoorSensor": "window-capability"},
        tags={"typeCategory": "TCDoorId"},
    ),
    _device(
        "switch-device",
        "PSS",
        "Socket",
        {"SwitchActuator": "switch-capability"},
    ),
    _device(
        "climate-device",
        "VRCC",
        "Climate",
        {
            "RoomSetpoint": "setpoint-capability",
            "RoomTemperature": "temperature-capability",
            "RoomHumidity": "humidity-capability",
        },
        capability_config={
            "RoomSetpoint": {"minTemperature": 6.0, "maxTemperature": 30.0}
        },
    ),
]

VALUES = {
    ("window-capability", "isOpen"): False,
    ("switch-capability", ON_STATE): True,
    ("setpoint-capability", "pointTemperature"): 21.0,
    ("setpoint-capability", "setpointTemperature"): 21.0,
    ("temperature-capability", "temperature"): 20.0,
    ("humidity-capability", "humidity"): 45,
}


@pytest.mark.parametrize(
    ("controller", "target_temperature_property"),
    [
        pytest.param(CONTROLLER, "pointTemperature", id="classic"),
        pytest.param(
            replace(CONTROLLER, controller_type="Avatar", is_v1=False, is_v2=True),
            "setpointTemperature",
            id="avatar",
        ),
    ],
)
async def test_setup_entities_and_unload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: LivisiController,
    target_temperature_property: str,
) -> None:
    """Test setup with the LIVISI 1.0 API and unload cleanup."""
    listener_started = asyncio.Event()

    def get_value(capability: str, property_name: str) -> bool | float | int:
        return VALUES[(capability, property_name)]

    async def listen_for_events(*_args: object) -> None:
        listener_started.set()
        await asyncio.Future()

    connection = MagicMock(spec=LivisiConnection)
    connection.controller = controller
    connection.async_get_devices.return_value = DEVICES
    connection.async_get_value.side_effect = get_value
    connection.async_set_state.return_value = True
    connection.listen_for_events.side_effect = listen_for_events

    config_entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.livisi.coordinator.livisi_connect",
        return_value=connection,
    ) as connect:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    connect.assert_awaited_once_with("1.1.1.1", "test")

    binary_sensor_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, "window-device"
    )
    switch_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, "switch-device"
    )
    climate_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "climate-device"
    )
    assert binary_sensor_id is not None
    assert switch_id is not None
    assert climate_id is not None
    assert hass.states.is_state(binary_sensor_id, STATE_OFF)
    assert hass.states.is_state(switch_id, STATE_ON)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_id},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: climate_id, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )
    connection.async_set_state.assert_has_awaits(
        [
            call("switch-capability", key=ON_STATE, value=False),
            call(
                "setpoint-capability",
                key=target_temperature_property,
                value=22.0,
            ),
        ]
    )

    async with asyncio.timeout(1):
        await listener_started.wait()
    on_data = connection.listen_for_events.await_args.args[0]

    connection.async_get_devices.return_value = [
        replace(device, unreachable=device.id == "switch-device") for device in DEVICES
    ]
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    connection.async_get_devices.return_value = []
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    connection.async_get_devices.return_value = DEVICES
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_ON)

    on_data(
        LivisiWebsocketEvent(
            namespace="core.RWE",
            type=LIVISI_EVENT_STATE_CHANGED,
            source="switch-capability",
            timestamp=None,
            properties={ON_STATE: False},
        )
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_OFF)

    on_close = connection.listen_for_events.await_args.args[1]
    await on_close()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_OFF)

    on_data(
        LivisiWebsocketEvent(
            namespace="core.RWE",
            type=LIVISI_EVENT_STATE_CHANGED,
            source="switch-device",
            timestamp=None,
            properties={"isReachable": False},
        )
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    on_data(
        LivisiWebsocketEvent(
            namespace="core.RWE",
            type=LIVISI_EVENT_STATE_CHANGED,
            source="climate-device",
            timestamp=None,
            properties={"isReachable": False},
        )
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(climate_id, STATE_UNAVAILABLE)

    on_data(
        LivisiWebsocketEvent(
            namespace="core.RWE",
            type=LIVISI_EVENT_STATE_CHANGED,
            source="temperature-capability",
            timestamp=None,
            properties={"temperature": 20.5},
        )
    )
    await hass.async_block_till_done()
    assert not hass.states.is_state(climate_id, STATE_UNAVAILABLE)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    connection.close.assert_awaited_once_with()


async def test_state_read_failure_keeps_entity_unavailable(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a failed recovery state read keeps the entity unavailable."""
    connection = MagicMock(spec=LivisiConnection)
    connection.controller = CONTROLLER
    connection.async_get_devices.return_value = [DEVICES[1]]
    connection.async_get_value.return_value = True

    config_entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.livisi.coordinator.livisi_connect",
        return_value=connection,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    switch_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, "switch-device"
    )
    assert switch_id is not None
    assert hass.states.is_state(switch_id, STATE_ON)

    connection.async_get_devices.return_value = [replace(DEVICES[1], unreachable=True)]
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    connection.async_get_devices.return_value = [DEVICES[1]]
    connection.async_get_value.side_effect = LivisiException
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    connection.async_get_value.side_effect = None
    connection.async_get_value.return_value = True
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_ON)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_new_unreachable_event_wins_over_recovery(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a stale recovery cannot override a newer unreachable event."""
    recovery_started = asyncio.Event()
    finish_recovery = asyncio.Event()

    connection = MagicMock(spec=LivisiConnection)
    connection.controller = CONTROLLER
    connection.async_get_devices.return_value = [DEVICES[1]]
    connection.async_get_value.return_value = True

    config_entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.livisi.coordinator.livisi_connect",
        return_value=connection,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    switch_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, "switch-device"
    )
    assert switch_id is not None

    connection.async_get_devices.return_value = [replace(DEVICES[1], unreachable=True)]
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    async def delayed_get_value(capability: str, property_name: str) -> bool:
        recovery_started.set()
        await finish_recovery.wait()
        return True

    connection.async_get_value.side_effect = delayed_get_value
    connection.async_get_devices.return_value = [DEVICES[1]]
    await config_entry.runtime_data.async_refresh()
    await recovery_started.wait()

    config_entry.runtime_data.on_data(
        LivisiWebsocketEvent(
            namespace="core.RWE",
            type=LIVISI_EVENT_STATE_CHANGED,
            source="switch-device",
            timestamp=None,
            properties={"isReachable": False},
        )
    )
    await asyncio.sleep(0)
    finish_recovery.set()
    await hass.async_block_till_done()
    assert hass.states.is_state(switch_id, STATE_UNAVAILABLE)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_unreachable_devices_ignore_cached_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test cached state does not make unreachable devices available."""
    connection = MagicMock(spec=LivisiConnection)
    connection.controller = CONTROLLER
    connection.async_get_devices.return_value = [
        replace(device, unreachable=True) for device in DEVICES
    ]

    def get_value(capability: str, property_name: str) -> bool | float | int:
        return VALUES[(capability, property_name)]

    connection.async_get_value.side_effect = get_value

    config_entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.livisi.coordinator.livisi_connect",
        return_value=connection,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    for platform, unique_id in (
        (Platform.BINARY_SENSOR, "window-device"),
        (Platform.SWITCH, "switch-device"),
        (Platform.CLIMATE, "climate-device"),
    ):
        entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
        assert entity_id is not None
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
