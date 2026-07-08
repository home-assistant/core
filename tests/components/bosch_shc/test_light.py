"""Tests for the Bosch SHC light platform."""

from collections.abc import Callable
from unittest.mock import MagicMock, PropertyMock, create_autospec, patch

from boschshcpy import SHCLight, SHCLightSwitch, SHCMicromoduleDimmer
from boschshcpy.exceptions import SHCException
from boschshcpy.services_impl import PowerSwitchService
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def _find_subscribed_callback(device: MagicMock, entity_id: str) -> Callable[[], None]:
    """Return the on_state_changed callback the entity registered on setup."""
    for call in device.subscribe_callback.call_args_list:
        if call[0][0] == entity_id:
            return call[0][1]
    pytest.fail(f"No subscribe_callback registered for {entity_id}")


def _make_onoff_device(serial: str, device_id: str) -> MagicMock:
    """Build an autospecced micromodule light-attached switch device."""
    device = create_autospec(SHCLightSwitch, instance=True)
    device.serial = serial
    device.id = device_id
    device.root_device_id = "shc-test-uid"
    device.name = "Test Onoff Light"
    device.manufacturer = "Bosch"
    device.device_model = "MICROMODULE_LIGHT_ATTACHED"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    device.switchstate = PowerSwitchService.State.OFF
    return device


def _make_color_device(
    spec: type,
    serial: str,
    device_id: str,
    *,
    supports_brightness: bool = True,
    supports_color_temp: bool = False,
    supports_color_hsb: bool = False,
) -> MagicMock:
    """Build an autospecced colour/dimmable light device."""
    device = create_autospec(spec, instance=True)
    device.serial = serial
    device.id = device_id
    device.root_device_id = "shc-test-uid"
    device.name = "Test Color Light"
    device.manufacturer = "Bosch"
    device.device_model = "TEST_MODEL"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    device.binarystate = True
    device.brightness = 80
    # boschshcpy's color/min_color_temperature/max_color_temperature are
    # mireds, not Kelvin (confirmed against boschshcpy's own
    # async_set_color docstring and the mature boschshc-hass integration,
    # which converts via color_temperature_mired_to_kelvin). 250 mireds =
    # 4000K; min/max are crossed since mireds and Kelvin are inversely
    # related (smallest mired = largest Kelvin).
    device.color = 250
    device.rgb = 0
    device.min_color_temperature = 153  # -> max_color_temp_kelvin ~6535K
    device.max_color_temperature = 370  # -> min_color_temp_kelvin ~2702K
    device.supports_brightness = supports_brightness
    device.supports_color_temp = supports_color_temp
    device.supports_color_hsb = supports_color_hsb
    return device


async def _setup_light_platform(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Set up the bosch_shc config entry with only the light platform loaded."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.async_get_instance"),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.LIGHT]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Every light entity is created for a fully-featured SHC installation."""
    mock_session.device_helper.micromodule_light_attached = [
        _make_onoff_device("mla-serial", "mla-id")
    ]
    mock_session.device_helper.hue_lights = [
        _make_color_device(SHCLight, "hue-serial", "hue-id", supports_color_hsb=True)
    ]
    mock_session.device_helper.ledvance_lights = [
        _make_color_device(SHCLight, "lv-serial", "lv-id", supports_color_temp=True)
    ]
    mock_session.device_helper.micromodule_dimmers = [
        _make_color_device(SHCMicromoduleDimmer, "dim-serial", "dim-id")
    ]

    await _setup_light_platform(hass, mock_config_entry, mock_session)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_light_switches_bsm_not_double_exposed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """light_switches_bsm devices stay switch-only; light.py must not also expose them."""
    mock_session.device_helper.light_switches_bsm = [
        _make_onoff_device("bsm-serial", "bsm-id")
    ]

    await _setup_light_platform(hass, mock_config_entry, mock_session)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_onoff_light_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Turning an on/off light on and off writes switchstate."""
    device = _make_onoff_device("mla-serial", "mla-id")
    mock_session.device_helper.micromodule_light_attached = [device]

    await _setup_light_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(LIGHT_DOMAIN)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.switchstate is True

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.switchstate is False


