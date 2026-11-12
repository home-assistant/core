"""Test pushbullet notification platform."""

import errno
from http import HTTPStatus
import os
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests_mock

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushbullet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_CONFIG


async def test_pushbullet_push_default(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = {"title": "Test Title", "message": "Test Message"}
    await hass.services.async_call(NOTIFY_DOMAIN, "pushbullet", data)
    await hass.async_block_till_done()

    expected_body = {"body": "Test Message", "title": "Test Title", "type": "note"}
    assert requests_mock.last_request
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_device(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP"],
    }
    await hass.services.async_call(NOTIFY_DOMAIN, "pushbullet", data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "device_iden": "identity1",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_devices(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP", "device/My iPhone"],
    }
    await hass.services.async_call(NOTIFY_DOMAIN, "pushbullet", data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "device_iden": "identity1",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.request_history[-2].json() == expected_body
    expected_body = {
        "body": "Test Message",
        "device_iden": "identity2",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.request_history[-1].json() == expected_body


async def test_pushbullet_push_email(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["email/user@host.net"],
    }
    await hass.services.async_call(NOTIFY_DOMAIN, "pushbullet", data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "email": "user@host.net",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_mixed(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP", "email/user@host.net"],
    }

    await hass.services.async_call(NOTIFY_DOMAIN, "pushbullet", data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "device_iden": "identity1",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.request_history[-2].json() == expected_body
    expected_body = {
        "body": "Test Message",
        "email": "user@host.net",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.request_history[-1].json() == expected_body


@pytest.mark.parametrize(
    ("error_no", "translation_key"),
    [
        pytest.param(errno.ENOENT, "os_read_not_found", id="not_found"),
        pytest.param(errno.EACCES, "os_read_permission_denied", id="permission"),
        pytest.param(errno.EISDIR, "os_read_is_directory", id="is_directory"),
        pytest.param(errno.EIO, "os_read_error", id="fallback"),
    ],
)
@pytest.mark.usefixtures("requests_mock")
async def test_pushbullet_push_file_read_error(
    hass: HomeAssistant, error_no: int, translation_key: str
) -> None:
    """Test that a file read error raises a translated error."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch(
            "homeassistant.components.pushbullet.notify.open",
            side_effect=OSError(error_no, os.strerror(error_no)),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "pushbullet",
            {"message": "Test", "data": {"file": "/some/file.jpg"}},
            blocking=True,
        )

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"path": "/some/file.jpg"}
