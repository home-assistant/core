"""Tests for the Bosch SHC number platform."""

from unittest.mock import MagicMock

from boschshcpy import SHCRoomThermostat2, SHCWallThermostat
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import (
    micromodule_relay_device,
    setup_integration,
    shutter_contact2_device,
    smart_plug_compact_device,
    smart_plug_device,
    thermostat_device,
    thermostat_gen2_device,
)

OFFSET_ENTITY_ID = "number.thermostat_temperature_offset"
IMPULSE_LENGTH_ENTITY_ID = "number.relay_pulse_length"
BYPASS_TIMEOUT_ENTITY_ID = "number.shutter_contact_break_function_timeout"
POWER_THRESHOLD_ENTITY_ID = "number.smart_plug_energy_saving_power_threshold"
POWER_THRESHOLD_COMPACT_ENTITY_ID = (
    "number.smart_plug_compact_energy_saving_power_threshold"
)
LED_BRIGHTNESS_ENTITY_ID = "number.smart_plug_led_brightness"
LED_BRIGHTNESS_COMPACT_ENTITY_ID = "number.smart_plug_compact_led_brightness"
DISPLAY_BRIGHTNESS_ENTITY_ID = "number.thermostat_gen2_display_brightness"
DISPLAY_ON_TIME_ENTITY_ID = "number.thermostat_gen2_display_on_time"
ENTER_DURATION_ENTITY_ID = "number.smart_plug_energy_saving_enter_duration"
ENTER_DURATION_COMPACT_ENTITY_ID = (
    "number.smart_plug_compact_energy_saving_enter_duration"
)


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_impulse_relays": [micromodule_relay_device(impulse_length=50)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_impulse_relay_impulse_length_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The impulse length is reported, converted from tenths of a second."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(IMPULSE_LENGTH_ENTITY_ID)
    assert state is not None
    assert state.state == "5.0"


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_impulse_relays": [micromodule_relay_device(impulse_length=50)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_impulse_relay_impulse_length_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes it to the device, converted to tenths of a second."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_impulse_relays[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: IMPULSE_LENGTH_ENTITY_ID, ATTR_VALUE: 2.5},
        blocking=True,
    )
    assert device.impulse_length == 25


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_impulse_relays": [micromodule_relay_device(impulse_length=None)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_impulse_relay_no_impulse_length_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No number entity is created for a relay without impulse-length support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(IMPULSE_LENGTH_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_impulse_relays": [
                micromodule_relay_device(impulse_length_raises_key_error=True)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_impulse_relay_impulse_length_partial_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The entity is still created if the initial poll omits the field."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(IMPULSE_LENGTH_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device(bypass_timeout=7)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_bypass_timeout_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The bypass timeout is reported in minutes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(BYPASS_TIMEOUT_ENTITY_ID)
    assert state is not None
    assert state.state == "7.0"


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_bypass_timeout_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes the rounded minutes to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_contacts2[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: BYPASS_TIMEOUT_ENTITY_ID, ATTR_VALUE: 10.6},
        blocking=True,
    )
    device.set_bypass_configuration.assert_called_once_with(timeout=11)


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(supports_energy_saving_mode=True, power_threshold=5.0)
            ],
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    supports_energy_saving_mode=True, power_threshold=7.0
                )
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_power_threshold_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The power threshold is reported for both smart plug variants."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(POWER_THRESHOLD_ENTITY_ID)
    assert state is not None
    assert state.state == "5.0"
    state = hass.states.get(POWER_THRESHOLD_COMPACT_ENTITY_ID)
    assert state is not None
    assert state.state == "7.0"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(supports_energy_saving_mode=True, power_threshold=5.0)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_power_threshold_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes the power threshold to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_THRESHOLD_ENTITY_ID, ATTR_VALUE: 20},
        blocking=True,
    )
    assert device.power_threshold == 20


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [smart_plug_device(power_threshold=5.0)],
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    supports_energy_saving_mode=True, power_threshold=None
                )
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_no_power_threshold_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No entity is created without energy-saving or a power threshold."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(POWER_THRESHOLD_ENTITY_ID) is None
    assert hass.states.get(POWER_THRESHOLD_COMPACT_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(
                    supports_energy_saving_mode=True, enter_duration_seconds=60
                )
            ],
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    supports_energy_saving_mode=True, enter_duration_seconds=120
                )
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_enter_duration_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The enter duration is reported for both smart plug variants."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTER_DURATION_ENTITY_ID)
    assert state is not None
    assert state.state == "60.0"
    state = hass.states.get(ENTER_DURATION_COMPACT_ENTITY_ID)
    assert state is not None
    assert state.state == "120.0"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(
                    supports_energy_saving_mode=True, enter_duration_seconds=60
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_enter_duration_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes the enter duration to the device."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTER_DURATION_ENTITY_ID, ATTR_VALUE: 300},
        blocking=True,
    )
    assert device.enter_duration_seconds == 300


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [smart_plug_device(enter_duration_seconds=60)],
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    supports_energy_saving_mode=True, enter_duration_seconds=None
                )
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_no_enter_duration_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No entity is created without energy-saving or an enter duration."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTER_DURATION_ENTITY_ID) is None
    assert hass.states.get(ENTER_DURATION_COMPACT_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(offset=1.5)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_offset_value_and_bounds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The offset and the bounds reported by the device are exposed."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(OFFSET_ENTITY_ID)
    assert state is not None
    assert state.state == "1.5"
    assert state.attributes["min"] == -5.0
    assert state.attributes["max"] == 5.0
    assert state.attributes["step"] == 0.5


@pytest.mark.parametrize(
    "device_buckets",
    [
        {"thermostats": [thermostat_device(offset=1.0, step_size=0.0)]},
        {"thermostats": [thermostat_device(offset=1.0, step_size=-1.0)]},
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_offset_non_positive_step_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-positive device step size falls back to 0.5."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(OFFSET_ENTITY_ID)
    assert state is not None
    assert state.attributes["step"] == 0.5


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(offset=0.0)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_offset_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes it to the thermostat."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: OFFSET_ENTITY_ID, ATTR_VALUE: -2.5},
        blocking=True,
    )
    assert device.offset == -2.5


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_offset_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No number is created without temperature offset support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(OFFSET_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("device_buckets", "entity_id"),
    [
        (
            {
                "wallthermostats": [
                    thermostat_device(offset=1.0, spec=SHCWallThermostat)
                ]
            },
            OFFSET_ENTITY_ID,
        ),
        (
            {
                "roomthermostats": [
                    thermostat_device(offset=1.0, spec=SHCRoomThermostat2)
                ]
            },
            OFFSET_ENTITY_ID,
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_other_thermostat_families_offset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Wall Thermostat and Room Thermostat II also get the offset number."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1.0"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [smart_plug_device(led_brightness=70)],
            "smart_plugs_compact": [smart_plug_compact_device(led_brightness=20)],
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_led_brightness_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The LED brightness of both plug types is exposed."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LED_BRIGHTNESS_ENTITY_ID)
    assert state is not None
    assert state.state == "70"
    state = hass.states.get(LED_BRIGHTNESS_COMPACT_ENTITY_ID)
    assert state is not None
    assert state.state == "20"


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [smart_plug_device(led_brightness=70)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_led_brightness_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes it to the plug."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: LED_BRIGHTNESS_ENTITY_ID, ATTR_VALUE: 35},
        blocking=True,
    )
    assert device.led_brightness == 35


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [smart_plug_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_no_led_brightness_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No entity is created without LED brightness support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(LED_BRIGHTNESS_ENTITY_ID) is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    supports_display_configuration=True,
                    display_brightness=60,
                    display_on_time=30,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_gen2_display_numbers_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The display brightness and on time are exposed."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DISPLAY_BRIGHTNESS_ENTITY_ID)
    assert state is not None
    assert state.state == "60"
    state = hass.states.get(DISPLAY_ON_TIME_ENTITY_ID)
    assert state is not None
    assert state.state == "30"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "roomthermostats": [
                thermostat_gen2_device(
                    device_id="hdm:ZigBee:roomthermostat2_1",
                    name="Room Thermostat 2",
                    supports_display_configuration=True,
                    display_brightness=10,
                    display_on_time=5,
                    spec=SHCRoomThermostat2,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_room_thermostat2_display_numbers_set_value(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting a value writes it to the room thermostat."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.roomthermostats[0]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.room_thermostat_2_display_brightness",
            ATTR_VALUE: 80,
        },
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.room_thermostat_2_display_on_time",
            ATTR_VALUE: 120,
        },
        blocking=True,
    )
    assert device.display_brightness == 80
    assert device.display_on_time == 120


@pytest.mark.parametrize(
    ("device_buckets", "brightness_present", "on_time_present"),
    [
        (
            {
                "thermostats": [
                    thermostat_gen2_device(supports_display_configuration=False)
                ]
            },
            False,
            False,
        ),
        (
            {
                "thermostats": [
                    thermostat_gen2_device(
                        supports_display_configuration=True, display_brightness=40
                    )
                ]
            },
            True,
            False,
        ),
        (
            {
                "thermostats": [
                    thermostat_gen2_device(
                        supports_display_configuration=True, display_on_time=20
                    )
                ]
            },
            False,
            True,
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_gen2_display_numbers_partial_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    brightness_present: bool,
    on_time_present: bool,
) -> None:
    """Each display number exists only when its own value is available."""
    await setup_integration(hass, mock_config_entry)

    assert (hass.states.get(DISPLAY_BRIGHTNESS_ENTITY_ID) is not None) is (
        brightness_present
    )
    assert (hass.states.get(DISPLAY_ON_TIME_ENTITY_ID) is not None) is on_time_present
