from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from homeassistant.components.omie.const import DOMAIN
from tests.common import assert_setup_component


async def test_empty_config(hass: HomeAssistant) -> None:
    """Test setup with empty configuration. """
    assert await async_setup_component(
        hass,
        DOMAIN,
        {},
    )
    assert_setup_component(0, DOMAIN)
