"""Test the Teslemetry config flow."""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientConnectionError
from bleak.exc import BleakError
import pytest
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    InvalidToken,
    NotOnWhitelistFault,
    SubscriptionRequired,
    TeslaFleetError,
    WhitelistOperationAttemptingToAddExistingKey,
)
from tesla_fleet_api.tesla import VehicleRouter
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.components.teslemetry.const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    CONF_VIN,
    DOMAIN,
    SUBENTRY_TYPE_VEHICLE,
    TOKEN_URL,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentryData,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)

from . import mock_config_entry, setup_platform
from .const import CONFIG_V1, UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    assert result["url"].startswith(AUTHORIZE_URL)
    parsed_url = urlparse(result["url"])
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_query["response_type"][0] == "code"
    assert parsed_query["client_id"][0] == CLIENT_ID
    assert parsed_query["redirect_uri"][0] == REDIRECT
    assert parsed_query["state"][0] == state
    assert parsed_query["code_challenge"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    response = {
        "refresh_token": "test_refresh_token",
        "access_token": "test_access_token",
        "type": "Bearer",
        "expires_in": 60,
    }

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json=response,
    )

    # Complete OAuth
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID
    assert result["data"]["auth_implementation"] == "teslemetry"
    assert result["data"]["token"]["refresh_token"] == response["refresh_token"]
    assert result["data"]["token"]["access_token"] == response["access_token"]
    assert result["data"]["token"]["type"] == response["type"]
    assert result["data"]["token"]["expires_in"] == response["expires_in"]
    assert "expires_at" in result["result"].data["token"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow."""

    mock_entry = await setup_platform(hass, [])

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    # Progress from reauth_confirm to external OAuth step
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Tesla Fleet reauthentication with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    result = await old_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test duplicate unique ID aborts flow."""
    # Create existing entry
    await setup_platform(hass, [])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Complete OAuth - should abort due to duplicate unique_id
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
) -> None:
    """Test OAuth flow with various API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated
    assert mock_entry.data["auth_implementation"] == DOMAIN
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"
    assert mock_entry.data["token"]["type"] == "Bearer"
    assert mock_entry.data["token"]["expires_in"] == 60
    assert "expires_at" in mock_entry.data["token"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    result = await old_entry.start_reconfigure_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_reconfigure_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
    exception: Exception,
) -> None:
    """Test reconfigure flow with various API errors."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_oauth_error_recovery(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow can recover from an OAuth error."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    # First attempt - simulate OAuth error
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"

    # Second attempt - should succeed (recovery)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.clear_requests()
    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated after recovery
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"


async def test_migrate_error_from_future(
    hass: HomeAssistant, mock_metadata: AsyncMock
) -> None:
    """Test a future version isn't migrated."""

    mock_metadata.side_effect = TeslaFleetError

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        minor_version=1,
        unique_id="abc-123",
        data=CONFIG_V1,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


VIN = "LRW3F7EK4NC700000"
ADDRESS = "AA:BB:CC:DD:EE:FF"


def _entry_with_ble() -> MockConfigEntry:
    """Return a config entry whose vehicle subentry is already BLE-paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_VEHICLE,
                unique_id=VIN,
                title="Test",
                data={CONF_VIN: VIN, CONF_ADDRESS: ADDRESS},
            )
        ],
    )


def _discovered_info() -> MagicMock:
    """Return a fake discovered service info matching the test VIN."""
    info = MagicMock()
    info.name = TeslaBluetooth().get_name(VIN)
    info.address = ADDRESS
    info.device = MagicMock()
    return info


def _mock_vehicle(*, on_whitelist: bool = True) -> AsyncMock:
    """Return a mock VehicleBluetooth for the pairing flow."""
    vehicle = AsyncMock()
    if on_whitelist:
        vehicle.handshakeVehicleSecurity = AsyncMock()
    else:
        vehicle.handshakeVehicleSecurity = AsyncMock(
            side_effect=[NotOnWhitelistFault(), None]
        )
    return vehicle


def _mock_ble_parent(vehicle: AsyncMock | None = None) -> MagicMock:
    """Return a mock shared TeslaBluetooth parent for the pairing flow."""
    parent = MagicMock()
    parent.get_name.return_value = TeslaBluetooth().get_name(VIN)
    if vehicle is not None:
        parent.vehicles.createBluetooth.return_value = vehicle
    return parent


async def _setup_account_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an account entry with no vehicle subentry.

    Local control is opt-in: no Bluetooth subentry exists until the user pairs a
    vehicle through the add flow, so a fresh account entry starts with none.
    """
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _setup_paired_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose only account vehicle is already BLE-paired."""
    entry = _entry_with_ble()
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _start_pairing_at_scan(
    hass: HomeAssistant, entry: MockConfigEntry
) -> SubentryFlowResult:
    """Open the add flow and advance past VIN selection to the scan step."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_VIN: VIN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    return result


