"""Common methods used across tests for Bond."""
from bond import BOND_DEVICE_TYPE_MOTORIZED_SHADES

from homeassistant import core
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.components.bond.utils import BondDevice
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_platform(hass: core.HomeAssistant, platform: str):
    """Set up the specified Bond platform."""
    mock_entry = MockConfigEntry(
        domain=BOND_DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.bond.PLATFORMS", [platform]):
        assert await async_setup_component(hass, BOND_DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry


async def setup_cover(hass: core.HomeAssistant, cover_name: str):
    """Set up a Bond cover with a specified name."""
    with patch(
        "homeassistant.components.bond.utils.get_bond_devices",
        return_value=[
            BondDevice(
                "device-1",
                {"name": cover_name, "type": BOND_DEVICE_TYPE_MOTORIZED_SHADES},
            )
        ],
    ):
        await setup_platform(hass, COVER_DOMAIN)
