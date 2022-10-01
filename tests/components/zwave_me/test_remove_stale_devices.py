import pytest as pytest

from homeassistant.components.zwave_me import ZWaveMeController
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, mock_device_registry

DEFAULT_DEVICE_INFO = {"device_id": "DummyDevice-1", "device_identifier": "16-23"}


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def test_remove_stale_devices(hass: HomeAssistant, device_reg):
    """Test removing devices with old-format ids."""
    config_entry = MockConfigEntry(
        domain="zwave_me", data={CONF_TOKEN: "test_token", CONF_URL: "http://test_test"}
    )
    config_entry.add_to_hass(hass)
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
        identifiers={
            ("zwave_me", f"{config_entry.unique_id}-{DEFAULT_DEVICE_INFO['device_id']}")
        },
    )

    controller = ZWaveMeController(hass, config_entry)
    controller.entity_ids = {DEFAULT_DEVICE_INFO["device_id"]}
    controller.remove_stale_devices(device_reg)

    assert (
        device_reg.async_get_device(
            {
                (
                    "zwave_me",
                    f"{config_entry.unique_id}-{DEFAULT_DEVICE_INFO['device_id']}",
                )
            }
        )
        is None
    )


async def test_new_format_device_non_removal(hass: HomeAssistant, device_reg):
    """Test new format is not removed."""
    config_entry = MockConfigEntry(
        domain="zwave_me", data={CONF_TOKEN: "test_token", CONF_URL: "http://test_test"}
    )
    config_entry.add_to_hass(hass)
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
        identifiers={
            (
                "zwave_me",
                f"{config_entry.unique_id}-{DEFAULT_DEVICE_INFO['device_identifier']}",
            )
        },
    )

    controller = ZWaveMeController(hass, config_entry)
    controller.entity_ids = {"DEFAULT_DEVICE_INFO['device_id']"}
    controller.remove_stale_devices(device_reg)

    assert (
        device_reg.async_get_device(
            {
                (
                    "zwave_me",
                    f"{config_entry.unique_id}-{DEFAULT_DEVICE_INFO['device_identifier']}",
                )
            }
        )
        is not None
    )
