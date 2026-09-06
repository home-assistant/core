"""Test DROP device registry linkage."""

import pytest

from homeassistant.components.drop_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import config_entry_hub, config_entry_softener

HUB_IDENTIFIER = (DOMAIN, "DROP-1_C0FFEE_255")
SOFTENER_IDENTIFIER = (DOMAIN, "DROP-1_C0FFEE_0")


@pytest.mark.usefixtures("mqtt_mock")
async def test_sub_device_links_to_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sub-device links to its hub via via_device_id when the hub exists."""
    hub_entry = config_entry_hub()
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    softener_entry = config_entry_softener()
    softener_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(softener_entry.entry_id)
    await hass.async_block_till_done()

    hub_device = device_registry.async_get_device_by_identifier(
        HUB_IDENTIFIER, hub_entry.entry_id
    )
    assert hub_device is not None

    softener_device = device_registry.async_get_device_by_identifier(
        SOFTENER_IDENTIFIER, softener_entry.entry_id
    )
    assert softener_device is not None
    assert softener_device.via_device_id == hub_device.id


@pytest.mark.usefixtures("mqtt_mock")
async def test_sub_device_without_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sub-device set up without its hub is not linked and does not crash."""
    softener_entry = config_entry_softener()
    softener_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(softener_entry.entry_id)
    await hass.async_block_till_done()

    softener_device = device_registry.async_get_device_by_identifier(
        SOFTENER_IDENTIFIER, softener_entry.entry_id
    )
    assert softener_device is not None
    assert softener_device.via_device_id is None
