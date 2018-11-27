"""The test for the Melissa Climate component."""
from tests.common import MockDependency, mock_coro_func

from homeassistant.components import melissa

VALID_CONFIG = {
    "melissa": {
        "username": "********",
        "password": "********",
    }
}


async def test_setup(hass):
    """Test setting up the Melissa component."""
    with MockDependency('melissa') as mocked_melissa:
        mocked_melissa.AsyncMelissa().async_connect = mock_coro_func()
        await melissa.async_setup(hass, VALID_CONFIG)

        mocked_melissa.AsyncMelissa.assert_called_with(
            username="********", password="********")

        assert melissa.DATA_MELISSA in hass.data
        assert isinstance(hass.data[melissa.DATA_MELISSA], type(
                mocked_melissa.AsyncMelissa()))
