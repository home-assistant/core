"""Tests for the Mastodon services."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from mastodon.Mastodon import MastodonAPIError, MastodonNotFoundError, MediaAttachment
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mastodon.const import (
    ATTR_ACCOUNT_NAME,
    ATTR_CONTENT_WARNING,
    ATTR_DURATION,
    ATTR_HIDE_NOTIFICATIONS,
    ATTR_IDEMPOTENCY_KEY,
    ATTR_LANGUAGE,
    ATTR_MEDIA,
    ATTR_MEDIA_DESCRIPTION,
    ATTR_STATUS,
    ATTR_VISIBILITY,
    DOMAIN,
)
from homeassistant.components.mastodon.services import (
    SERVICE_GET_ACCOUNT,
    SERVICE_MUTE_ACCOUNT,
    SERVICE_POST,
    SERVICE_UNMUTE_ACCOUNT,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_get_account_success(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_account service successfully returns account data."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ACCOUNT,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
        },
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )


async def test_get_account_failure(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_account service handles API errors."""
    await setup_integration(hass, mock_config_entry)

    # Test API error (this is the only error type currently caught by the service)
    mock_mastodon_client.account_lookup.side_effect = MastodonAPIError("API error")
    with pytest.raises(
        HomeAssistantError,
        match='Unable to get account "@test@mastodon.social"',
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@test@mastodon.social",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    (
        "service_data",
        "expected_notifications",
        "expected_duration",
    ),
    [
        (
            {ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social"},
            True,
            None,
        ),
        (
            {
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
                ATTR_HIDE_NOTIFICATIONS: False,
            },
            False,
            None,
        ),
        (
            {
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
                ATTR_DURATION: timedelta(hours=2),
            },
            True,
            7200,
        ),
        (
            {
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
                ATTR_DURATION: timedelta(hours=12),
                ATTR_HIDE_NOTIFICATIONS: False,
            },
            False,
            43200,
        ),
    ],
)
async def test_mute_account_success(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service_data: dict[str, str | int | bool],
    expected_notifications: bool,
    expected_duration: int | None,
) -> None:
    """Test the mute_account service mutes the target account with all options."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUTE_ACCOUNT,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | service_data,
        blocking=True,
        return_response=False,
    )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct=service_data[ATTR_ACCOUNT_NAME]
    )
    account = mock_mastodon_client.account_lookup.return_value
    assert mock_mastodon_client.account_mute.call_count == 1
    call_args, call_kwargs = mock_mastodon_client.account_mute.call_args

    if call_kwargs:
        actual_id = call_kwargs["id"]
        actual_notifications = call_kwargs["notifications"]
        actual_duration = call_kwargs.get("duration")
    else:
        _, positional_args, _ = call_args
        actual_id, actual_notifications, actual_duration = positional_args

    assert actual_id == account.id
    assert actual_notifications == expected_notifications
    assert actual_duration == expected_duration


async def test_mute_account_duration_too_long(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test mute_account rejects overly long durations."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch("homeassistant.components.mastodon.services.MAX_DURATION_SECONDS", 5),
        pytest.raises(ServiceValidationError) as err,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MUTE_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
                ATTR_DURATION: timedelta(seconds=10),
            },
            blocking=True,
            return_response=False,
        )

    assert err.value.translation_key == "mute_duration_too_long"
    mock_mastodon_client.account_mute.assert_not_called()


async def test_mute_account_failure_not_found(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test mute_account raises validation when account does not exist."""
    await setup_integration(hass, mock_config_entry)

    mock_mastodon_client.account_lookup.side_effect = MastodonNotFoundError(
        "account not found"
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MUTE_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
            },
            blocking=True,
            return_response=False,
        )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )
    mock_mastodon_client.account_mute.assert_not_called()


async def test_mute_account_failure_api_error(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test mute_account wraps API errors with translated message."""
    await setup_integration(hass, mock_config_entry)

    mock_mastodon_client.account_mute.side_effect = MastodonAPIError("mute failed")

    with pytest.raises(
        HomeAssistantError,
        match='Unable to mute account "@trwnh@mastodon.social"',
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MUTE_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
            },
            blocking=True,
            return_response=False,
        )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )
    account = mock_mastodon_client.account_lookup.return_value
    mock_mastodon_client.account_mute.assert_called_once_with(
        id=account.id, notifications=True, duration=None
    )


async def test_unmute_account_success(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the unmute_account service unmutes the target account."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UNMUTE_ACCOUNT,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
        },
        blocking=True,
        return_response=False,
    )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )
    account = mock_mastodon_client.account_lookup.return_value
    mock_mastodon_client.account_unmute.assert_called_once_with(id=account.id)


async def test_unmute_account_failure_not_found(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unmute_account raises validation when account does not exist."""
    await setup_integration(hass, mock_config_entry)

    mock_mastodon_client.account_lookup.side_effect = MastodonNotFoundError(
        "account not found"
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UNMUTE_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
            },
            blocking=True,
            return_response=False,
        )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )
    mock_mastodon_client.account_unmute.assert_not_called()


