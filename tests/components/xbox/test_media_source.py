"""Tests for the Xbox media source platform."""

from httpx import HTTPStatusError, RequestError, Response, TimeoutException
import pytest
from pythonxbox.api.provider.people.models import PeopleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import (
    URI_SCHEME,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.xbox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import AsyncMock, MockConfigEntry, async_load_json_object_fixture
from tests.typing import MagicMock


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Setup media source component."""

    await async_setup_component(hass, "media_source", {})


@pytest.mark.usefixtures("xbox_live_client")
@pytest.mark.freeze_time("2025-11-06T17:12:27")
async def test_browse_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing media."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    ).as_dict() == snapshot(name="games_view")

    assert (
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135"
        )
    ).as_dict() == snapshot(name="category_view")

    assert (
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/gameclips"
        )
    ).as_dict() == snapshot(name="gameclips_view")

    assert (
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/screenshots"
        )
    ).as_dict() == snapshot(name="screenshots_view")

    assert (
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/game_media"
        )
    ).as_dict() == snapshot(name="game_media_view")

    assert (
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/community_gameclips"
        )
    ).as_dict() == snapshot(name="community_gameclips_view")

    assert (
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/community_screenshots",
        )
    ).as_dict() == snapshot(name="community_screenshots_view")


async def test_browse_media_accounts(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing media we get account view if more than 1 account is configured."""
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

    xbox_live_client.people.get_friends_by_xuid.return_value = PeopleResponse(
        **(await async_load_json_object_fixture(hass, "people_batch2.json", DOMAIN))  # type: ignore[reportArgumentType]
    )

    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Iqnavs",
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
        unique_id="277923030577271",
        minor_version=3,
    )
    config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry2.entry_id)
    await hass.async_block_till_done()

    assert config_entry2.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_loaded_entries(DOMAIN)) == 2

    assert (
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    ).as_dict() == snapshot


@pytest.mark.parametrize(
    ("media_content_id", "provider", "method"),
    [
        ("", "titlehub", "get_title_history"),
        ("/271958441785640", "titlehub", "get_title_history"),
        ("/271958441785640/1297287135", "titlehub", "get_title_info"),
        (
            "/271958441785640/1297287135/gameclips",
            "gameclips",
            "get_recent_clips_by_xuid",
        ),
        (
            "/271958441785640/1297287135/screenshots",
            "screenshots",
            "get_recent_screenshots_by_xuid",
        ),
        (
            "/271958441785640/1297287135/game_media",
            "titlehub",
            "get_title_info",
        ),
        (
            "/271958441785640/1297287135/community_gameclips",
            "gameclips",
            "get_recent_community_clips_by_title_id",
        ),
        (
            "/271958441785640/1297287135/community_screenshots",
            "screenshots",
            "get_recent_community_screenshots_by_title_id",
        ),
    ],
)
@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (
            HTTPStatusError("", request=MagicMock(), response=Response(500)),
            "request_exception",
        ),
        (
            RequestError(""),
            "request_exception",
        ),
        (TimeoutException(""), "timeout_exception"),
    ],
)
async def test_browse_media_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    media_content_id: str,
    provider: str,
    method: str,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test browsing media exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    with pytest.raises(BrowseError) as e:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}{media_content_id}")
    assert e.value.translation_key == translation_key


