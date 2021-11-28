"""snmp conftest."""
import json
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
def config_addon():
    """Add entra configuration items."""
    return None


@pytest.fixture
def mock_getcmd(get_value):
    """Fixture to allow mocking the pysnmp getCmd call."""

    async def replace_with(a, b, c, d, e):
        class MockValue:
            def __init__(self, value):
                self._value = value

            def prettyPrint(self):
                return str(self._value)

        key = e._ObjectType__args[0]._ObjectIdentity__args[0]
        return (None, None, None, [[1, MockValue(get_value[key])]])

    with patch("pysnmp.hlapi.asyncio.getCmd", replace_with):
        yield


@pytest.fixture
async def start_ha(hass, count, domain, config_addon, config, caplog, mock_getcmd):
    """Do setup of integration."""
    if config_addon:
        for key, value in config_addon.items():
            config = config.replace(key, value)
        config = json.loads(config)
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

    await hass.async_block_till_done()


@pytest.fixture
async def caplog_setup_text(caplog):
    """Return setup log of integration."""
    yield caplog.text
