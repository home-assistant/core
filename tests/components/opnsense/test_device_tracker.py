"""The tests for the opnsense device tracker platform."""
from homeassistant.setup import async_setup_component

from homeassistant.components.opnsense import (
    CONF_API_SECRET,
    DOMAIN,
    OPNSENSE_DATA,
)
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_VERIFY_SSL

from tests.common import MockDependency, mock_coro_func

FAKEFILE = None

VALID_CONFIG_ROUTER_SSH = {
    DOMAIN: {
        CONF_URL: "https://fakehost",
        CONF_API_KEY: "fake_key",
        CONF_API_SECRET: "fake_secret",
        CONF_VERIFY_SSL: False,
    }
}


async def test_get_scanner(hass):
    """Test creating an opnsense scanner."""
    with MockDependency("pyopnsense") as mocked_opnsense:
        mocked_opnsense.diagnostic.InterfaceClient().get_arp = mock_coro_func()
        mocked_opnsense.diagnostic.NetworkInsightClient().get_interfaces = mock_coro_func(
            return_value={}
        )
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_URL: "https://fakehost",
                    CONF_API_KEY: "fake_key",
                    CONF_API_SECRET: "fake_secret",
                    CONF_VERIFY_SSL: False,
                }
            },
        )
        assert result
        assert hass.data[OPNSENSE_DATA] is not None