async def test_subentry_pairing_already_whitelisted(hass: HomeAssistant) -> None:
    """The add flow creates the subentry when the key is already whitelisted."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle(on_whitelist=True)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    # The subentry is created atomically with its credentials, never identity-only.
    assert subentries[0].unique_id == VIN
    assert subentries[0].data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}
    vehicle.connect.assert_awaited_once()
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing walks through instructions and key install when not whitelisted."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle(on_whitelist=False)
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        # scan -> connect -> handshake raises NotOnWhitelistFault -> instructions
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "pair"

        # pair() completes -> progress done -> handshake ok -> finish
        release.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    assert subentries[0].data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}
    vehicle.pair.assert_awaited_once()


async def test_subentry_scan_connect_fails(hass: HomeAssistant) -> None:
    """The scan step re-shows the form with an error when BLE connect fails."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle()
    vehicle.connect = AsyncMock(side_effect=BleakError("nope"))

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "cannot_connect"}
    # A failed pairing never creates a subentry.
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    vehicle.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BluetoothTimeout, "timeout"),
        (BluetoothTransportError, "cannot_connect"),
        (TeslaFleetError, "pair_failed"),
    ],
    ids=["timeout", "transport", "rejected"],
)
async def test_subentry_authorize_failure(
    hass: HomeAssistant, error: type[TeslaFleetError], expected: str
) -> None:
    """Each pairing failure surfaces its own error, not a blanket timeout."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle(on_whitelist=False)
    release = asyncio.Event()

    async def _pair() -> None:
        await release.wait()
        raise error

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # pair() fails -> progress done -> instructions re-shown with the error
        release.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instructions"
    assert result["errors"] == {"base": expected}
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    # pair() is a single bounded op; it is never re-sent.
    vehicle.pair.assert_awaited_once()


async def test_subentry_authorize_existing_key_finishes(hass: HomeAssistant) -> None:
    """Approving the key after a timeout, then retrying, completes the pairing."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle(on_whitelist=False)
    releases = [asyncio.Event(), asyncio.Event()]
    attempts = iter(
        zip(
            releases,
            [BluetoothTimeout(), WhitelistOperationAttemptingToAddExistingKey()],
            strict=True,
        )
    )

    async def _pair() -> None:
        release, error = next(attempts)
        await release.wait()
        raise error

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "instructions"

        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # the vehicle never confirms -> instructions re-shown, asking for approval
        releases[0].set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "timeout"}

        # the user approves the key and retries -> pair() runs again
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # the vehicle reports the key already exists -> handshake confirms -> finish
        releases[1].set()
        await hass.async_block_till_done()
        result = await hass.config_entries.subentries.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    assert subentries[0].data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}
    assert vehicle.pair.await_count == 2
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_handshake_error_aborts(hass: HomeAssistant) -> None:
    """A handshake failure aborts with cannot_connect; a disconnect error is swallowed."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle()
    vehicle.handshakeVehicleSecurity = AsyncMock(side_effect=TeslaFleetError())
    vehicle.disconnect = AsyncMock(side_effect=BleakError("boom"))

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    vehicle.disconnect.assert_awaited_once()


async def test_subentry_pairing_abandoned(hass: HomeAssistant) -> None:
    """Abandoning the flow mid-pairing cancels the pair task and disconnects."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle(on_whitelist=False)
    cancelled = asyncio.Event()

    async def _pair() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    vehicle.pair = AsyncMock(side_effect=_pair)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        # confirm instructions -> authorize runs pair() as a progress task
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # abandon the flow while pairing is still running
        hass.config_entries.subentries.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    assert cancelled.is_set()
    vehicle.disconnect.assert_awaited_once()
    # An abandoned pairing never creates a subentry.
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)


