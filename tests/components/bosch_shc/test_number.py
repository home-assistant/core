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

from .conftest import micromodule_relay_device, setup_integration

from tests.common import MockConfigEntry

IMPULSE_LENGTH_ENTITY_ID = "number.relay_pulse_length"


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