async def test_color_light_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Turning on with a brightness converts HA's 0-255 scale to Bosch's 0-100."""
    device = _make_color_device(
        SHCLight, "lv-serial", "lv-id", supports_color_temp=True
    )
    mock_session.device_helper.ledvance_lights = [device]

    await _setup_light_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(LIGHT_DOMAIN)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert device.brightness == round(128 * 100 / 255)


async def test_color_light_mode_switches_between_color_temp_and_hs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """color_mode reflects the last write, not boschshcpy's stale rgb value.

    boschshcpy doesn't clear rgb when a color temperature is written, so
    inferring the active mode from rgb's truthiness would get stuck on HS
    forever after the first color was ever set. Regression test for that.
    """
    device = _make_color_device(
        SHCLight, "hue-serial", "hue-id", supports_color_hsb=True
    )
    mock_session.device_helper.hue_lights = [device]

    await _setup_light_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(LIGHT_DOMAIN)
    on_state_changed = _find_subscribed_callback(device, entity_id)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (30.0, 100.0)},
        blocking=True,
    )
    # This integration is push-based: nothing re-reads entity properties until
    # the (mocked) device pushes an update, so invoke the callback the entity
    # actually subscribed with, like a real device push would.
    on_state_changed()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["color_mode"] == ColorMode.HS

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    on_state_changed()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["color_mode"] == ColorMode.COLOR_TEMP
    # boschshcpy's rgb value is untouched by the color-temp write.
    assert device.rgb != 0


@pytest.mark.parametrize(
    ("supports_brightness", "supports_color_temp", "supports_color_hsb", "expected"),
    [
        pytest.param(True, False, False, ColorMode.BRIGHTNESS, id="brightness_only"),
        pytest.param(True, True, False, ColorMode.COLOR_TEMP, id="color_temp"),
        pytest.param(False, False, False, ColorMode.ONOFF, id="no_capabilities"),
    ],
)
async def test_color_light_initial_mode_from_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    supports_brightness: bool,
    supports_color_temp: bool,
    supports_color_hsb: bool,
    expected: ColorMode,
) -> None:
    """The initial color_mode is derived from the device's reported capabilities."""
    device = _make_color_device(
        SHCLight,
        "lv-serial",
        "lv-id",
        supports_brightness=supports_brightness,
        supports_color_temp=supports_color_temp,
        supports_color_hsb=supports_color_hsb,
    )
    mock_session.device_helper.ledvance_lights = [device]

    await _setup_light_platform(hass, mock_config_entry, mock_session)
    (entity_id,) = hass.states.async_entity_ids(LIGHT_DOMAIN)

    assert hass.states.get(entity_id).attributes["color_mode"] == expected


@pytest.mark.parametrize(
    (
        "device_helper_attr",
        "make_device",
        "service",
        "service_data",
        "property_name",
        "read_value",
    ),
    [
        pytest.param(
            "micromodule_light_attached",
            lambda: _make_onoff_device("mla-serial", "mla-id"),
            SERVICE_TURN_ON,
            {},
            "switchstate",
            PowerSwitchService.State.OFF,
            id="onoff_turn_on",
        ),
        pytest.param(
            "micromodule_light_attached",
            lambda: _make_onoff_device("mla-serial", "mla-id"),
            SERVICE_TURN_OFF,
            {},
            "switchstate",
            PowerSwitchService.State.OFF,
            id="onoff_turn_off",
        ),
        pytest.param(
            "ledvance_lights",
            lambda: _make_color_device(
                SHCLight, "lv-serial", "lv-id", supports_color_temp=True
            ),
            SERVICE_TURN_ON,
            {},
            "binarystate",
            False,
            id="color_turn_on",
        ),
        pytest.param(
            "ledvance_lights",
            lambda: _make_color_device(
                SHCLight, "lv-serial", "lv-id", supports_color_temp=True
            ),
            SERVICE_TURN_OFF,
            {},
            "binarystate",
            True,
            id="color_turn_off",
        ),
        pytest.param(
            "ledvance_lights",
            lambda: _make_color_device(
                SHCLight, "lv-serial", "lv-id", supports_color_temp=True
            ),
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "brightness",
            80,
            id="color_turn_on_brightness",
        ),
        pytest.param(
            "ledvance_lights",
            lambda: _make_color_device(
                SHCLight, "lv-serial", "lv-id", supports_color_temp=True
            ),
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 3000},
            "color",
            250,
            id="color_turn_on_color_temp",
        ),
        pytest.param(
            "hue_lights",
            lambda: _make_color_device(
                SHCLight, "hue-serial", "hue-id", supports_color_hsb=True
            ),
            SERVICE_TURN_ON,
            {ATTR_HS_COLOR: (30.0, 100.0)},
            "rgb",
            0,
            id="color_turn_on_hs_color",
        ),
    ],
)
async def test_light_action_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    device_helper_attr: str,
    make_device: Callable[[], MagicMock],
    service: str,
    service_data: dict[str, object],
    property_name: str,
    read_value: object,
) -> None:
    """A library error while writing a light property surfaces as a HomeAssistantError."""
    device = make_device()
    setattr(mock_session.device_helper, device_helper_attr, [device])

    def _raise_on_write(*args: object) -> object:
        if args:
            raise SHCException("Test error")
        return read_value

    with patch.object(
        type(device),
        property_name,
        PropertyMock(side_effect=_raise_on_write),
        create=True,
    ):
        await _setup_light_platform(hass, mock_config_entry, mock_session)
        (entity_id,) = hass.states.async_entity_ids(LIGHT_DOMAIN)

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id, **service_data},
                blocking=True,
            )
