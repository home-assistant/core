"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components.opnsense import CONF_API_SECRET, DOMAIN, OPNSENSE_DATA
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_VERIFY_SSL
from homeassistant.setup import async_setup_component

from tests.common import MockDependency


async def test_get_scanner(hass):
    """Test creating an opnsense scanner."""
    with MockDependency("pyopnsense") as mocked_opnsense:
        get_arp = mock.MagicMock()
        get_interfaces = mock.MagicMock()
        get_interfaces.return_value = {}
        mocked_opnsense.diagnostic.InterfaceClient().get_arp = get_arp
        mocked_opnsense.diagnostic.NetworkInsightClient().get_interfaces = (
            get_interfaces
        )
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_URL: "https://fake_host_fun/api",
                    CONF_API_KEY: "fake_key",
                    CONF_API_SECRET: "fake_secret",
                    CONF_VERIFY_SSL: False,
                }
            },
        )
        assert result
        assert hass.data[OPNSENSE_DATA] is not None
