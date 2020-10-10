"""NuHeat component tests."""
from homeassistant.components.nuheat.const import DOMAIN
from homeassistant.setup import async_setup_component

from .mocks import _get_mock_nuheat

from tests.async_mock import patch

VALID_CONFIG = {
    "nuheat": {"username": "warm", "password": "feet", "devices": "thermostat123"}
}
INVALID_CONFIG = {"nuheat": {"username": "warm", "password": "feet"}}


async def test_init_success(hass):
    """Test that we can setup with valid config."""
    mock_nuheat = _get_mock_nuheat()

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        assert await async_setup_component(hass, DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()
