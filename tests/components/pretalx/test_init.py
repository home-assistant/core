"""Test the pretalx integration setup."""

from aiohttp import ClientError

from homeassistant.components.pretalx.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import BASE_URL

from tests.common import MockConfigEntry, async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_pretalx: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "DemoCon"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a connection error results in a retry."""
    aioclient_mock.get(f"{BASE_URL}/", exc=ClientError)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_rooms_pagination(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that all pages of a paginated endpoint are fetched."""
    aioclient_mock.get(
        f"{BASE_URL}/",
        json=await async_load_json_object_fixture(hass, "event.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{BASE_URL}/rooms/?cursor=next",
        json={
            "count": 2,
            "next": None,
            "previous": None,
            "results": [{"id": 131, "name": {"en": "Magenta Room"}}],
        },
    )
    aioclient_mock.get(
        f"{BASE_URL}/rooms/",
        json={
            "count": 2,
            "next": f"{BASE_URL}/rooms/?cursor=next",
            "previous": None,
            "results": [{"id": 130, "name": {"en": "Khaki Room"}}],
        },
    )
    aioclient_mock.get(
        f"{BASE_URL}/submissions/",
        json={"count": 0, "next": None, "previous": None, "results": []},
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 2
    )
