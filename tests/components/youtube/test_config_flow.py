"""Test the YouTube config flow."""

from unittest.mock import patch

import pytest
from youtubeaio.types import ForbiddenError

from homeassistant import config_entries
from homeassistant.components.youtube.const import (
    CONF_CHANNEL_ID,
    CONF_CHANNELS,
    DOMAIN,
    SUBENTRY_TYPE_CHANNEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import MockYouTube
from .conftest import (
    CHANNEL_ID,
    CLIENT_ID,
    GOOGLE_AUTH_URI,
    GOOGLE_TOKEN_URI,
    SCOPES,
    TITLE,
    ComponentSetup,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

LINUS_CHANNEL_ID = "UCXuqSBlHAE6Xw-yeJA0Tunw"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with (
        patch(
            "homeassistant.components.youtube.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.youtube.config_flow.YouTube",
            return_value=MockYouTube(hass),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "channels"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CHANNELS: [CHANNEL_ID]}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert "result" in result
    entry = result["result"]
    assert entry.unique_id == CHANNEL_ID
    assert entry.version == 2
    assert "token" in entry.data
    assert entry.data["token"]["access_token"] == "mock-access-token"
    assert entry.data["token"]["refresh_token"] == "mock-refresh-token"
    assert entry.options == {}
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_CHANNEL
    assert subentry.unique_id == CHANNEL_ID
    assert subentry.title == "Google for Developers"
    assert subentry.data == {CONF_CHANNEL_ID: CHANNEL_ID}


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_abort_without_channel(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check abort flow if user has no channel."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    service = MockYouTube(hass, channel_fixture="get_no_channel.json")
    with (
        patch("homeassistant.components.youtube.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.youtube.config_flow.YouTube", return_value=service
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_channel"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_abort_without_subscriptions(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check abort flow if user has no subscriptions and no own channel."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    service = MockYouTube(
        hass,
        channel_fixture="get_no_channel.json",
        subscriptions_fixture="get_no_subscriptions.json",
    )
    with (
        patch("homeassistant.components.youtube.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.youtube.config_flow.YouTube", return_value=service
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_channel"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_without_subscriptions(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check flow continues without subscriptions using own channel."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    service = MockYouTube(hass, subscriptions_fixture="get_no_subscriptions.json")
    with (
        patch("homeassistant.components.youtube.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.youtube.config_flow.YouTube", return_value=service
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "channels"

        # Verify the form schema contains only the user's own channel
        schema = result["data_schema"]
        channels = schema.schema[CONF_CHANNELS].config["options"]
        assert len(channels) == 1
        assert channels[0]["value"] == CHANNEL_ID
        assert "(Your Channel)" in channels[0]["label"]

        # Test selecting the own channel
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CHANNELS: [CHANNEL_ID]},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert "result" in result
    entry = result["result"]
    assert entry.unique_id == CHANNEL_ID
    assert "token" in entry.data
    assert entry.data["token"]["access_token"] == "mock-access-token"
    assert entry.data["token"]["refresh_token"] == "mock-refresh-token"
    assert entry.options == {}
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.unique_id == CHANNEL_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_http_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.youtube.config_flow.YouTube.get_user_channels",
        side_effect=ForbiddenError(
            "YouTube Data API v3 has not been used in project 0"
            " before or it is disabled. Enable it by visiting"
            " https://console.developers.google.com/apis/api/"
            "youtube.googleapis.com/overview?project=0 then"
            " retry. If you enabled this API recently, wait a"
            " few minutes for the action to propagate to our"
            " systems and retry."
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "access_not_configured"
        assert result["description_placeholders"]["message"] == (
            "YouTube Data API v3 has not been used in project 0"
            " before or it is disabled. Enable it by visiting"
            " https://console.developers.google.com/apis/api/"
            "youtube.googleapis.com/overview?project=0 then"
            " retry. If you enabled this API recently, wait a"
            " few minutes for the action to propagate to our"
            " systems and retry."
        )


@pytest.mark.parametrize(
    ("fixture", "abort_reason", "placeholders", "call_count", "access_token"),
    [
        (
            "get_channel",
            "reauth_successful",
            None,
            1,
            "updated-access-token",
        ),
        (
            "get_channel_2",
            "wrong_account",
            {"title": "Linus Tech Tips"},
            0,
            "mock-access-token",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    fixture: str,
    abort_reason: str,
    placeholders: dict[str, str],
    call_count: int,
    access_token: str,
) -> None:
    """Test the re-authentication case updates the correct config entry.

    Make sure we abort if the user selects the
    wrong account on the consent screen.
    """
    config_entry.add_to_hass(hass)

    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "updated-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    youtube = MockYouTube(hass, channel_fixture=f"{fixture}.json")
    with (
        patch(
            "homeassistant.components.youtube.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.youtube.config_flow.YouTube",
            return_value=youtube,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason
    assert result["description_placeholders"] == placeholders
    assert len(mock_setup.mock_calls) == call_count

    assert config_entry.unique_id == CHANNEL_ID
    assert "token" in config_entry.data
    # Verify access token is refreshed
    assert config_entry.data["token"]["access_token"] == access_token
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_exception(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check full flow."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.youtube.config_flow.YouTube", side_effect=Exception
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_own_channel_included(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test user's own channel is included in selectable channels."""
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

    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with (
        patch(
            "homeassistant.components.youtube.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.youtube.config_flow.YouTube",
            return_value=MockYouTube(hass),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "channels"

        # Verify the form schema contains the user's own channel
        schema = result["data_schema"]
        channels = schema.schema[CONF_CHANNELS].config["options"]
        assert any(
            channel["value"] == CHANNEL_ID and "(Your Channel)" in channel["label"]
            for channel in channels
        )

        # Test selecting both own channel and a subscribed channel
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CHANNELS: [CHANNEL_ID, CHANNEL_ID]},
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert "result" in result
    entry = result["result"]
    assert entry.unique_id == CHANNEL_ID
    assert "token" in entry.data
    assert entry.data["token"]["access_token"] == "mock-access-token"
    assert entry.data["token"]["refresh_token"] == "mock-refresh-token"
    assert entry.options == {}
    # Duplicate selections are deduplicated into a single subentry
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.unique_id == CHANNEL_ID
    assert subentry.title == "Google for Developers"


async def test_subentry_flow_add_channel(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test adding a channel subentry."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with (
        patch(
            "homeassistant.components.youtube.config_flow.YouTube",
            return_value=MockYouTube(hass, channel_fixture="get_channel_2.json"),
        ),
        patch(
            "homeassistant.components.youtube.api.YouTube",
            return_value=MockYouTube(
                hass, extra_channel_fixtures=["get_channel_2.json"]
            ),
        ),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # The already configured channel is not selectable
        options = result["data_schema"].schema[CONF_CHANNEL_ID].config["options"]
        assert [option["value"] for option in options] == [LINUS_CHANNEL_ID]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: LINUS_CHANNEL_ID}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Linus Tech Tips"
    assert result["data"] == {CONF_CHANNEL_ID: LINUS_CHANNEL_ID}
    assert len(entry.subentries) == 2
    new_subentry = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == LINUS_CHANNEL_ID
    )
    assert new_subentry.title == "Linus Tech Tips"
    assert hass.states.get("sensor.linus_tech_tips_subscribers") is not None


async def test_subentry_flow_no_channels_left(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test the subentry flow aborts when all channels are already tracked."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(
        "homeassistant.components.youtube.config_flow.YouTube",
        return_value=MockYouTube(hass),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_subscriptions"
