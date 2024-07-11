"""template conftest."""

import pytest

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def start_ha(
    hass: HomeAssistant, count, domain, config, caplog: pytest.LogCaptureFixture
):
    """Do setup of integration."""
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def caplog_setup_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return setup log of integration."""
    return caplog.text
