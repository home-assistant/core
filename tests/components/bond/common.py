"""Common methods used across tests for Bond."""
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
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
