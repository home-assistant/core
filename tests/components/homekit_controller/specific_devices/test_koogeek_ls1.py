"""Make sure that existing Koogeek LS1 support isn't broken."""

import os
from datetime import timedelta
from unittest import mock

import pytest

from homekit.exceptions import AccessoryDisconnectedError, EncryptionError
import homeassistant.util.dt as dt_util
from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from tests.common import async_fire_time_changed
from tests.components.homekit_controller.common import (
    setup_accessories_from_file, setup_test_accessories, FakePairing, Helper
)

LIGHT_ON = ('lightbulb', 'on')


async def test_koogeek_ls1_setup(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    profile_path = os.path.join(os.path.dirname(__file__), 'koogeek_ls1.json')
    accessories = setup_accessories_from_file(profile_path)
    pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Assert that the entity is correctly added to the entity registry
    entry = entity_registry.async_get('light.koogeek_ls1_20833f')
    assert entry.unique_id == 'homekit-AAAA011111111111-7'

    helper = Helper(hass, 'light.koogeek_ls1_20833f', pairing, accessories[0])
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes['friendly_name'] == 'Koogeek-LS1-20833F'

    # Assert that all optional features the LS1 supports are detected
    assert state.attributes['supported_features'] == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR
    )


@pytest.mark.parametrize('failure_cls', [
    AccessoryDisconnectedError, EncryptionError
])
async def test_recover_from_failure(hass, utcnow, failure_cls):
    """
    Test that entity actually recovers from a network connection drop.

    See https://github.com/home-assistant/home-assistant/issues/18949
    """
    profile_path = os.path.join(os.path.dirname(__file__), 'koogeek_ls1.json')
    accessories = setup_accessories_from_file(profile_path)
    pairing = await setup_test_accessories(hass, accessories)

    helper = Helper(hass, 'light.koogeek_ls1_20833f', pairing, accessories[0])

    # Set light state on fake device to off
    helper.characteristics[LIGHT_ON].set_value(False)

    # Test that entity starts off in a known state
    state = await helper.poll_and_get_state()
    assert state.state == 'off'

    # Set light state on fake device to on
    helper.characteristics[LIGHT_ON].set_value(True)

    # Test that entity remains in the same state if there is a network error
    next_update = dt_util.utcnow() + timedelta(seconds=60)
    with mock.patch.object(FakePairing, 'get_characteristics') as get_char:
        get_char.side_effect = failure_cls('Disconnected')

        state = await helper.poll_and_get_state()
        assert state.state == 'off'

        get_char.assert_called_with([(1, 8), (1, 9), (1, 10), (1, 11)])

    # Test that entity changes state when network error goes away
    next_update += timedelta(seconds=60)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = await helper.poll_and_get_state()
    assert state.state == 'on'
