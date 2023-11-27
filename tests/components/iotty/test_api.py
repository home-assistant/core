"""Unit tests for iottycloud API."""


from aiohttp import ClientSession
import pytest

from homeassistant.components.iotty import api
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def aiohttp_client_session() -> None:
    """AIOHTTP client session."""
    return ClientSession


async def test_api_create_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test API creation with no session."""

    with pytest.raises(ValueError) as excinfo:
        _ = api.IottyProxy(hass, None, None)
    assert "websession" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        _ = api.IottyProxy(hass, aioclient_mock, None)
    assert "oauth_session" in str(excinfo.value)


async def test_api_create_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aiohttp_client_session: None,
    oauth_impl: ClientSession,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth_impl)

    assert iotty is not None


async def test_api_init_ok_nodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    oauth_impl: ClientSession,
    aiohttp_client_session: None,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth_impl)

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()

    assert len(iotty._devices) == 0


# async def test_api_init_ok_twodevices(
#     hass: HomeAssistant,
#     mock_config_entry: MockConfigEntry,
#     oauth_impl: ClientSession,
#     aiohttp_client_session: None,
#     mock_devices: list,
# ) -> None:
#     """Test API creation."""

#     mock_config_entry.add_to_hass(hass)

#     config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

#     iotty = api.IottyProxy(hass, aiohttp_client_session, oauth_impl)

#     with patch.object(iotty, "_devices", mock_devices):
#         await iotty.init(mock_config_entry)
#         await hass.async_block_till_done()
#         assert 2 == len(iotty._devices)

#     await iotty._coroutine()


def test_store_entity_duplicate_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_devices: list,
) -> None:
    """Store twice the same entity. Only one remains."""
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth_impl)
    assert len(iotty._entities) == 0

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1


def test_store_entity_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_devices: list,
) -> None:
    """Store two entities."""
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, oauth_impl)

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth_impl)
    assert len(iotty._entities) == 0

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1

    iotty.store_entity("TEST1", mock_devices[0])
    assert len(iotty._entities) == 2
