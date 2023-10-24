"""Test TvOverlay notify."""

from unittest.mock import patch

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


async def test_notify_1(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with message and title."""
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
                "message": "Message",
                "title": "Title",
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"


async def test_notify_2(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data image url."""
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
        hass.config, "is_allowed_external_url", return_value=True
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "image": "http://example.com/image.png",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert (
            mock_notify.mock_calls[0].kwargs["image"] == "http://example.com/image.png"
        )


async def test_notify_3(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data image url not allowed."""
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
        hass.config, "is_allowed_external_url", return_value=False
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "image": "http://example.com/image.png",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["image"] is None


async def test_notify_4(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data image invalid url."""
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
        hass.config, "is_allowed_external_url", return_value=True
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {"image": {"url": "example/image.png"}},
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["image"] is None


async def test_notify_5(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data app_icon path."""
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
        "os.path.isfile", return_value=True
    ), patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "app_icon": "/temp/image.png",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["appIcon"] == "/temp/image.png"


async def test_notify_6(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data app_icon invalid path."""
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
        "os.path.isfile", return_value=False
    ), patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "app_icon": "/temp/image.png",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["appIcon"] is None


async def test_notify_7(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data app_icon path not allowed."""
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
        "os.path.isfile", return_value=True
    ), patch.object(hass.config, "is_allowed_path", return_value=False):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "app_icon": "/temp/image.png",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["appIcon"] is None


async def test_notify_8(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data app_icon as mdi icon."""
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
                "message": "Message",
                "title": "Title",
                "data": {
                    "app_icon": "mdi:bell",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["appIcon"] == "mdi:bell"


async def test_notify_9(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data image not allowed path."""
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
        hass.config, "is_allowed_path", return_value=False
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {"image": {"path": "/temp/image.png"}},
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["image"] is None


async def test_notify_10(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data invalid position."""
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
        hass.config, "is_allowed_external_url", return_value=True
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {
                    "position": "top_middle",
                },
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["corner"] == "top_right"


async def test_notify_11(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data invalid shape."""
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


async def test_notify_12(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data ImageUrlSource url."""
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
        hass.config, "is_allowed_external_url", return_value=True
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {"image": {"url": "http://example.com/image.png"}},
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert (
            mock_notify.mock_calls[0].kwargs["image"].url
            == "http://example.com/image.png"
        )


async def test_notify_13(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data valid path."""
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
        "os.path.isfile", return_value=True
    ), patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERICVE_NAME,
            {
                "message": "Message",
                "title": "Title",
                "data": {"image": {"path": "/temp/image.png"}},
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["image"] == "/temp/image.png"


async def test_notify_14(
    hass: HomeAssistant,
) -> None:
    """Test service call notify with data mdi icon."""
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
                "message": "Message",
                "title": "Title",
                "data": {"image": {"mdi_icon": "mdi:bell"}},
            },
            blocking=True,
        )
        assert mock_notify.mock_calls[0].args[0] == "Message"
        assert mock_notify.mock_calls[0].kwargs["title"] == "Title"
        assert mock_notify.mock_calls[0].kwargs["image"] == "mdi:bell"
