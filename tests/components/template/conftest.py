"""template conftest."""
import pytest

from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def start_ha(hass, do_count, do_domain, do_config, caplog):
    """Do setup of integration."""
    with assert_setup_component(do_count, do_domain):
        assert await async_setup_component(
            hass,
            do_domain,
            do_config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
