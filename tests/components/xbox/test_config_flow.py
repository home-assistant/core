"""Test the xbox config flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from httpx import HTTPStatusError, RequestError, TimeoutException
import pytest
from pythonxbox.api.provider.people.models import PeopleResponse

from homeassistant import config_entries
from homeassistant.components.xbox.const import (
    CONF_XUID,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .conftest import CLIENT_ID

from tests.common import MockConfigEntry, async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""

    result = await hass.config_entries.flow.async_init(
        "xbox", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    scope = "Xboxlive.signin+Xboxlive.offline_access"

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )

    with patch(
        "homeassistant.components.xbox.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["result"].unique_id == "271958441785640"
    assert result["result"].title == "GSR Ae"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    ("source", "service_info"),
    [
        (
            config_entries.SOURCE_DHCP,
            DhcpServiceInfo(
                hostname="xboxone",
                ip="192.168.0.1",
                macaddress="aaaaaaaaaaaa",
            ),
        ),
        (
            config_entries.SOURCE_SSDP,
            SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                upnp={"manufacturer": "Microsoft Corporation", "modelName": "Xbox One"},
            ),
        ),
    ],
)
@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_discovery(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    source: str,
    service_info: Any,
) -> None:
    """Check DHCP/SSDP discovery."""

    result = await hass.config_entries.flow.async_init(
        "xbox", context={"source": source}, data=service_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=Xboxlive.signin+Xboxlive.offline_access"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )

    with patch(
        "homeassistant.components.xbox.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["result"].unique_id == "271958441785640"
    assert result["result"].title == "GSR Ae"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_form_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort flow when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_form_already_configured_as_subentry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we abort flow when entry is already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ikken Hissatsuu",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="friend",
                title="GSR Ae",
                unique_id="271958441785640",
            ),
        ],
        unique_id="2533274838782903",
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_as_subentry"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_add_friend_flow(hass: HomeAssistant) -> None:
    """Test add friend subentry flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GSR Ae",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id="271958441785640",
        minor_version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "friend"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_XUID: "2533274913657542"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={},
            subentry_id=subentry_id,
            subentry_type="friend",
            title="erics273",
            unique_id="2533274913657542",
        )
    }


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_add_friend_flow_already_configured(hass: HomeAssistant) -> None:
    """Test add friend subentry flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GSR Ae",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="friend",
                title="erics273",
                unique_id="2533274913657542",
            )
        ],
        unique_id="271958441785640",
        minor_version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "friend"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_XUID: "2533274913657542"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_add_friend_flow_already_configured_as_entry(hass: HomeAssistant) -> None:
    """Test add friend subentry flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GSR Ae",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id="271958441785640",
        minor_version=3,
    )
    MockConfigEntry(
        domain=DOMAIN,
        title="erics273",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id="2533274913657542",
        minor_version=3,
    ).add_to_hass(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "friend"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_XUID: "2533274913657542"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_as_entry"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "authentication_manager",
)
async def test_add_friend_flow_no_friends(
    hass: HomeAssistant, xbox_live_client: AsyncMock
) -> None:
    """Test add friend subentry flow."""
    xbox_live_client.people.get_friends_own.return_value = PeopleResponse(
        **await async_load_json_object_fixture(
            hass, "people_friends_own_no_friends.json", DOMAIN
        )  # type: ignore[reportArgumentType]
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="GSR Ae",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id="271958441785640",
        minor_version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "friend"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_friends"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "xbox_live_client",
    "authentication_manager",
)
async def test_add_friend_flow_config_entry_not_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test add friend subentry flow."""
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "friend"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_loaded"


@pytest.mark.usefixtures("xbox_live_client", "authentication_manager")
async def test_unique_id_and_friends_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test config entry unique_id migration and favorite to subentry migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Cloud",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
    )

    config_entry.add_to_hass(hass)

    device_own = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "xbox_live")},
    )

    device_friend = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "2533274838782903")},
    )
    assert device_friend.config_entries_subentries[config_entry.entry_id] == {None}

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.LOADED
    assert config_entry.version == 1
    assert config_entry.minor_version == 3
    assert config_entry.unique_id == "271958441785640"
    assert config_entry.title == "GSR Ae"

    # Assert favorite friends migrated to subentries
    assert len(config_entry.subentries) == 1
    subentries = list(config_entry.subentries.values())
    assert subentries[0].unique_id == "2533274838782903"
    assert subentries[0].title == "Ikken Hissatsuu"
    assert subentries[0].subentry_type == "friend"

    ## Assert devices have been migrated
    assert (device_own := device_registry.async_get(device_own.id))
    assert device_own.identifiers == {(DOMAIN, "271958441785640")}

    assert (device_friend := device_registry.async_get(device_friend.id))
    assert device_friend.config_entries_subentries[config_entry.entry_id] == {
        subentries[0].subentry_id
    }


@pytest.mark.parametrize(
    ("provider", "method"),
    [
        ("people", "get_friends_by_xuid"),
        ("people", "get_friends_own"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        TimeoutException(""),
        RequestError("", request=Mock()),
        HTTPStatusError("", request=Mock(), response=Mock()),
    ],
)
@pytest.mark.usefixtures("authentication_manager")
async def test_migration_exceptions(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    provider: str,
    method: str,
    exception: Exception,
) -> None:
    """Test exceptions during migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Cloud",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
    )

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR


@pytest.mark.usefixtures("xbox_live_client", "authentication_manager")
async def test_migration_implementation_unavailable(hass: HomeAssistant) -> None:
    """Test implementation unavailable exception during migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Cloud",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
    )

    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xbox.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR


@pytest.mark.usefixtures(
    "xbox_live_client",
    "current_request_with_host",
    "authentication_manager",
)
async def test_flow_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow."""

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    scope = "Xboxlive.signin+Xboxlive.offline_access"

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )
    with patch(
        "homeassistant.components.xbox.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    assert config_entry.data["token"]["access_token"] == "new-access-token"


@pytest.mark.usefixtures(
    "xbox_live_client",
    "current_request_with_host",
    "authentication_manager",
)
async def test_flow_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we abort reauth flow on unique id mismatch."""

    xbox_live_client.xuid = "277923030577271"

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    scope = "Xboxlive.signin+Xboxlive.offline_access"

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "XboxLive.signin XboxLive.offline_access",
            "service": "xbox",
            "token_type": "bearer",
            "user_id": "AAAAAAAAAAAAAAAAAAAAA",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