@pytest.mark.usefixtures("xbox_live_client")
async def test_browse_media_not_configured_exception(
    hass: HomeAssistant,
) -> None:
    """Test browsing media integration not configured exception."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock title",
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
        unique_id="2533274838782903",
        disabled_by=ConfigEntryDisabler.USER,
        minor_version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(BrowseError) as e:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert e.value.translation_key == "xbox_not_configured"


@pytest.mark.usefixtures("xbox_live_client")
async def test_browse_media_account_not_configured_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing media account not configured exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(BrowseError) as e:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/2533274838782903")
    assert e.value.translation_key == "account_not_configured"


@pytest.mark.parametrize(
    ("media_content_id", "url", "mime_type"),
    [
        (
            "/271958441785640/1297287135/screenshots/41593644-be22-43d6-b224-c7bebe14076e",
            "https://screenshotscontent-d5001.xboxlive.com/00097bbbbbbbbb23-41593644-be22-43d6-b224-c7bebe14076e/Screenshot-Original.png?sv=2015-12-11&sr=b&si=DefaultAccess&sig=ALKo3DE2HXqBTlpdyynIrH6RPKIECOF7zwotH%2Bb30Ts%3D",
            "image/png",
        ),
        (
            "/271958441785640/1297287135/gameclips/f87cc6ac-c291-4998-9124-d8b36c059b6a",
            "https://gameclipscontent-d2015.xboxlive.com/asset-d5448dbd-f45e-46ab-ae4e-a2e205a70e7c/GameClip-Original.MP4?sv=2015-12-11&sr=b&si=DefaultAccess&sig=ArSoLvy9EnQeBthGW6%2FbasedHHk0Jb6iXjI3EMq8oh8%3D&__gda__=1522241341_69f67a7a3533626ae90b52845664dc0c",
            "video/mp4",
        ),
        (
            "/271958441785640/1297287135/game_media/0",
            "https://store-images.s-microsoft.com/image/apps.35725.65457035095819016.56f55216-1bb9-40aa-8796-068cf3075fc1.c4bf34f8-ad40-4af3-914e-a85e75a76bed",
            "image/png",
        ),
        (
            "/271958441785640/1297287135/community_screenshots/504a78e5-be24-4020-a245-77cb528e91ea",
            "https://screenshotscontent-d5002.media.xboxlive.com/xuid-2535422966774043-private/504a78e5-be24-4020-a245-77cb528e91ea.PNG?skoid=296fcea0-0bf0-4a22-abf7-16b3524eba1b&sktid=68cd85cc-e0b3-43c8-ba3c-67686dbf8a67&skt=2025-11-06T10%3A21%3A06Z&ske=2025-11-07T10%3A21%3A06Z&sks=b&skv=2025-05-05&sv=2025-05-05&st=2025-11-06T10%3A35%3A59Z&se=2125-11-06T10%3A50%3A59Z&sr=b&sp=r&sig=TqUUNeuAzHawaXBTFfSVuUzuXbGOMgrDu0Q2VBTFd5U%3D",
            "image/png",
        ),
        (
            "/271958441785640/1297287135/community_gameclips/6fa2731a-8b58-4aa6-848c-4bf15734358b",
            "https://gameclipscontent-d3021.media.xboxlive.com/xuid-2535458333395495-private/6fa2731a-8b58-4aa6-848c-4bf15734358b.MP4?skoid=2938738c-0e58-4f21-9b82-98081ade42e2&sktid=68cd85cc-e0b3-43c8-ba3c-67686dbf8a67&skt=2025-11-06T08%3A20%3A51Z&ske=2025-11-07T08%3A20%3A51Z&sks=b&skv=2025-05-05&sv=2025-05-05&st=2025-11-06T10%3A05%3A41Z&se=2125-11-06T10%3A20%3A41Z&sr=b&sp=r&sig=s%2FWDtmE2cnAwl9iJJFcch3knbRlkxkALoinHQwCnNP0%3D&__gda__=1762438393_eb8a56c3f482d00099045aa892a2aa05",
            "video/mp4",
        ),
    ],
    ids=[
        "screenshot",
        "gameclips",
        "game_media",
        "community_screenshots",
        "community_gameclips",
    ],
)
@pytest.mark.usefixtures("xbox_live_client")
async def test_resolve_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_content_id: str,
    url: str,
    mime_type: str,
) -> None:
    """Test resolve media."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}{media_content_id}",
        None,
    )
    assert media.url == url
    assert media.mime_type == mime_type


@pytest.mark.parametrize(
    ("media_content_id", "provider", "method"),
    [
        (
            "/271958441785640/1297287135/screenshots/41593644-be22-43d6-b224-c7bebe14076e",
            "screenshots",
            "get_recent_screenshots_by_xuid",
        ),
        (
            "/271958441785640/1297287135/gameclips/f87cc6ac-c291-4998-9124-d8b36c059b6a",
            "gameclips",
            "get_recent_clips_by_xuid",
        ),
        (
            "/271958441785640/1297287135/community_screenshots/504a78e5-be24-4020-a245-77cb528e91ea",
            "screenshots",
            "get_recent_community_screenshots_by_title_id",
        ),
        (
            "/271958441785640/1297287135/community_gameclips/6fa2731a-8b58-4aa6-848c-4bf15734358b",
            "gameclips",
            "get_recent_community_clips_by_title_id",
        ),
        (
            "/271958441785640/1297287135/game_media/0",
            "titlehub",
            "get_title_info",
        ),
    ],
)
@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (
            HTTPStatusError("", request=MagicMock(), response=Response(500)),
            "request_exception",
        ),
        (RequestError(""), "request_exception"),
        (TimeoutException(""), "timeout_exception"),
    ],
)
async def test_resolve_media_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    media_content_id: str,
    provider: str,
    method: str,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test resolve media exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    with pytest.raises(Unresolvable) as e:
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}{media_content_id}",
            None,
        )
    assert e.value.translation_key == translation_key


@pytest.mark.parametrize(("media_type"), ["screenshots", "gameclips", "game_media"])
@pytest.mark.usefixtures("xbox_live_client")
async def test_resolve_media_not_found_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    media_type: str,
) -> None:
    """Test resolve media not found exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(Unresolvable) as e:
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/271958441785640/1297287135/{media_type}/12345",
            None,
        )
    assert e.value.translation_key == "media_not_found"


@pytest.mark.usefixtures("xbox_live_client")
async def test_resolve_media_not_configured(
    hass: HomeAssistant,
) -> None:
    """Test resolve media integration not configured exception."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock title",
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
        unique_id="2533274838782903",
        disabled_by=ConfigEntryDisabler.USER,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(Unresolvable) as e:
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/2533274838782903",
            None,
        )
    assert e.value.translation_key == "xbox_not_configured"


@pytest.mark.usefixtures("xbox_live_client")
async def test_resolve_media_account_not_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test resolve media account not configured exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(Unresolvable) as e:
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/2533274838782903",
            None,
        )
    assert e.value.translation_key == "account_not_configured"
