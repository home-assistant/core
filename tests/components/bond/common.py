"""Common methods used across tests for Bond."""
from typing import Any, Dict

from homeassistant import core
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_HUB_VERSION: dict = {"bondid": "test-bond-id"}


async def setup_bond_entity(
    hass: core.HomeAssistant, config_entry: MockConfigEntry, hub_version=None
):
    """Set up Bond entity."""
    if hub_version is None:
        hub_version = MOCK_HUB_VERSION

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bond.Bond.getVersion", return_value=hub_version
    ):
        return await hass.config_entries.async_setup(config_entry.entry_id)


async def setup_platform(
    hass: core.HomeAssistant,
    platform: str,
    discovered_device: Dict[str, Any],
    bond_device_id: str = "bond-device-id",
    props: Dict[str, Any] = None,
):
    """Set up the specified Bond platform."""
    if not props:
        props = {}

    mock_entry = MockConfigEntry(
        domain=BOND_DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.bond.PLATFORMS", [platform]), patch(
        "homeassistant.components.bond.Bond.getVersion", return_value=MOCK_HUB_VERSION
    ), patch(
        "homeassistant.components.bond.Bond.getDeviceIds",
        return_value=[bond_device_id],
    ), patch(
        "homeassistant.components.bond.Bond.getDevice", return_value=discovered_device
    ), patch(
        "homeassistant.components.bond.Bond.getDeviceState", return_value={}
    ), patch(
        "homeassistant.components.bond.Bond.getProperties", return_value=props
    ):
        assert await async_setup_component(hass, BOND_DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry
