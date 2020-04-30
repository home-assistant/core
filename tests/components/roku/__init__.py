"""Tests for the Roku component."""
from requests_mock import Mocker

from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry, load_fixture

HOST = "192.168.1.160"
NAME = "Roku 3"
SSDP_LOCATION = "http://192.168.1.160/"
UPNP_FRIENDLY_NAME = "My Roku 3"
UPNP_SERIAL = "1GU48T017973"


def mock_connection(
    requests_mocker: Mocker, device: str = "roku3", app: str = "roku", host: str = HOST,
) -> None:
    """Mock the Roku connection."""
    roku_url = f"http://{host}:8060"

    requests_mocker.get(
        f"{roku_url}/query/device-info",
        text=load_fixture(f"roku/{device}-device-info.xml"),
    )

    apps_fixture = "roku/apps.xml"
    if device == "rokutv":
        apps_fixture = "roku/apps-tv.xml"

    requests_mocker.get(
        f"{roku_url}/query/apps", text=load_fixture(apps_fixture),
    )

    requests_mocker.get(
        f"{roku_url}/query/active-app", text=load_fixture(f"roku/active-app-{app}.xml"),
    )


async def setup_integration(
    hass: HomeAssistantType,
    requests_mocker: Mocker,
    device: str = "roku3",
    app: str = "roku",
    host: str = HOST,
    unique_id: str = UPNP_SERIAL,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Roku integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data={CONF_HOST: host})

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        mock_connection(requests_mocker, device, app=app, host=host)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
