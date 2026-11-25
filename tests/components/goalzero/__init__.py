"""Tests for the Goal Zero Yeti integration."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.goalzero.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

HOST = "1.2.3.4"
MAC = "aa:bb:cc:dd:ee:ff"

CONF_DATA = {CONF_HOST: HOST}

CONF_DHCP_FLOW = DhcpServiceInfo(
    ip=HOST,
    macaddress=format_mac("AA:BB:CC:DD:EE:FF").replace(":", ""),
    hostname="yeti",
)


def create_entry(hass: HomeAssistant, data: dict[str, str] | None = None):
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data or CONF_DATA,
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
        "homeassistant.components.goalzero.config_flow.Yeti",
        return_value=mocked_yeti,
    )


async def async_init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
    data: dict[str, str] | None = None,
) -> MockConfigEntry:
    """Set up the Goal Zero integration in Home Assistant."""
    entry = create_entry(hass, data)
    base_url = f"http://{HOST}/"
    aioclient_mock.get(
        f"{base_url}state",
        text=await async_load_fixture(hass, "state_data.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{base_url}sysinfo",
        text=await async_load_fixture(hass, "info_data.json", DOMAIN),
    )

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
