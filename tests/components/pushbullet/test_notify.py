"""Test pushbullet notification platform."""
from http import HTTPStatus

from requests_mock import Mocker

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushbullet.const import DOMAIN

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_pushbullet_push_default(hass, requests_mock: Mocker):
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


async def test_pushbullet_push_device(hass, requests_mock):
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


async def test_pushbullet_push_devices(hass, requests_mock):
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


async def test_pushbullet_push_email(hass, requests_mock):
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


async def test_pushbullet_push_mixed(hass, requests_mock):
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
