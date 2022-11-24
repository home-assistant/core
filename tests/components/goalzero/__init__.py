"""Tests for the Goal Zero Yeti integration."""
from unittest.mock import AsyncMock, patch

from spencerassistant.components import dhcp
from spencerassistant.components.goalzero import DOMAIN
from spencerassistant.components.goalzero.const import DEFAULT_NAME
from spencerassistant.const import CONF_HOST, CONF_NAME
from spencerassistant.core import spencerAssistant
from spencerassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "1.2.3.4"
MAC = "aa:bb:cc:dd:ee:ff"

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: DEFAULT_NAME,
}

CONF_DHCP_FLOW = dhcp.DhcpServiceInfo(
    ip=HOST,
    macaddress=format_mac("AA:BB:CC:DD:EE:FF"),
    hostname="yeti",
)


def create_entry(hass: spencerAssistant):
    """Add config entry in spencer Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=MAC,
    )
    entry.add_to_hass(hass)
    return entry


async def create_mocked_yeti():
    """Create mocked yeti device."""
    mocked_yeti = AsyncMock()
    mocked_yeti.data = {}
    mocked_yeti.data["firmwareVersion"] = "1.0.0"
    mocked_yeti.sysdata = {}
    mocked_yeti.sysdata["model"] = "test_model"
    mocked_yeti.sysdata["macAddress"] = MAC
    return mocked_yeti


def patch_config_flow_yeti(mocked_yeti):
    """Patch Goal Zero config flow."""
    return patch(
        "spencerassistant.components.goalzero.config_flow.Yeti",
        return_value=mocked_yeti,
    )


async def async_init_integration(
    hass: spencerAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Goal Zero integration in spencer Assistant."""
    entry = create_entry(hass)
    base_url = f"http://{HOST}/"
    aioclient_mock.get(
        f"{base_url}state",
        text=load_fixture("goalzero/state_data.json"),
    )
    aioclient_mock.get(
        f"{base_url}sysinfo",
        text=load_fixture("goalzero/info_data.json"),
    )

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
