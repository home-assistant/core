"""Test the NO-IP component."""
import base64
from unittest.mock import Mock

import pytest

from homeassistant.components import no_ip
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "test.example.com"

PASSWORD = "xyz789"

USERNAME = "abc@123.com"


async def test_setup(hass: HomeAssistant) -> None:
    """Test the setup of the NO-IP component."""
    result = await async_setup_component(
        hass,
        no_ip.DOMAIN,
        {
            no_ip.DOMAIN: {
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
                "timeout": 10,
            }
        },
    )
    assert result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_text"),
    [
        ("good 0.0.0.0"),
        ("nochg 0.0.0.0"),
    ],
)
async def test_update_no_ip(result_text):
    """Test successful update of NO-IP."""
    hass = Mock(spec=HomeAssistant)
    session = Mock()
    domain = DOMAIN
    auth_str = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode())
    timeout = 10

    # Replace the session.get method with the fake_session_get function.
    async def fake_session_get(url, params, headers):
        # Simulate a real aiohttp.ClientResponse object.
        class FakeResponse:
            async def text(self):
                # Return the expected response text here.
                return result_text

        return FakeResponse()

    # Replace the session.get method with the fake_session_get function.
    session.get.side_effect = fake_session_get

    result = await no_ip._update_no_ip(hass, session, domain, auth_str, timeout)

    assert result is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_text"),
    [
        ("badauth"),
        ("badagent"),
        ("nohost"),
    ],
)
async def test_fail_update_no_ip(result_text):
    """Test failed update of NO-IP."""
    hass = Mock(spec=HomeAssistant)
    session = Mock()
    domain = DOMAIN
    auth_str = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode())
    timeout = 10

    # Replace the session.get method with the fake_session_get function.
    async def fake_session_get(url, params, headers):
        # Simulate a real aiohttp.ClientResponse object.
        class FakeResponse:
            async def text(self):
                # Return the expected response text here.
                return result_text

        return FakeResponse()

    # Replace the session.get method with the fake_session_get function.
    session.get.side_effect = fake_session_get

    result = await no_ip._update_no_ip(hass, session, domain, auth_str, timeout)

    assert result is False
