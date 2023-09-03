"""Test the NO-IP component."""
import base64
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from homeassistant.components import no_ip
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

DOMAIN = "test.example.com"

PASSWORD = "xyz789"

USERNAME = "abc@123.com"


async def test_setup(hass: HomeAssistant) -> None:
    """Test the setup of the NO-IP component."""

    async def fake_get(url, **kwargs):
        response = AsyncMock(spec=aiohttp.ClientResponse)
        response.status = 200
        response.text.return_value = "good 1.2.3.4"

        return response

    with patch("aiohttp.ClientSession.get", side_effect=fake_get):
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


async def test_async_setup_entry_with_interval(hass: HomeAssistant):
    """Test async_setup_entry with time interval."""
    with patch("homeassistant.components.no_ip._update_no_ip", return_value=True):
        entry = MockConfigEntry(
            domain=no_ip.DOMAIN,
            data={
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
                "timeout": 10,
            },
        )
        entry.add_to_hass(hass)

        result = await no_ip.async_setup_entry(hass, entry)

        assert result  # Ensure that async_setup_entry returns True

        async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))


async def test_async_setup_entry_failure(hass: HomeAssistant):
    """Test async_setup_entry when _update_no_ip returns False."""
    with patch("homeassistant.components.no_ip._update_no_ip", return_value=False):
        entry = MockConfigEntry(
            domain=no_ip.DOMAIN,
            data={
                "domain": DOMAIN,
                "username": USERNAME,
                "password": PASSWORD,
                "timeout": 10,
            },
        )
        entry.add_to_hass(hass)

        result = await no_ip.async_setup_entry(hass, entry)

    assert not result  # Ensure that async_setup_entry returns False


async def test_async_setup_entry_failure_no_data(hass: HomeAssistant):
    """Test async_setup_entry when _update_no_ip returns False."""
    with patch("homeassistant.components.no_ip._update_no_ip", return_value=False):
        entry = MockConfigEntry(
            domain=no_ip.DOMAIN,
            data={},
        )
        entry.add_to_hass(hass)

        result = await no_ip.async_setup_entry(hass, entry)

    assert not result  # Ensure that async_setup_entry returns False


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


@pytest.mark.asyncio
async def test_update_no_ip_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test failed update timeout of NO-IP."""
    AUTH_STR = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode())
    TIMEOUT = 10

    # Mock the aiohttp GET request to simulate a TimeoutError
    aioclient_mock.get(
        f"https://dynupdate.no-ip.com/nic/update?hostname={DOMAIN}", exc=TimeoutError()
    )

    # Call the _update_no_ip function
    result = await no_ip._update_no_ip(
        hass, async_get_clientsession(hass), DOMAIN, AUTH_STR, TIMEOUT
    )

    # Ensure it returns False due to the TimeoutError
    assert result is False


@pytest.mark.asyncio
async def test_update_no_ip_clienterror(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test failed update clienterror of NO-IP."""
    AUTH_STR = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode())
    TIMEOUT = 10

    # Mock the aiohttp GET request to simulate a TimeoutError
    aioclient_mock.get(
        f"https://dynupdate.no-ip.com/nic/update?hostname={DOMAIN}",
        exc=aiohttp.ClientError(),
    )

    # Call the _update_no_ip function
    result = await no_ip._update_no_ip(
        hass, async_get_clientsession(hass), DOMAIN, AUTH_STR, TIMEOUT
    )

    # Ensure it returns False due to the TimeoutError
    assert result is False
