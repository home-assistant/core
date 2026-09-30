"""Test the Bosch Smart Home Camera config flow, setup and camera platform."""

import base64
from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.bosch_shc_camera.application_credentials import (
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)
from homeassistant.components.bosch_shc_camera.config_flow import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"

ACCOUNT_ID = "fake-account-sub"
CAMERA_ID = "11111111-1111-1111-1111-111111111111"
CAMERAS = [
    Camera(
        CAMERA_ID, "Garden", "HOME_Eyes_Outdoor", CameraModel.EYES_OUTDOOR_II, "9.40.25"
    )
]
ENTITY_ID = "camera.garden"
OTHER_ID = "22222222-2222-2222-2222-222222222222"
OTHER = Camera(OTHER_ID, "Hall", "SOMETHING_NEW", CameraModel.UNKNOWN, None)


def _fake_access_token(claims: dict[str, object]) -> str:
    """Build an unsigned fake JWT access token from the given claims."""

    def _part(value: dict[str, object]) -> str:
        raw = json.dumps(value).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return ".".join([_part({"alg": "none"}), _part(claims), "sig"])


pytestmark = pytest.mark.usefixtures("current_request_with_host")


@pytest.fixture(autouse=True)
async def setup_application_credentials(hass: HomeAssistant) -> None:
    """Set up the application credentials component."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with a valid token."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="fake-account-sub",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "expires_at": dt_util.utcnow().timestamp() + 3600,
            },
        },
    )


@pytest.fixture(autouse=True)
def mock_list_cameras() -> Generator[AsyncMock]:
    """Mock the camera list of the library."""
    with patch(
        "homeassistant.components.bosch_shc_camera.coordinator.list_cameras",
        autospec=True,
        return_value=list(CAMERAS),
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register the OAuth2 application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("fake-client-id", "fake-client-secret")
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the OAuth2 flow creates an entry that loads and unloads."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    parsed = urlparse(result["url"])
    query = {key: value[0] for key, value in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == OAUTH2_AUTHORIZE
    assert query["client_id"] == OAUTH2_CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["scope"] == OAUTH2_SCOPES
    assert query["code_challenge_method"] == "S256"

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": _fake_access_token({"sub": ACCOUNT_ID}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bosch Smart Home Camera"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == _fake_access_token(
        {"sub": ACCOUNT_ID}
    )
    assert result["result"].unique_id == ACCOUNT_ID
    assert "code_verifier" in aioclient_mock.mock_calls[0][2]

    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test a second config entry is rejected."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthentication updates the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "expires_at": 0,
            },
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": _fake_access_token({"sub": ACCOUNT_ID}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data["token"]["access_token"] == _fake_access_token(
        {"sub": ACCOUNT_ID}
    )
    assert entry.data["token"]["refresh_token"] == "new-refresh-token"


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthenticating with a different account is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "old", "refresh_token": "old", "expires_at": 0},
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": _fake_access_token({"sub": "other-account-sub"}),
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data["token"]["access_token"] == "old"


@pytest.mark.parametrize(
    "access_token",
    [
        _fake_access_token({"iss": "fake"}),
        "not-a-jwt",
        _fake_access_token({"sub": 123}),
        _fake_access_token({"sub": ""}),
        _fake_access_token({"sub": "   "}),
        _fake_access_token({"sub": ["a"]}),
        _fake_access_token({"sub": "a" * 129}),
    ],
    ids=[
        "missing_sub",
        "malformed",
        "int_sub",
        "empty_sub",
        "whitespace_sub",
        "list_sub",
        "too_long_sub",
    ],
)
async def test_invalid_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
) -> None:
    """Test a token without a usable subject aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


async def test_camera_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a camera entity and its device are created from the list."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == "idle"
    assert entity_registry.async_get(ENTITY_ID).unique_id == CAMERA_ID
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
    assert device.name == "Garden"
    assert device.manufacturer == "Bosch"
    assert device.model == "Eyes Outdoor II"
    assert device.sw_version == "9.40.25"


async def test_unknown_model_uses_hardware_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a model outside the known lineup falls back to the raw value."""
    mock_list_cameras.return_value = [OTHER]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )
    assert device.model == "SOMETHING_NEW"
    assert device.sw_version is None


async def test_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test the entry unloads."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (BoschCameraConnectionError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraInvalidResponseError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraAuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test library errors map to retry or reauthentication."""
    mock_list_cameras.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
    assert bool(list(mock_config_entry.async_get_active_flows(hass, {"reauth"}))) is (
        error is BoschCameraAuthError
    )


async def test_update_failure_makes_camera_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing poll marks the camera unavailable and recovers."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.side_effect = BoschCameraConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_list_cameras.side_effect = None
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "idle"


async def test_auth_failure_during_update_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token during a poll starts reauthentication."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.side_effect = BoschCameraAuthError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert list(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_camera_added_and_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cameras appear and disappear with the account."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("camera.hall") is None

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get(ENTITY_ID).state == "idle"

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None


async def test_stale_device_removed_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device of a camera removed while Home Assistant was off is dropped."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, OTHER_ID)},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
