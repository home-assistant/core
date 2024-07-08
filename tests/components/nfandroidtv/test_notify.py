"""Test nfandroidtv notify service."""

from typing import Any

import httpx
import pytest
import respx

from homeassistant.bootstrap import HomeAssistantError
from homeassistant.components.nfandroidtv.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import CONF_DATA

from tests.common import MockConfigEntry, load_json_value_fixture


@respx.mock
async def test_sending_notification(hass: HomeAssistant) -> None:
    """Test sending notification with message and title and data."""
    respx.get("http://1.2.3.4:7676/") % 200
    respx.post("http://1.2.3.4:7676/") % 200
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = load_json_value_fixture("data.json", "nfandroidtv")
    await hass.services.async_call(
        NOTIFY_DOMAIN, "android_tv_fire_tv", data, blocking=True
    )

    assert respx.calls.call_count == 2


@respx.mock
async def test_sending_notification_conn_error(hass: HomeAssistant) -> None:
    """Test having a connection error when sending."""
    respx.get("http://1.2.3.4:7676/") % 200
    respx.post("http://1.2.3.4:7676/").side_effect = httpx.ConnectError(
        "Host not found"
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = load_json_value_fixture("data.json", "nfandroidtv")
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "android_tv_fire_tv", data, blocking=True
        )
    assert (
        str(exc.value) == "Error communicating with http://1.2.3.4:7676: Host not found"
    )

    assert respx.calls.call_count == 2


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (
            {
                "title": "Test Title",
                "message": "Test Message",
                "data": {"icon": {"uri": "http://example.com"}},
            },
            "Invalid 'icon' data",
        ),
        (
            {
                "title": "Test Title",
                "message": "Test Message",
                "data": {"image": {"uri": "http://example.com"}},
            },
            "Invalid 'image' data",
        ),
        (
            {
                "title": "Test Title",
                "message": "Test Message",
                "data": {"icon": {"url": "http://example.com", "auth": "bla"}},
            },
            "Invalid 'icon' data: Invalid auth 'bla', must be 'basic' or 'digest'",
        ),
    ],
    ids=["invalid_icon_data", "invalid_image_data", "invalid_auth"],
)
@respx.mock
async def test_invalid_image_data(
    hass: HomeAssistant, data: dict[str, Any], message: str
) -> None:
    """Test sending notification with invalid image data."""
    respx.get("http://1.2.3.4:7676/") % 200
    respx.post("http://1.2.3.4:7676/") % 200
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "android_tv_fire_tv", data, blocking=True
        )
    assert f"{exc.value!r}" == "ServiceValidationError('Invalid image data provided')"
    assert str(exc.value.translation_placeholders["message"]) == message


@pytest.mark.parametrize(
    ("data", "key", "path"),
    [
        (
            {
                "title": "Test Title",
                "message": "Test Message",
                "data": {"icon": "mock_file.jpg"},
            },
            "icon",
            "mock_file.jpg",
        ),
        (
            {
                "title": "Test Title",
                "message": "Test Message",
                "data": {"image": {"path": "mock_file.jpg"}},
            },
            "image",
            "mock_file.jpg",
        ),
    ],
    ids=["insecure_icon_file", "insecure_image_file"],
)
@respx.mock
async def test_insecure_local_file(
    hass: HomeAssistant, data: dict[str, Any], key: str, path: str
) -> None:
    """Test sending notification with insecure local file."""
    respx.get("http://1.2.3.4:7676/") % 200
    respx.post("http://1.2.3.4:7676/") % 200
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "android_tv_fire_tv", data, blocking=True
        )
    assert f"{exc.value!r}" == "ServiceValidationError('File path is not secure')"
    assert str(exc.value.translation_placeholders["key"]) == key
    assert str(exc.value.translation_placeholders["path"]) == path
