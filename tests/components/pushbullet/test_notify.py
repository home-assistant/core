"""Test pushbullet notification platform."""
from http import HTTPStatus

from pushbullet import PushBullet
import pytest
from requests_mock import Mocker

from homeassistant.components.pushbullet.notify import PushBulletNotificationService


@pytest.fixture()
def mock_service(hass):
    """Return Mock PushBulletNotificationService."""
    yield PushBulletNotificationService(hass, PushBullet("MYAPIKEY"))


async def test_pushbullet_push_default(hass, requests_mock: Mocker, mock_service):
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    data = {"title": "Test Title", "message": "Test Message"}
    mock_service.send_message(**data)
    await hass.async_block_till_done()

    expected_body = {"body": "Test Message", "title": "Test Title", "type": "note"}
    assert requests_mock.last_request
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_device(hass, requests_mock, mock_service):
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP"],
    }
    mock_service.send_message(**data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "device_iden": "identity1",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_devices(hass, requests_mock, mock_service):
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP", "device/My iPhone"],
    }
    mock_service.send_message(**data)
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


async def test_pushbullet_push_email(hass, requests_mock, mock_service):
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["email/user@host.net"],
    }
    mock_service.send_message(**data)
    await hass.async_block_till_done()

    expected_body = {
        "body": "Test Message",
        "email": "user@host.net",
        "title": "Test Title",
        "type": "note",
    }
    assert requests_mock.last_request.json() == expected_body


async def test_pushbullet_push_mixed(hass, requests_mock, mock_service):
    """Test pushbullet push to default target."""
    requests_mock.register_uri(
        "POST",
        "https://api.pushbullet.com/v2/pushes",
        status_code=HTTPStatus.OK,
        json={"mock_response": "Ok"},
    )
    data = {
        "title": "Test Title",
        "message": "Test Message",
        "target": ["device/DESKTOP", "email/user@host.net"],
    }
    mock_service.send_message(**data)
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
