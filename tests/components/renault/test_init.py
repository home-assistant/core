"""Tests for Renault setup process."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import aiohttp
import pytest
from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya.exceptions import GigyaException, InvalidCredentialsException
from renault_api.renault_session import RenaultSession
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    CONF_LOGIN_TOKEN,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import MOCK_ACCOUNT_ID, MOCK_LOGIN_TOKEN

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

# Config data of an entry created before the login token was stored.
MOCK_CONFIG_NO_TOKEN = {
    CONF_USERNAME: "email@test.com",
    CONF_PASSWORD: "test",
    CONF_KAMEREON_ACCOUNT_ID: MOCK_ACCOUNT_ID,
    CONF_LOCALE: "fr_FR",
}


def _mock_login(session: RenaultSession, login_id: str, password: str) -> None:
    """Restore a login token like a successful Gigya login would."""
    session.set_login_token(MOCK_LOGIN_TOKEN)


@pytest.fixture(name="legacy_config_entry")
def get_legacy_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create an entry that predates the stored login token."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_NO_TOKEN,
        unique_id=MOCK_ACCOUNT_ID,
        entry_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        yield


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_setup_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test entry setup and unload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    # Unload the entry and verify that the data has been removed
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_setup_entry_password_login(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry
) -> None:
    """Test an entry without a stored login token falls back to a password login."""
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        autospec=True,
        side_effect=_mock_login,
    ) as mock_login:
        await hass.config_entries.async_setup(legacy_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_login.called
    assert legacy_config_entry.state is ConfigEntryState.LOADED
    # The obtained login token is persisted so future setups skip the password.
    assert legacy_config_entry.data[CONF_LOGIN_TOKEN] == MOCK_LOGIN_TOKEN


async def test_setup_entry_bad_password(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry
) -> None:
    """Test reauth is triggered when the stored password is invalid."""
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        await hass.config_entries.async_setup(legacy_config_entry.entry_id)
        await hass.async_block_till_done()

    assert legacy_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == legacy_config_entry.entry_id


@pytest.mark.parametrize(
    "side_effect", [aiohttp.ClientConnectionError(), GigyaException()]
)
async def test_setup_entry_password_exception(
    hass: HomeAssistant,
    legacy_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test ConfigEntryNotReady when the password login raises an exception."""
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(legacy_config_entry.entry_id)
        await hass.async_block_till_done()

    assert legacy_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_bad_token(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test reauth is triggered when the stored login token is no longer valid."""
    with patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        side_effect=NotAuthenticatedException("Authentication expired."),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


@pytest.mark.usefixtures("patch_renault_account")
@pytest.mark.parametrize(
    "side_effect", [aiohttp.ClientConnectionError(), GigyaException()]
)
async def test_setup_entry_exception(
    hass: HomeAssistant, config_entry: ConfigEntry, side_effect: Exception
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account")
async def test_setup_entry_kamereon_exception(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    # In this case we are testing the condition where renault_hub fails to retrieve
    # list of vehicles (see Gateway Time-out on #97324).
    with patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        side_effect=aiohttp.ClientResponseError(Mock(), (), status=504),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["missing_details"], indirect=True)
async def test_setup_entry_missing_vehicle_details(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when vehicleDetails is missing."""
    # In this case we are testing the condition where renault_hub fails to retrieve
    # vehicle details (see #99127).
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
async def test_device_registry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device is correctly registered."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})
    entry_id = config_entry.entry_id
    live_id = "VF1ZOE40VIN"
    dead_id = "VF1AAAAA555777888"

    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 0
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, dead_id)},
        manufacturer="Renault",
        model="Zoe",
        name="REGISTRATION-NUMBER",
        sw_version="X101VE",
    )
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Try to remove "VF1ZOE40VIN" - fails as it is live
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, live_id)}) is not None

    # Try to remove "VF1AAAAA555777888" - succeeds as it is dead
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert device_registry.async_get_device(identifiers={(DOMAIN, dead_id)}) is None