async def test_subentry_scan_device_not_found(hass: HomeAssistant) -> None:
    """The scan step re-shows the form with an error when no device is found."""
    entry = await _setup_account_entry(hass)

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(),
        ),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "device_not_found"}
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)


async def test_subentry_scan_finds_device_after_active_scan(
    hass: HomeAssistant,
) -> None:
    """An awake in-range car only in scan responses is found via active scan."""
    entry = await _setup_account_entry(hass)
    vehicle = _mock_vehicle()
    mock_discovered = MagicMock(return_value=[])

    async def _active_scan(hass: HomeAssistant) -> None:
        mock_discovered.return_value = [_discovered_info()]

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            mock_discovered,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_request_active_scan",
            AsyncMock(side_effect=_active_scan),
        ) as mock_active_scan,
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_pairing_at_scan(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    mock_active_scan.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    assert subentries[0].data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}
    vehicle.connect.assert_awaited_once()


async def test_subentry_add_flow_keeps_device_on_parent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The add flow pairs an account vehicle without moving its device off the parent entry."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # No Bluetooth subentry exists until the user adds one.
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    existing_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VIN), entry.entry_id
    )
    assert existing_device is not None
    # The device and its entities start on the parent entry, owned by no subentry.
    assert existing_device.config_subentry_id is None
    vehicle_entities = er.async_entries_for_device(
        entity_registry, existing_device.id, include_disabled_entities=True
    )
    assert vehicle_entities
    assert all(entity.config_subentry_id is None for entity in vehicle_entities)

    vehicle = _mock_vehicle(on_whitelist=True)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # async_schedule_reload is deliberately left unpatched: the subentry is
    # committed only after the flow step returns, so the real reload the parent
    # entry's subentry-change listener schedules must run here with the BLE
    # address present. Keep the setup-time Bluetooth mocks active so that reload
    # neither writes the vehicle key file nor opens a real connection.
    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.async_discovered_service_info",
            return_value=[_discovered_info()],
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.async_get_ble_parent",
            return_value=_mock_ble_parent(vehicle),
        ),
        patch(
            "homeassistant.components.teslemetry.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_private_key = AsyncMock()
        mock_parent.return_value.vehicles.createBluetooth.return_value = MagicMock()

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_VIN: VIN}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "scan"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        # The subentry commits after the flow step returns; its change listener
        # then schedules the reload, which runs to completion here.
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentries = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
    assert len(subentries) == 1
    subentry = subentries[0]
    assert subentry.unique_id == VIN
    assert subentry.data == {CONF_VIN: VIN, CONF_ADDRESS: ADDRESS}

    # The real reload picked up the stored address: the reloaded vehicle now
    # routes over Bluetooth instead of staying cloud-only.
    assert isinstance(entry.runtime_data.vehicles[0].api, VehicleRouter)

    # The pairing reuses the vehicle's existing device, never a duplicate.
    bound_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VIN), entry.entry_id
    )
    assert bound_device is not None
    # The same device ID is kept and it stays on the parent entry, not the
    # subentry, so removing the pairing never deletes the cloud vehicle.
    assert bound_device.id == existing_device.id
    assert bound_device.config_subentry_id is None

    # The vehicle entities keep their unique IDs and stay on the parent entry.
    bound_entities = er.async_entries_for_device(
        entity_registry, bound_device.id, include_disabled_entities=True
    )
    assert {entity.unique_id for entity in bound_entities} == {
        entity.unique_id for entity in vehicle_entities
    }
    assert all(entity.config_subentry_id is None for entity in bound_entities)


async def test_subentry_add_flow_no_available_vehicles(hass: HomeAssistant) -> None:
    """The add flow aborts when every account vehicle is already added."""
    entry = await _setup_paired_entry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_vehicles"


async def test_subentry_add_flow_entry_not_loaded(hass: HomeAssistant) -> None:
    """The add flow aborts when the parent entry is not loaded."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_VEHICLE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
