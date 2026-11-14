"""Tests for Renault setup process."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
)
from pytest_homeassistant.typing import WebSocketGenerator
from renault_api.exceptions import NotAuthenticatedException
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidCredentialsException,
    PendingTwoFactorAuthenticationException,
)
from renault_api.kamereon import exceptions, models, schemas
from renault_api.kamereon.models import KamereonVehicleCockpitData
from renault_api.renault_session import RenaultSession
from renault_api.renault_vehicle import RenaultVehicle
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.renault.const import (
    DOMAIN,
    VEHICLE_LIST_SCAN_INTERVAL,
    RenaultConfigurationKeys,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .const import (
    FORBIDDEN_EXCEPTION,
    MOCK_ACCOUNT_ID,
    MOCK_DEVICE_IDS,
    MOCK_LOGIN_TOKEN,
    OTHER_ACCOUNT_ID,
)

# Config data of an entry created before the login token was stored.
MOCK_CONFIG_NO_TOKEN = {
    RenaultConfigurationKeys.USERNAME: "email@test.com",
    RenaultConfigurationKeys.PASSWORD: "test",
    RenaultConfigurationKeys.KAMEREON_ACCOUNT_ID: MOCK_ACCOUNT_ID,
    RenaultConfigurationKeys.LOCALE: "fr_FR",
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
    assert (
        legacy_config_entry.data[RenaultConfigurationKeys.LOGIN_TOKEN]
        == MOCK_LOGIN_TOKEN
    )


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_setup_entry_password_login_device_ids(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry
) -> None:
    """Test the remembered device ids are restored before a password login."""
    hass.config_entries.async_update_entry(
        legacy_config_entry,
        data={
            **legacy_config_entry.data,
            RenaultConfigurationKeys.DEVICE_IDS: MOCK_DEVICE_IDS,
        },
    )
    device_ids: list[dict[str, str]] = []

    def _record_device_ids(
        session: RenaultSession, login_id: str, password: str
    ) -> None:
        device_ids.append(session.device_ids)
        _mock_login(session, login_id, password)

    with patch(
        "renault_api.renault_session.RenaultSession.login",
        autospec=True,
        side_effect=_record_device_ids,
    ):
        await hass.config_entries.async_setup(legacy_config_entry.entry_id)
        await hass.async_block_till_done()

    assert device_ids == [MOCK_DEVICE_IDS]
    assert legacy_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            InvalidCredentialsException(403042, "invalid loginID or password"),
            id="invalid_credentials",
        ),
        pytest.param(
            PendingTwoFactorAuthenticationException(
                403101, "Pending Two-Factor Authentication", "reg-token"
            ),
            id="two_factor_auth",
        ),
    ],
)
async def test_setup_entry_bad_password(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry, side_effect: Exception
) -> None:
    """Test reauth is triggered when the password login fails."""
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=side_effect,
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


@pytest.mark.usefixtures("patch_renault_account", "patch_get_api_accounts")
@pytest.mark.parametrize(
    ("account_ids", "expected_issues"),
    [
        pytest.param([MOCK_ACCOUNT_ID], set(), id="account_listed"),
        pytest.param(
            [OTHER_ACCOUNT_ID],
            {(DOMAIN, "account_not_found_123456")},
            id="account_not_listed",
        ),
    ],
)
async def test_setup_entry_forbidden(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    issue_registry: ir.IssueRegistry,
    expected_issues: set[tuple[str, str]],
) -> None:
    """Test a forbidden Kamereon account fails setup without retrying."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        side_effect=FORBIDDEN_EXCEPTION,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert set(issue_registry.issues) == expected_issues


@pytest.mark.usefixtures(
    "patch_renault_account", "patch_get_api_accounts", "patch_get_vehicles"
)
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
@pytest.mark.parametrize("account_ids", [[OTHER_ACCOUNT_ID]])
async def test_account_not_found_issue_deleted_on_setup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue is deleted once the account loads again."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        side_effect=FORBIDDEN_EXCEPTION,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert len(issue_registry.issues) == 0


