"""Test the zwave_me removal of stale devices."""
from unittest.mock import patch

import pytest as pytest

from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, mock_device_registry

DEFAULT_DEVICE_INFO = {"device_id": "DummyDevice-1", "device_identifier": "16-23"}


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.mark.parametrize(
    "identifier,use_device",
    [
        (DEFAULT_DEVICE_INFO["device_id"], False),
        (DEFAULT_DEVICE_INFO["device_identifier"], True),
    ],
)
async def test_remove_stale_devices(
    hass: HomeAssistant, device_reg, identifier, use_device
):
    """Test removing devices with old-format ids."""
    config_entry = MockConfigEntry(
        domain="zwave_me", data={CONF_TOKEN: "test_token", CONF_URL: "http://test_test"}
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zwave_me.ZWaveMeController.async_establish_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.zwave_me.async_setup_platforms",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        if use_device:
            result = device_reg.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                connections={("mac", "12:34:56:AB:CD:EF")},
                identifiers={("zwave_me", f"{config_entry.unique_id}-{identifier}")},
            )
        else:
            result = None
    controller = hass.data["zwave_me"][config_entry.entry_id]
    controller.device_ids = {DEFAULT_DEVICE_INFO["device_id"]}
    controller.remove_stale_devices(device_reg)

    assert (
        device_reg.async_get_device(
            {
                (
                    "zwave_me",
                    f"{config_entry.unique_id}-{identifier}",
                )
            }
        )
        is result
    )
