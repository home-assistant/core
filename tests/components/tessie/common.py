"""Tessie common helpers for tests."""

from http import HTTPStatus
from unittest.mock import patch

from aiohttp import ClientConnectionError, ClientResponseError
from aiohttp.client import RequestInfo
from syrupy import SnapshotAssertion

from homeassistant.components.tessie import PLATFORMS
from homeassistant.components.tessie.const import DOMAIN, TessieStatus
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.common import MockConfigEntry, load_json_object_fixture

# Tessie library
TEST_STATE_OF_ALL_VEHICLES = load_json_object_fixture("vehicles.json", DOMAIN)
TEST_VEHICLE_STATE_ONLINE = load_json_object_fixture("online.json", DOMAIN)
TEST_VEHICLE_STATUS_AWAKE = {"status": TessieStatus.AWAKE}
TEST_VEHICLE_STATUS_ASLEEP = {"status": TessieStatus.ASLEEP}

TEST_RESPONSE = {"result": True}
TEST_RESPONSE_ERROR = {"result": False, "reason": "reason_why"}

TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}
TESSIE_URL = "https://api.tessie.com/"

TEST_REQUEST_INFO = RequestInfo(
    url=TESSIE_URL, method="GET", headers={}, real_url=TESSIE_URL
)


def error_auth() -> ClientResponseError:
    """Return an error."""
    return ClientResponseError(
        request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.UNAUTHORIZED
    )


def error_timeout() -> ClientResponseError:
    """Return an error."""
    return ClientResponseError(
        request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.REQUEST_TIMEOUT
    )


def error_unknown() -> ClientResponseError:
    """Return an error."""
    return ClientResponseError(
        request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.BAD_REQUEST
    )


def error_virtual_key() -> ClientResponseError:
    """Return an error."""
    return ClientResponseError(
        request_info=TEST_REQUEST_INFO,
        history=None,
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def error_connection() -> ClientResponseError:
    """Return an error."""
    return ClientConnectionError()


# Fleet API library
PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
LIVE_STATUS = load_json_object_fixture("live_status.json", DOMAIN)
SITE_INFO = load_json_object_fixture("site_info.json", DOMAIN)
RESPONSE_OK = {"response": {}, "error": None}
COMMAND_OK = {"response": {"result": True, "reason": ""}}
SCOPES = [
    "user_data",
    "vehicle_device_data",
    "vehicle_cmds",
    "vehicle_charging_cmds",
    "energy_device_data",
    "energy_cmds",
    "offline_access",
    "openid",
]
NO_SCOPES = ["user_data", "offline_access", "openid"]


async def setup_platform(
    hass: HomeAssistant, platforms: list[Platform] | UndefinedType = UNDEFINED
) -> MockConfigEntry:
    """Set up the Tessie platform."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tessie.PLATFORMS",
        PLATFORMS if platforms is UNDEFINED else platforms,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry


def assert_entities(
    hass: HomeAssistant,
    entry_id: str,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all entities match their snapshot."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")
