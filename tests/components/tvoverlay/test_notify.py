"""Test TvOverlay notify."""
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.tvoverlay.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    CONF_CONFIG_FLOW,
    SERICVE_NAME,
    mocked_send_notification,
    mocked_send_persistent_notification,
    mocked_tvoverlay_info,
)


@pytest.mark.parametrize(
    ("message", "title", "data", "expected_args", "expected_kwargs"),
    [
        ("message", "title", {}, "message", {"title": "title"}),
        (
            "message",
            "title",
            {"image": "http://example.com/image.png", "duration": 10},
            "message",
            {"title": "title", "image": "http://example.com/image.png"},
        ),
        (
            "message",
            "title",
            {"image": "http://example.com/image.png"},
            "message",
            {"title": "title", "image": None},
        ),
        (
            "message",
            "title",
            {"image": {"url": "example/image.png"}},
            "message",
            {"title": "title", "image": None},
        ),
        (
            "message",
            "title",
            {"app_icon": "/temp/image.png"},
            "message",
            {"title": "title", "appIcon": "/temp/image.png"},
        ),
        (
            "message",
            "title",
            {"app_icon": "/temp/image.png"},
            "message",
            {"title": "title", "appIcon": None},
        ),
        (
            "message",
            "title",
            {"app_icon": "/temp/image.png"},
            "message",
            {"title": "title", "appIcon": None},
        ),
        (
            "message",
            "title",
            {"app_icon": "mdi:bell", "duration": "3h4m5s"},
            "message",
            {"title": "title", "appIcon": "mdi:bell", "duration": "3h4m5s"},
        ),
        (
            "message",
            "title",
            {"image": {"path": "/temp/image.png"}},
            "message",
            {"title": "title", "image": None},
        ),
        (
            "message",
            "title",
            {"position": "top_middle"},
            "message",
            {"title": "title", "corner": "top_right"},
        ),
        (
            "message",
            "title",
            {"image": {"url": "http://example.com/image.png"}},
            "message",
            {"title": "title", "image": "http://example.com/image.png"},
        ),
        (
            "message",
            "title",
            {"image": {"path": "/temp/image.png"}},
            "message",
            {"title": "title", "image": "/temp/image.png"},
        ),
        (
            "message",
            "title",
            {"image": {"mdi_icon": "mdi:bell"}},
            "message",
            {"title": "title", "image": "mdi:bell"},
        ),
    ],
)
async def test_notify(
    hass: HomeAssistant,
    message: str,
    title: str,
    data: dict[str, Any] | None,
    expected_args: Any,
    expected_kwargs: Any,
) -> None:
    """Test TvOverlay notify."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_tvoverlay_info():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        await hass.async_block_till_done()

    with mocked_send_notification() as mock_notify:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": message,
                "title": title,
                "data": data,
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == expected_args
        assert mock_notify.mock_calls[0].kwargs["title"] == expected_kwargs["title"]


@pytest.mark.parametrize(
    (
        "message",
        "title",
        "data",
        "isfile",
        "is_allowed_path",
        "expected_message",
        "expected_title",
        "expected_image",
        "expected_app_icon",
    ),
    [
        (
            "Message",
            "Title",
            {"image": {"path": "/temp/image.png"}},
            True,
            True,
            "Message",
            "Title",
            "/temp/image.png",
            None,
        ),
        (
            "Message",
            "Title",
            {"app_icon": "/temp/image.png"},
            True,
            True,
            "Message",
            "Title",
            None,
            "/temp/image.png",
        ),
    ],
)
async def test_notify_local_path(
    hass: HomeAssistant,
    message: str,
    title: str,
    data: Any,
    isfile: bool,
    is_allowed_path: bool,
    expected_message: str,
    expected_title: str,
    expected_image: str,
    expected_app_icon: str,
) -> None:
    """Test service call notify image local path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_tvoverlay_info():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        await hass.async_block_till_done()

    with mocked_send_notification() as mock_notify, patch(
        "os.path.isfile", return_value=isfile
    ), patch.object(hass.config, "is_allowed_path", return_value=is_allowed_path):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {"message": message, "title": title, "data": data},
            blocking=True,
        )

        assert mock_notify.mock_calls[0].args[0] == expected_message
        assert mock_notify.mock_calls[0].kwargs["title"] == expected_title
        assert mock_notify.mock_calls[0].kwargs["image"] == expected_image
        assert mock_notify.mock_calls[0].kwargs["appIcon"] == expected_app_icon


async def test_notify_persistent(
    hass: HomeAssistant,
) -> None:
    """Test service call notify persistent."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_tvoverlay_info():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        await hass.async_block_till_done()

    with mocked_send_persistent_notification() as mock_notify, patch.object(
        hass.config, "is_allowed_external_url", return_value=True
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "is_persistent": "true",
                    "shape": "triangle",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["shape"] == "circle"


@pytest.mark.parametrize(
    (
        "message",
        "title",
        "data",
        "is_allowed_external_url",
        "expected_message",
        "expected_title",
        "expected_image",
        "expected_app_icon",
    ),
    [
        (
            "Message",
            "Title",
            {"image": {"url": "http://example.com/image.png"}},
            True,
            "Message",
            "Title",
            "http://example.com/image.png",
            None,
        ),
        (
            "Message",
            "Title",
            {
                "image": {"url": "http://example.com/image.png"},
                "app_icon": "http://example.com/image.png",
            },
            True,
            "Message",
            "Title",
            "http://example.com/image.png",
            "http://example.com/image.png",
        ),
    ],
)
async def test_notify_url(
    hass: HomeAssistant,
    message: str,
    title: str,
    data: Any,
    is_allowed_external_url: bool,
    expected_message: str,
    expected_title: str,
    expected_image: str,
    expected_app_icon: str,
) -> None:
    """Test service call notify image url."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_tvoverlay_info():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        await hass.async_block_till_done()

    with mocked_send_notification() as mock_notify, patch.object(
        hass.config, "is_allowed_external_url", return_value=is_allowed_external_url
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {"message": message, "title": title, "data": data},
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == expected_message
        assert mock_notify.mock_calls[0].kwargs["title"] == expected_title
        assert mock_notify.mock_calls[0].kwargs["image"].url == expected_image
        assert mock_notify.mock_calls[0].kwargs["appIcon"] == expected_app_icon
