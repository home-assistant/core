import time
from unittest.mock import patch, create_autospec

from mastodon import Mastodon

import homeassistant.components.notify as notify
from homeassistant.setup import async_setup_component


async def test_load_notify(hass, notify_mastodon):
    """Verify we can load the mastodon notify service."""

    assert hass.services.has_service(notify.DOMAIN, notify_mastodon)


async def test_send_message(hass, mastodon_config):
    """Verify we can send a message without any additional params."""

    with patch.object(Mastodon, "status_post", return_value=None) as mock_post:
        with patch.object(Mastodon, "account_verify_credentials", return_value=True):
            await async_setup_component(
                hass,
                notify.DOMAIN,
                {
                    notify.DOMAIN: [mastodon_config],
                },
            )
            await hass.async_block_till_done()

        await hass.services.async_call(
            notify.DOMAIN,
            mastodon_config["name"],
            {
                "message": "this is a test message",
            },
        )

    mock_post.assert_called_once_with("this is a test message")


async def test_send_message_with_params(hass, mastodon_config):
    """Verify we can send a message with additional params."""

    with patch.object(Mastodon, "status_post", return_value=None) as mock_post:
        with patch.object(Mastodon, "account_verify_credentials", return_value=True):
            await async_setup_component(
                hass,
                notify.DOMAIN,
                {
                    notify.DOMAIN: [mastodon_config],
                },
            )
            await hass.async_block_till_done()

        await hass.services.async_call(
            notify.DOMAIN,
            mastodon_config["name"],
            {
                "message": "this is a direct test message",
                "data": {
                    "visibility": "direct",
                },
            },
        )
        await hass.async_block_till_done()

    mock_post.assert_called_once_with(
        "this is a direct test message", visibility="direct"
    )


async def test_send_message_with_ignored_params(hass, mastodon_config):
    """Verify we can send a message with additional params."""

    with patch.object(Mastodon, "status_post", return_value=None) as mock_post:
        with patch.object(Mastodon, "account_verify_credentials", return_value=True):
            await async_setup_component(
                hass,
                notify.DOMAIN,
                {
                    notify.DOMAIN: [mastodon_config],
                },
            )
            await hass.async_block_till_done()

        await hass.services.async_call(
            notify.DOMAIN,
            mastodon_config["name"],
            {
                "message": "this is a direct test message",
                "data": {
                    "visibility": "direct",
                    "should_be_ignored": 1,
                },
            },
        )
        await hass.async_block_till_done()

    mock_post.assert_called_once_with(
        "this is a direct test message", visibility="direct"
    )