async def test_unmute_account_failure_api_error(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unmute_account wraps API errors with translated message."""
    await setup_integration(hass, mock_config_entry)

    mock_mastodon_client.account_unmute.side_effect = MastodonAPIError("unmute failed")

    with pytest.raises(
        HomeAssistantError,
        match='Unable to unmute account "@trwnh@mastodon.social"',
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UNMUTE_ACCOUNT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_ACCOUNT_NAME: "@trwnh@mastodon.social",
            },
            blocking=True,
            return_response=False,
        )

    mock_mastodon_client.account_lookup.assert_called_once_with(
        acct="@trwnh@mastodon.social"
    )
    account = mock_mastodon_client.account_lookup.return_value
    mock_mastodon_client.account_unmute.assert_called_once_with(id=account.id)


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_STATUS: "test toot",
            },
            {
                "status": "test toot",
                "spoiler_text": None,
                "visibility": None,
                "idempotency_key": None,
                "language": None,
                "media_ids": None,
                "sensitive": None,
            },
        ),
        (
            {ATTR_STATUS: "test toot", ATTR_VISIBILITY: "private"},
            {
                "status": "test toot",
                "spoiler_text": None,
                "visibility": "private",
                "idempotency_key": None,
                "language": None,
                "media_ids": None,
                "sensitive": None,
            },
        ),
        (
            {
                ATTR_STATUS: "test toot",
                ATTR_CONTENT_WARNING: "Spoiler",
                ATTR_VISIBILITY: "private",
            },
            {
                "status": "test toot",
                "spoiler_text": "Spoiler",
                "visibility": "private",
                "idempotency_key": None,
                "language": None,
                "media_ids": None,
                "sensitive": None,
            },
        ),
        (
            {
                ATTR_STATUS: "test toot",
                ATTR_CONTENT_WARNING: "Spoiler",
                ATTR_LANGUAGE: "nl",
                ATTR_MEDIA: "/image.jpg",
            },
            {
                "status": "test toot",
                "spoiler_text": "Spoiler",
                "visibility": None,
                "idempotency_key": None,
                "language": "nl",
                "media_ids": "1",
                "sensitive": None,
            },
        ),
        (
            {
                ATTR_STATUS: "test toot",
                ATTR_CONTENT_WARNING: "Spoiler",
                ATTR_LANGUAGE: "en",
                ATTR_MEDIA: "/image.jpg",
                ATTR_MEDIA_DESCRIPTION: "A test image",
            },
            {
                "status": "test toot",
                "spoiler_text": "Spoiler",
                "visibility": None,
                "idempotency_key": None,
                "language": "en",
                "media_ids": "1",
                "sensitive": None,
            },
        ),
        (
            {ATTR_STATUS: "test toot", ATTR_LANGUAGE: "invalid-lang"},
            {
                "status": "test toot",
                "language": "invalid-lang",
                "spoiler_text": None,
                "visibility": None,
                "idempotency_key": None,
                "media_ids": None,
                "sensitive": None,
            },
        ),
        (
            {
                ATTR_STATUS: "test toot\nwith idempotency",
                ATTR_IDEMPOTENCY_KEY: "post_once_only",
            },
            {
                "status": "test toot\nwith idempotency",
                "idempotency_key": "post_once_only",
                "language": None,
                "spoiler_text": None,
                "visibility": None,
                "media_ids": None,
                "sensitive": None,
            },
        ),
    ],
)
async def test_service_post(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, str],
    kwargs: dict[str, str | None],
) -> None:
    """Test the post service."""

    await setup_integration(hass, mock_config_entry)

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch.object(
            mock_mastodon_client, "media_post", return_value=MediaAttachment(id="1")
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            }
            | payload,
            blocking=True,
            return_response=False,
        )

    mock_mastodon_client.status_post.assert_called_with(**kwargs)

    mock_mastodon_client.status_post.reset_mock()


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_STATUS: "test toot",
            },
            {"status": "test toot", "spoiler_text": None, "visibility": None},
        ),
        (
            {
                ATTR_STATUS: "test toot",
                ATTR_CONTENT_WARNING: "Spoiler",
                ATTR_MEDIA: "/image.jpg",
            },
            {
                "status": "test toot",
                "spoiler_text": "Spoiler",
                "visibility": None,
                "idempotency_key": None,
                "media_ids": "1",
                "media_description": None,
                "sensitive": None,
            },
        ),
    ],
)
async def test_post_service_failed(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, str],
    kwargs: dict[str, str | None],
) -> None:
    """Test the post service raising an error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_mastodon_client.media_post.return_value = MediaAttachment(id="1")

    mock_mastodon_client.status_post.side_effect = MastodonAPIError

    with pytest.raises(HomeAssistantError, match="Unable to send message"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=False,
        )


async def test_post_media_upload_failed(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the post service raising an error because media upload fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    payload = {"status": "test toot", "media": "/fail.jpg"}

    mock_mastodon_client.media_post.side_effect = MastodonAPIError

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError, match="Unable to upload image /fail.jpg"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=False,
        )


async def test_post_path_not_whitelisted(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the post service raising an error because the file path is not whitelisted."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    payload = {"status": "test toot", "media": "/fail.jpg"}

    with pytest.raises(
        HomeAssistantError, match="/fail.jpg is not a whitelisted directory"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=False,
        )


async def test_idempotency_key_too_short(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the post service raising an error because the idempotency key is too short."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    payload = {"status": "test toot", "idempotency_key": "abc"}

    with pytest.raises(
        ServiceValidationError,
        match="Idempotency key must be at least 4 characters long",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=False,
        )


async def test_service_entry_availability(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    payload = {"status": "test toot"}

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=False,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=False,
        )
    assert err.value.translation_key == "service_config_entry_not_found"
