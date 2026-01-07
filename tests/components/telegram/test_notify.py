"""The tests for the telegram.notify platform."""

from typing import Any
from unittest.mock import AsyncMock, call, patch

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TITLE
from homeassistant.components.telegram import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceRegistry
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_reload_notify(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Verify we can reload the notify service."""

    with patch("homeassistant.components.telegram_bot.async_setup", return_value=True):
        assert await async_setup_component(
            hass,
            notify.DOMAIN,
            {
                notify.DOMAIN: [
                    {
                        "name": DOMAIN,
                        "platform": DOMAIN,
                        "chat_id": 1,
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = get_fixture_path("configuration.yaml", "telegram")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert hass.services.has_service(notify.DOMAIN, "telegram_reloaded")

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="migrate_notify",
    )
    assert len(issue_registry.issues) == 1


async def test_notify(hass: HomeAssistant) -> None:
    """Test notify."""

    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "chat_id": 1,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    original_call = ServiceRegistry.async_call
    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_service_call:
        # setup mock

        async def call_service(*args, **kwargs) -> Any:
            if args[0] == notify.DOMAIN:
                return await original_call(
                    hass.services, args[0], args[1], args[2], kwargs["blocking"]
                )
            return AsyncMock()

        mock_service_call.side_effect = call_service

        # test send message

        data: dict[str, Any] = {"title": "mock title", "message": "mock message"}
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            {ATTR_TITLE: "mock title", ATTR_MESSAGE: "mock message"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert mock_service_call.mock_calls == [
            call(
                "notify",
                "telegram",
                data,
                blocking=True,
            ),
            call(
                "telegram_bot",
                "send_message",
                {"target": 1, "title": "mock title", "message": "mock message"},
                False,
                None,
                None,
                False,
            ),
        ]

        mock_service_call.reset_mock()

        # test send file

        data = {
            ATTR_TITLE: "mock title",
            ATTR_MESSAGE: "mock message",
            ATTR_DATA: {
                "photo": {"url": "https://mock/photo.jpg", "caption": "mock caption"}
            },
        }

        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            data,
            blocking=True,
        )
        await hass.async_block_till_done()

        assert mock_service_call.mock_calls == [
            call(
                "notify",
                "telegram",
                data,
                blocking=True,
            ),
            call(
                "telegram_bot",
                "send_photo",
                {
                    "target": 1,
                    "url": "https://mock/photo.jpg",
                    "caption": "mock caption",
                },
                False,
                None,
                None,
                False,
            ),
        ]
