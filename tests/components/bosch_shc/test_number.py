"""Tests for the Bosch SHC number platform."""

from unittest.mock import MagicMock

import pytest

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
)

from tests.common import MockConfigEntry

IMPULSE_LENGTH_ENTITY_ID = "number.relay_pulse_length"
BYPASS_TIMEOUT_ENTITY_ID = "number.shutter_contact_break_function_timeout"
POWER_THRESHOLD_ENTITY_ID = "number.smart_plug_energy_saving_power_threshold"
POWER_THRESHOLD_COMPACT_ENTITY_ID = (
    "number.smart_plug_compact_energy_saving_power_threshold"
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
    device.async_set_impulse_length.assert_awaited_once_with(25)


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
    device.async_set_bypass_timeout.assert_awaited_once_with(11)


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
    device.async_set_power_threshold.assert_awaited_once_with(20)


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