@pytest.mark.usefixtures("patch_renault_account", "patch_get_api_accounts")
@pytest.mark.parametrize("account_ids", [[OTHER_ACCOUNT_ID]])
async def test_account_not_found_issue_deleted_on_removal(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue is deleted when the config entry is removed."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        side_effect=FORBIDDEN_EXCEPTION,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(DOMAIN, "account_not_found_123456")
    assert issue is not None
    assert issue.config_entry_id == config_entry.entry_id

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 0


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["missing_details"], indirect=True)
async def test_setup_entry_missing_vehicle_details(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_get_vehicle_details: AsyncMock
) -> None:
    """Test ConfigEntryNotReady when vehicleDetails is missing."""
    # In this case we are testing the condition where renault_hub fails to retrieve
    # vehicle details (see #99127), even when requested separately.
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Requested for each vehicle without details in the vehicle list.
    assert mock_get_vehicle_details.await_count == 2
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
async def test_stale_device_removed_on_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
) -> None:
    """Test a device no longer in the vehicle list is removed on setup."""
    entry_id = config_entry.entry_id
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, "VF1AAAAA555777888")},
        manufacturer="Renault",
        model="Zoe",
        name="REGISTRATION-NUMBER",
    )

    await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(device_registry, entry_id)
    assert [device.identifiers for device in device_entries] == [
        {(DOMAIN, "VF1ZOE40VIN")}
    ]


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["missing_details"], indirect=True)
async def test_stale_device_removed_on_setup_retry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
) -> None:
    """Test stale devices are removed when no vehicle details are available."""
    entry_id = config_entry.entry_id
    for vin in ("VF1ZOE40VIN", "VF1AAAAA555777888"):
        device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, vin)},
            manufacturer="Renault",
            model="Zoe",
            name="REGISTRATION-NUMBER",
        )

    await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    device_entries = dr.async_entries_for_config_entry(device_registry, entry_id)
    assert [device.identifiers for device in device_entries] == [
        {(DOMAIN, "VF1ZOE40VIN")}
    ]


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_stale_devices_kept_on_empty_vehicle_list(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
) -> None:
    """Test devices are kept when the vehicle list is empty."""
    entry_id = config_entry.entry_id
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, "VF1ZOE40VIN")},
        manufacturer="Renault",
        model="Zoe",
        name="REGISTRATION-NUMBER",
    )

    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=models.KamereonVehiclesResponse(
            raw_data={},
            errors=None,
            accountId=MOCK_ACCOUNT_ID,
            country="FR",
            vehicleLinks=[],
        ),
    ):
        await hass.config_entries.async_setup(entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1


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

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, dead_id)},
        manufacturer="Renault",
        model="Zoe",
        name="REGISTRATION-NUMBER",
    )
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Try to remove "VF1ZOE40VIN" - fails as it is live
    device = device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
        is not None
    )

    # Try to remove "VF1AAAAA555777888" - succeeds as it is dead
    device = device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
    response = await client.remove_device(device.id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
        is None
    )


ZOE_VIN = "VF1ZOE40VIN"
CAPTUR_VIN = "VF1CAPTURFUELVIN"
ZOE_50_VIN = "VF1ZOE50VIN"
# Listed in the zoe_40 fixture, without vehicle details.
MISSING_DETAILS_VIN = "VYSP0100875XXXXXX"


def _get_vehicles(*vins: str) -> models.KamereonVehiclesResponse:
    """Return a vehicle list with the given vehicles."""
    response: models.KamereonVehiclesResponse = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture("renault/vehicle_zoe_40.json")
        )
    )
    links = [
        *(response.vehicleLinks or []),
        *(
            link
            for fixture in ("captur_fuel", "zoe_50")
            for link in schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture(f"renault/vehicle_{fixture}.json")
            ).vehicleLinks
            or []
        ),
    ]
    response.vehicleLinks = [link for link in links if link.vin in vins]
    return response


