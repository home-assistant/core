"""Make sure that existing Koogeek LS1 support isn't broken."""

from datetime import timedelta
from unittest import mock

from aiohomekit.exceptions import AccessoryDisconnectedError, EncryptionError
from aiohomekit.testing import FakePairing
import pytest

from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)

LIGHT_ON = ("lightbulb", "on")


async def test_koogeek_ls1_setup(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Assert that the entity is correctly added to the entity registry
    entry = entity_registry.async_get("light.koogeek_ls1_20833f")
    assert entry.unique_id == "homekit-AAAA011111111111-7"

    helper = Helper(
        hass, "light.koogeek_ls1_20833f", pairing, accessories[0], config_entry
    )
    state = await helper.poll_and_get_state()

    # Assert that the friendly name is detected correctly
    assert state.attributes["friendly_name"] == "Koogeek-LS1-20833F"

    # Assert that all optional features the LS1 supports are detected
    assert state.attributes["supported_features"] == (
        SUPPORT_BRIGHTNESS | SUPPORT_COLOR
    )

    device_registry = await hass.helpers.device_registry.async_get_registry()

    device = device_registry.async_get(entry.device_id)
    assert device.manufacturer == "Koogeek"
    assert device.name == "Koogeek-LS1-20833F"
    assert device.model == "LS1"
    assert device.sw_version == "2.2.15"
    assert device.via_device_id is None


@pytest.mark.parametrize("failure_cls", [AccessoryDisconnectedError, EncryptionError])
async def test_recover_from_failure(hass, utcnow, failure_cls):
    """
    Test that entity actually recovers from a network connection drop.

    See https://github.com/home-assistant/home-assistant/issues/18949
    """
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    helper = Helper(
        hass, "light.koogeek_ls1_20833f", pairing, accessories[0], config_entry
    )

    # Set light state on fake device to off
    helper.characteristics[LIGHT_ON].set_value(False)

    # Test that entity starts off in a known state
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    # Set light state on fake device to on
    helper.characteristics[LIGHT_ON].set_value(True)

    # Test that entity remains in the same state if there is a network error
    next_update = dt_util.utcnow() + timedelta(seconds=60)
    with mock.patch.object(FakePairing, "get_characteristics") as get_char:
        get_char.side_effect = failure_cls("Disconnected")

        state = await helper.poll_and_get_state()
        assert state.state == "off"

        chars = get_char.call_args[0][0]
        assert set(chars) == {(1, 8), (1, 9), (1, 10), (1, 11)}

    # Test that entity changes state when network error goes away
    next_update += timedelta(seconds=60)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = await helper.poll_and_get_state()
    assert state.state == "on"
