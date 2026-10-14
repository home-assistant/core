"""Test Govee light local."""

from errno import EACCES, EADDRINUSE, EADDRNOTAVAIL, EAFNOSUPPORT, ENETDOWN
from ipaddress import IPv4Network
import logging
import os
from typing import Any
from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from govee_local_api import GoveeDevice
from govee_local_api.light_capabilities import ON_OFF_CAPABILITIES
from govee_local_api.message import DevStatusResponse
import pytest

from homeassistant.components.govee_light_local.const import (
    DEVICE_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import (
    DEFAULT_CAPABILITIES,
    DISABLED_NETWORK_ADAPTERS,
    EXPECTED_LISTENING_ADDRESSES,
    SCENE_CAPABILITIES,
    setup_light,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_known_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding a known device."""
    entry, _ = await setup_light(hass, mock_govee_api)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None

    color_modes = light.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert set(color_modes) == {ColorMode.COLOR_TEMP, ColorMode.RGB}

    # Remove
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.H615A") is None


async def test_light_unknown_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding an unknown device."""
    await setup_light(
        hass,
        mock_govee_api,
        ON_OFF_CAPABILITIES,
        ip="192.168.1.101",
        fingerprint="unkown_device",
        sku="XYZK",
    )

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.XYZK")
    assert light is not None

    assert light.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_remove(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test remove device."""
    entry, _ = await setup_light(hass, mock_govee_api, fingerprint="asdawdqwdqwd1")

    assert hass.states.get("light.H615A") is not None

    # Remove 1
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_light_setup_retry(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup retry."""

    mock_govee_api.devices = []

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.govee_light_local.DISCOVERY_TIMEOUT",
        0,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("bind_errno", "expected_error"),
    [
        pytest.param(
            EADDRINUSE, "Port 4002 is already in use", id="address_already_in_use"
        ),
        pytest.param(
            EADDRNOTAVAIL,
            "Could not listen for Govee devices: Cannot assign requested address",
            id="address_unavailable",
        ),
        pytest.param(
            ENETDOWN,
            "Could not listen for Govee devices: Network is down",
            id="network_down",
        ),
    ],
)
async def test_light_setup_retry_when_no_address_binds(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    bind_errno: int,
    expected_error: str,
) -> None:
    """Test setup is retried whenever the controller binds no address at all."""

    mock_govee_api.start.side_effect = OSError(bind_errno, os.strerror(bind_errno))
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == expected_error


@pytest.mark.parametrize(
    ("bind_errno", "expected_error"),
    [
        pytest.param(
            EACCES,
            "Could not listen for Govee devices: Permission denied",
            id="permission_denied",
        ),
        pytest.param(
            EAFNOSUPPORT,
            "Could not listen for Govee devices: Address family not supported by protocol",
            id="address_family_unsupported",
        ),
    ],
)
async def test_light_setup_error_when_bind_fails_permanently(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    bind_errno: int,
    expected_error: str,
) -> None:
    """Test setup fails without retrying when the bind error cannot clear on its own."""

    mock_govee_api.start.side_effect = OSError(bind_errno, os.strerror(bind_errno))

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == expected_error


async def test_light_on_off(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test light on and then off."""
    _, device = await setup_light(hass, mock_govee_api)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": light.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"
    mock_govee_api.turn_on_off.assert_awaited_with(device, False)


@pytest.mark.parametrize(
    ("attribute", "value", "mock_call", "mock_call_args", "mock_call_kwargs"),
    [
        (
            ATTR_RGB_COLOR,
            [100, 255, 50],
            "set_color",
            [],
            {"temperature": None, "rgb": (100, 255, 50)},
        ),
        (
            ATTR_COLOR_TEMP_KELVIN,
            4400,
            "set_color",
            [],
            {"temperature": 4400, "rgb": None},
        ),
        (ATTR_EFFECT, "sunrise", "set_scene", ["sunrise"], {}),
    ],
)
async def test_turn_on_call_order(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    attribute: str,
    value: str | int | list[int],
    mock_call: str,
    mock_call_args: list[str],
    mock_call_kwargs: dict[str, Any],
) -> None:
    """Test that turn_on is called after set_brightness/set_color/set_preset."""
    _, device = await setup_light(hass, mock_govee_api, SCENE_CAPABILITIES)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS_PCT: 50, attribute: value},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_govee_api.assert_has_calls(
        [
            call.set_brightness(device, 50),
            getattr(call, mock_call)(device, *mock_call_args, **mock_call_kwargs),
            call.turn_on_off(device, True),
        ]
    )


async def test_light_brightness(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test changing brightness."""
    _, device = await setup_light(hass, mock_govee_api)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS_PCT: 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    mock_govee_api.set_brightness.assert_awaited_with(device, 50)
    assert light.attributes[ATTR_BRIGHTNESS] == 127

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.set_brightness.assert_awaited_with(device, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.set_brightness.assert_awaited_with(device, 100)


async def test_light_color(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test changing color."""
    _, device = await setup_light(hass, mock_govee_api)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_RGB_COLOR: [100, 255, 50]},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == (100, 255, 50)
    assert light.attributes[ATTR_COLOR_MODE] == ColorMode.RGB

    mock_govee_api.set_color.assert_awaited_with(
        device, rgb=(100, 255, 50), temperature=None
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_COLOR_TEMP_KELVIN: 4400},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_COLOR_TEMP_KELVIN] == 4400
    assert light.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    mock_govee_api.set_color.assert_awaited_with(device, rgb=None, temperature=4400)


async def test_scene_on(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test turning on scene."""
    _, device = await setup_light(hass, mock_govee_api, SCENE_CAPABILITIES)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)


async def test_scene_restore_rgb(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test restore rgb color."""
    _, device = await setup_light(hass, mock_govee_api, SCENE_CAPABILITIES)

    assert len(hass.states.async_all()) == 1

    initial_color = (12, 34, 56)
    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    # Set initial color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_RGB_COLOR: initial_color},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)

    # Deactivate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255


async def test_scene_restore_temperature(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test restore color temperature."""
    _, device = await setup_light(hass, mock_govee_api, SCENE_CAPABILITIES)

    assert len(hass.states.async_all()) == 1

    initial_color = 3456
    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    # Set initial color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_COLOR_TEMP_KELVIN: initial_color},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_COLOR_TEMP_KELVIN] == initial_color
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.set_scene.assert_awaited_with(device, "sunrise")

    # Deactivate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    assert light.attributes[ATTR_COLOR_TEMP_KELVIN] == initial_color


async def test_update_callback_registered_and_triggers_state_update(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test that update callback is registered and triggers state update."""
    _, device = await setup_light(hass, mock_govee_api)

    assert device.update_callback is not None

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    # Mutate device state and fire callback
    await device.turn_on()
    device.update_callback(device)
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"


async def test_update_callback_cleared_on_remove(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test that update callback is cleared when entity is removed."""
    entry, device = await setup_light(hass, mock_govee_api)

    assert device.update_callback is not None

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert device.update_callback is None


async def test_scene_none(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test turn on 'none' scene."""
    _, device = await setup_light(hass, mock_govee_api, SCENE_CAPABILITIES)

    assert len(hass.states.async_all()) == 1

    initial_color = (12, 34, 56)
    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    # Set initial color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_RGB_COLOR: initial_color},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(device, True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()
    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    mock_govee_api.set_scene.assert_not_called()


def _status_response(
    *,
    is_on: bool = False,
    brightness: int = 0,
    r: int = 0,
    g: int = 0,
    b: int = 0,
    color_temp: int = 0,
) -> DevStatusResponse:
    """Build a DevStatusResponse matching the library's wire format.

    Driving availability tests through the library's public ``device.update``
    keeps the test honest about the contract we depend on: ``lastseen`` is
    refreshed whenever a status response is applied.
    """
    return DevStatusResponse(
        {
            "onOff": 1 if is_on else 0,
            "brightness": brightness,
            "color": {"r": r, "g": g, "b": b},
            "colorTemInKelvin": color_temp,
        }
    )


async def test_device_availability(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device availability tracks lastseen against DEVICE_TIMEOUT.

    Walks the full timeline in a single fixture: stays available below the
    timeout, goes unavailable past it, and recovers when a status response
    refreshes ``lastseen``.
    """
    _, device = await setup_light(hass, mock_govee_api)

    state = hass.states.get("light.H615A")
    assert state is not None
    assert state.state == STATE_OFF

    # Advance but stay below DEVICE_TIMEOUT: the device must remain available
    # even though no status responses have arrived.
    freezer.tick(DEVICE_TIMEOUT - SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get("light.H615A")
    assert state is not None
    assert state.state == STATE_OFF

    # Advance past DEVICE_TIMEOUT: the device should go unavailable.
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get("light.H615A")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # A status response refreshes lastseen and fires the entity callback, so
    # the device recovers without waiting for another coordinator poll.
    device.update(_status_response())
    await hass.async_block_till_done()

    state = hass.states.get("light.H615A")
    assert state is not None
    assert state.state == STATE_OFF


async def test_one_silent_device_does_not_affect_others(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that one silent device does not pull the others unavailable."""
    silent = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.100",
        fingerprint="silent_device",
        sku="H615A",
        capabilities=DEFAULT_CAPABILITIES,
    )
    chatty = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.1.101",
        fingerprint="chatty_device",
        sku="H615B",
        capabilities=DEFAULT_CAPABILITIES,
    )
    mock_govee_api.devices = [silent, chatty]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Tick past the timeout, but have the chatty device reply along the way.
    freezer.tick(SCAN_INTERVAL)
    chatty.update(_status_response())
    freezer.tick(DEVICE_TIMEOUT)
    chatty.update(_status_response())

    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    silent_state = hass.states.get("light.H615A")
    chatty_state = hass.states.get("light.H615B")
    assert silent_state is not None
    assert chatty_state is not None
    assert silent_state.state == STATE_UNAVAILABLE
    assert chatty_state.state == STATE_OFF


@pytest.mark.usefixtures("mock_network_adapters")
async def test_single_controller_for_all_adapters(
    hass: HomeAssistant, mock_govee_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a single controller listens on every enabled adapter address."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.govee_light_local")

    with patch(
        "homeassistant.components.govee_light_local.coordinator.GoveeController",
        return_value=mock_govee_api,
    ) as mock_controller:
        await setup_light(hass, mock_govee_api)

    assert mock_controller.call_count == 1
    assert (
        mock_controller.call_args.kwargs["listening_addresses"]
        == EXPECTED_LISTENING_ADDRESSES
    )

    assert "Adapter eth0 (enabled): ['192.168.1.2/24', '192.168.1.2/24']" in caplog.text
    assert "Adapter eth2 (disabled): ['172.16.0.5/16']" in caplog.text
    assert "Listening on port 4002: 10.0.0.7 (10.0.0.0/8)" in caplog.text
    assert "192.168.1.2 (192.168.1.0/24)" in caplog.text


@pytest.mark.usefixtures("mock_network_adapters")
async def test_setup_with_partial_bind(
    hass: HomeAssistant, mock_govee_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup succeeds when only some of the adapter addresses bind."""

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.govee_light_local")

    # The controller drops what it could not bind, keeping both lists aligned.
    mock_govee_api.listening_addresses = ["192.168.1.2"]
    mock_govee_api.networks = [IPv4Network("192.168.1.0/24")]
    mock_govee_api.bind_failures = [
        ("10.0.0.7", OSError(EADDRNOTAVAIL, "Cannot assign requested address"))
    ]

    entry, _ = await setup_light(hass, mock_govee_api)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.H615A") is not None

    mock_govee_api.start.assert_awaited_once_with(require_all=False)
    assert "Listening on port 4002: 192.168.1.2 (192.168.1.0/24)" in caplog.text
    assert "Not listening on 10.0.0.7: Cannot assign requested address" in caplog.text


async def test_light_setup_retry_without_listening_addresses(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup is retried when no enabled adapter has an IPv4 address."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == "No enabled network adapter has an IPv4 address to listen on"
    mock_govee_api.start.assert_not_awaited()
