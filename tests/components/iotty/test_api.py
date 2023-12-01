"""Unit tests for iottycloud API."""


from unittest.mock import patch

from aiohttp import ClientSession
from iottycloud.verbs import LS_DEVICE_TYPE_UID
import pytest

from homeassistant.components.iotty import api
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.switch import IottyLightSwitch
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import test_devices

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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
    local_oauth_impl: ClientSession,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)

    assert iotty is not None


@patch(
    "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.valid_token", False
)
async def test_api_getaccesstoken_tokennotvalid_reloadtoken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_aioclient: None,
    aiohttp_client_session: ClientSession,
) -> None:
    """Print a message if the token is not valid."""
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    mock_aioclient.post(
        "https://token.url", json={"access_token": "ACCESS_TOKEN_1", "expires_in": 100}
    )

    mock_aioclient.post("https://example.com", status=201)

    mock_config_entry.add_to_hass(hass)
    oauth2_session = config_entry_oauth2_flow.OAuth2Session(
        hass, mock_config_entry, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth2_session)

    tok = await iotty.async_get_access_token()
    assert tok is not None


async def test_api_init_ok_nodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_get_devices_nodevices,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()

    assert len(mock_get_devices_nodevices.mock_calls) != 0
    assert len(iotty._devices) == 0


async def test_api_init_ok_twodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_get_devices_twodevices,
    mock_get_status_filled,
    mock_store_entity,
) -> None:
    """Test API creation."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)

    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = iotty

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  ## Also wait for BG tasks

    assert len(mock_get_devices_twodevices.mock_calls) != 0
    assert len(await iotty.devices(LS_DEVICE_TYPE_UID)) == 2
    assert len(mock_get_status_filled.mock_calls) != 0
    assert len(mock_store_entity.mock_calls) == 2


def test_store_entity_duplicate_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_devices: list,
) -> None:
    """Store twice the same entity. Only one remains."""
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)
    assert len(iotty._entities) == 0

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1


def test_store_entity_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_devices: list,
) -> None:
    """Store two entities."""
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)
    assert len(iotty._entities) == 0

    iotty.store_entity("TEST", mock_devices[0])
    assert len(iotty._entities) == 1

    iotty.store_entity("TEST1", mock_devices[0])
    assert len(iotty._entities) == 2


async def test_api_polling_nostatus(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_devices: list,
    mock_get_status_empty,
    mock_schedule_update_ha_state,
    mock_get_devices_twodevices,
) -> None:
    """Test polling get_status from iottyCloud API, with no status returned."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = iotty

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()

    assert len(mock_get_devices_twodevices.mock_calls) != 0
    assert len(mock_get_status_empty.mock_calls) != 0

    assert len(mock_schedule_update_ha_state.mock_calls) == 0


async def test_api_polling_withstatus_device_non_existant(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_get_devices_twodevices: list,
    mock_get_status_filled,
    mock_schedule_update_ha_state,
    mock_update_status,
) -> None:
    """Test polling get_status from iottyCloud API, with a status returned, but with a non-existing entity/device."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()

    assert len(mock_get_devices_twodevices.mock_calls) != 0
    assert len(mock_get_status_filled.mock_calls) != 0
    assert len(mock_update_status.mock_calls) == 2
    assert len(mock_schedule_update_ha_state.mock_calls) == 0


async def test_api_polling_withstatus(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    aiohttp_client_session: None,
    mock_get_devices_twodevices,
    mock_get_status_filled,
    mock_schedule_update_ha_state,
    mock_update_status,
) -> None:
    """Test polling get_status from iottyCloud API, with a status returned."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = iotty
    await hass.async_block_till_done()

    iotty.store_entity(
        test_devices[0].device_id, IottyLightSwitch(iotty, test_devices[0])
    )
    iotty.store_entity(
        test_devices[1].device_id, IottyLightSwitch(iotty, test_devices[1])
    )

    await iotty.init(mock_config_entry)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(mock_get_devices_twodevices.mock_calls) != 0
    assert len(iotty._devices) == 2
    assert len(iotty._entities) == 2
    assert len(mock_get_status_filled.mock_calls) != 0

    assert len(mock_update_status.mock_calls) == 2
    assert len(mock_schedule_update_ha_state.mock_calls) == 2