@pytest.fixture(name="sensor_platform")
def override_sensor_platform() -> Generator[None]:
    """Set up the sensor platform only."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.fixture(name="mock_get_vehicles")
def patch_get_vehicles() -> Generator[AsyncMock]:
    """Mock the vehicle list, with the Zoe only."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=_get_vehicles(ZOE_VIN),
    ) as mock_get_vehicles:
        yield mock_get_vehicles


async def _async_poll_vehicle_list(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Trigger the next vehicle list update."""
    freezer.tick(VEHICLE_LIST_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _device_vins(
    device_registry: dr.DeviceRegistry, config_entry: ConfigEntry
) -> set[str]:
    """Return the VINs of the vehicle devices of the config entry."""
    return {
        identifier
        for device in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    }


def _vehicle_entities(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: ConfigEntry,
    vin: str,
) -> list[er.RegistryEntry]:
    """Return the entities of a vehicle, after checking its device exists."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, vin), config_entry.entry_id
    )
    assert device is not None
    return er.async_entries_for_device(entity_registry, device.id)


@pytest.mark.usefixtures(
    "patch_renault_account", "fixtures_with_data", "sensor_platform"
)
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_added(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
) -> None:
    """Test a vehicle added to the account is set up without a reload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, CAPTUR_VIN), config_entry.entry_id
        )
        is None
    )

    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, CAPTUR_VIN)
    await _async_poll_vehicle_list(hass, freezer)

    assert _device_vins(device_registry, config_entry) == {ZOE_VIN, CAPTUR_VIN}
    entities = _vehicle_entities(
        device_registry, entity_registry, config_entry, CAPTUR_VIN
    )
    assert entities
    assert all(hass.states.get(entity.entity_id) for entity in entities)


@pytest.mark.usefixtures("patch_renault_account", "sensor_platform")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_added_with_failed_sibling(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    fixtures_with_data: dict[str, AsyncMock],
) -> None:
    """Test a vehicle added to the account gets its entities when another fails."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    cockpit = fixtures_with_data["cockpit"].return_value

    async def _get_cockpit(vehicle: RenaultVehicle) -> KamereonVehicleCockpitData:
        if vehicle.vin == ZOE_50_VIN:
            raise NotAuthenticatedException("Not logged in")
        return cockpit

    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, CAPTUR_VIN, ZOE_50_VIN)
    with patch.object(RenaultVehicle, "get_cockpit", _get_cockpit):
        await _async_poll_vehicle_list(hass, freezer)

    assert _device_vins(device_registry, config_entry) == {ZOE_VIN, CAPTUR_VIN}
    entities = _vehicle_entities(
        device_registry, entity_registry, config_entry, CAPTUR_VIN
    )
    assert entities
    assert all(hass.states.get(entity.entity_id) for entity in entities)
    # The scan interval of all vehicles is adjusted despite the failure.
    assert (
        len(
            {
                coordinator.update_interval
                for vehicle in config_entry.runtime_data.vehicles.values()
                for coordinator in vehicle.coordinators.values()
            }
        )
        == 1
    )
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures(
    "patch_renault_account", "fixtures_with_data", "sensor_platform"
)
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_removed(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
) -> None:
    """Test a vehicle removed from the account is removed without a reload."""
    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, CAPTUR_VIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entities = _vehicle_entities(
        device_registry, entity_registry, config_entry, CAPTUR_VIN
    )
    assert entities

    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN)
    await _async_poll_vehicle_list(hass, freezer)

    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, CAPTUR_VIN), config_entry.entry_id
        )
        is None
    )
    assert not any(entity_registry.async_get(entity.entity_id) for entity in entities)
    assert not any(hass.states.get(entity.entity_id) for entity in entities)
    assert _vehicle_entities(device_registry, entity_registry, config_entry, ZOE_VIN)


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_list_empty(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
) -> None:
    """Test an empty vehicle list does not remove the vehicles."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_get_vehicles.return_value = _get_vehicles()
    await _async_poll_vehicle_list(hass, freezer)

    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, ZOE_VIN), config_entry.entry_id
    )


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_missing_details_retried(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    mock_get_vehicle_details: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the details of a vehicle are requested again at the next update."""
    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, MISSING_DETAILS_VIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_get_vehicle_details.await_count == 1
    assert [
        record.levelname
        for record in caplog.records
        if record.getMessage()
        == f"Ignoring vehicle with missing details: {MISSING_DETAILS_VIN}"
    ] == ["WARNING"]

    caplog.clear()
    await _async_poll_vehicle_list(hass, freezer)

    assert mock_get_vehicle_details.await_count == 2
    # The warning is only logged once for each vehicle.
    assert [
        record.levelname
        for record in caplog.records
        if record.getMessage()
        == f"Ignoring vehicle with missing details: {MISSING_DETAILS_VIN}"
    ] == ["DEBUG"]
    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            exceptions.QuotaLimitException(
                "err.func.wired.overloaded", "You have reached your quota limit"
            ),
            id="quota_limit",
        ),
        pytest.param(
            exceptions.KamereonResponseException(
                "err.func.unknown", "Something went wrong"
            ),
            id="kamereon_error",
        ),
    ],
)
async def test_vehicle_list_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test an error during the vehicle list update keeps the vehicles."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_get_vehicles.side_effect = side_effect
    await _async_poll_vehicle_list(hass, freezer)

    assert mock_get_vehicles.await_count == 2
    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_list_authentication_expired(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
) -> None:
    """Test an expired login during the vehicle list update starts a reauth flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_get_vehicles.side_effect = NotAuthenticatedException("Not logged in")
    await _async_poll_vehicle_list(hass, freezer)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_details_authentication_expired(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    mock_get_vehicle_details: AsyncMock,
) -> None:
    """Test an expired login while requesting new vehicle details starts a reauth flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, MISSING_DETAILS_VIN)
    mock_get_vehicle_details.side_effect = NotAuthenticatedException("Not logged in")
    await _async_poll_vehicle_list(hass, freezer)

    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("patch_renault_account", "fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(aiohttp.ClientConnectionError, id="client_error"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(GigyaException, id="gigya_error"),
    ],
)
async def test_vehicle_details_connection_error(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    mock_get_vehicle_details: AsyncMock,
    side_effect: type[Exception],
) -> None:
    """Test a connection error while requesting new vehicle details is retried."""
    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, MISSING_DETAILS_VIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_get_vehicle_details.side_effect = side_effect
    await _async_poll_vehicle_list(hass, freezer)
    await _async_poll_vehicle_list(hass, freezer)

    assert mock_get_vehicle_details.await_count == 3
    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.usefixtures("patch_renault_account", "sensor_platform")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_vehicle_list_throttled(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_get_vehicles: AsyncMock,
    mock_get_vehicle_details: AsyncMock,
    fixtures_with_data: dict[str, AsyncMock],
) -> None:
    """Test the Renault servers are not called while the hub is throttled."""
    mock_get_vehicles.return_value = _get_vehicles(ZOE_VIN, MISSING_DETAILS_VIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The vehicle updates just before the vehicle list update start the cooldown.
    for get_data_mock in fixtures_with_data.values():
        get_data_mock.side_effect = exceptions.QuotaLimitException(
            "err.func.wired.overloaded", "You have reached your quota limit"
        )
    freezer.tick(VEHICLE_LIST_SCAN_INTERVAL - timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_get_vehicles.await_count == 1
    assert mock_get_vehicle_details.await_count == 1
    assert _device_vins(device_registry, config_entry) == {ZOE_VIN}
