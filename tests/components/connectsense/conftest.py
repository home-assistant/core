import pytest

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from tests.common import MockConfigEntry

DOMAIN = "connectsense"


@pytest.fixture
def domain() -> str:
    return DOMAIN


@pytest.fixture
def serial() -> str:
    return "1000001"


@pytest.fixture
def host() -> str:
    return "rebooter-pro.local"


@pytest.fixture
def device_display_name(serial: str) -> str:
    return f"Rebooter Pro {serial}"


@pytest.fixture
def mock_http(aioclient_mock, host: str, serial: str):
    """Mock the device HTTPS endpoints used by the integration."""
    base = f"https://{host}:443"
    aioclient_mock.get(
        f"{base}/info",
        json={
            "device": f"CS-RBTR-{serial}",
            "firmware_version": "1.0.0",
            "update_available": False,
            "MAC": "00:00:00:00:00:00",
        },
    )
    aioclient_mock.post(f"{base}/control", status=200, text="OK")
    return aioclient_mock


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    domain: str,
    host: str,
    serial: str,
    mock_http,
):
    """Create and set up a real ConfigEntry for the integration."""
    # Avoid NoURLAvailableError during webhook generation
    hass.config.internal_url = "http://example.local"
    hass.config.external_url = "https://example.com"

    entry = MockConfigEntry(
        domain=domain,
        data={CONF_HOST: host},
        unique_id=serial,  # matches serial from /info
        title=f"Rebooter Pro {serial}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def device_id(hass: HomeAssistant, setup_entry: MockConfigEntry, domain: str) -> str:
    """Return the device_id created by the integration for this entry."""
    dev_reg = dr.async_get(hass)
    uid = setup_entry.unique_id or setup_entry.data[CONF_HOST]
    device = dev_reg.async_get_device(identifiers={(domain, uid)})
    assert device is not None
    return device.id
