"""Tests for the ONVIF event webhook."""

import asyncio
from collections.abc import Generator
from http import HTTPStatus
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL
from zeep.exceptions import Fault, TransportError

from homeassistant.components.onvif.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from . import HOST, MAC, NAME, PASSWORD, PORT, USERNAME, setup_mock_onvif_camera

INTERNAL_URL = "http://192.168.1.2:8123"
MAC_WEBHOOK_PATH = "/api/webhook/onvifaabbccddeeff"
NOTIFICATION = b"<notification/>"


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return an ONVIF config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        unique_id=MAC,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def notification_manager() -> MagicMock:
    """Return a mock ONVIF notification manager."""
    manager = MagicMock(closed=False)
    manager.set_synchronization_point = AsyncMock()
    manager.shutdown = AsyncMock()
    manager.process.return_value = MagicMock(NotificationMessage=[])
    return manager


@pytest.fixture
def mock_onvif_camera(notification_manager: MagicMock) -> Generator[MagicMock]:
    """Patch the ONVIF camera with a camera that only supports webhooks."""
    with patch(
        "homeassistant.components.onvif.device.ONVIFCamera"
    ) as mock_onvif_camera:
        setup_mock_onvif_camera(mock_onvif_camera, with_full_setup=True)
        mock_onvif_camera.create_notification_manager = AsyncMock(
            return_value=notification_manager
        )
        yield mock_onvif_camera


async def _async_setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the webhook component and the ONVIF config entry."""
    assert await async_setup_component(hass, "webhook", {})
    await async_process_ha_core_config(hass, {"internal_url": INTERNAL_URL})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def _subscribed_url(mock_onvif_camera: MagicMock) -> URL:
    """Return the webhook URL the camera was last subscribed with."""
    return URL(
        mock_onvif_camera.create_notification_manager.call_args.kwargs["address"]
    )


@pytest.mark.parametrize(
    "remote",
    [
        pytest.param("192.168.1.10", id="local"),
        pytest.param("123.123.123.123", id="remote"),
    ],
)
async def test_webhook_notification(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
    notification_manager: MagicMock,
    remote: str,
) -> None:
    """Test notifications sent to the subscribed webhook URL are processed."""
    await _async_setup(hass, config_entry)

    url = _subscribed_url(mock_onvif_camera)
    assert str(url.origin()) == INTERNAL_URL
    assert url.path != MAC_WEBHOOK_PATH
    assert url.path.startswith("/api/webhook/onvif")
    assert len(url.name) == len("onvif") + 12

    client = await hass_client_no_auth()
    with patch(
        "homeassistant.components.webhook.ip_address",
        return_value=ip_address(remote),
    ):
        resp = await client.post(url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    notification_manager.process.assert_called_once_with(NOTIFICATION)


@pytest.mark.usefixtures("mock_onvif_camera")
async def test_mac_based_webhook_not_registered(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    notification_manager: MagicMock,
) -> None:
    """Test the webhook can't be reached with an id derived from the MAC."""
    await _async_setup(hass, config_entry)

    client = await hass_client_no_auth()
    resp = await client.post(MAC_WEBHOOK_PATH, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    notification_manager.process.assert_not_called()


async def test_webhook_id_changes_on_reload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
    notification_manager: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a new webhook id is used each time the config entry is set up."""
    await _async_setup(hass, config_entry)
    first_url = _subscribed_url(mock_onvif_camera)

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_onvif_camera.create_notification_manager.call_count == 2
    second_url = _subscribed_url(mock_onvif_camera)
    assert second_url != first_url

    client = await hass_client_no_auth()
    resp = await client.post(first_url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    # The old manager drops notifications after unloading, so check the log
    # to verify the old webhook is unregistered.
    assert f"Received message for unregistered webhook {first_url.name}" in caplog.text
    notification_manager.process.assert_not_called()

    resp = await client.post(second_url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    notification_manager.process.assert_called_once_with(NOTIFICATION)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Fault("no notification support"), id="fault"),
        pytest.param(TransportError("error", 500), id="transport_error"),
    ],
)
async def test_webhook_unregistered_when_subscription_fails(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test the webhook is unregistered when the subscription can't be created."""
    mock_onvif_camera.create_notification_manager.side_effect = error
    await _async_setup(hass, config_entry)
    url = _subscribed_url(mock_onvif_camera)

    client = await hass_client_no_auth()
    resp = await client.post(url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    assert f"Received message for unregistered webhook {url.name}" in caplog.text


async def test_webhook_unregistered_when_subscription_cancelled(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the webhook is unregistered when creating the subscription is cancelled."""
    mock_onvif_camera.create_notification_manager.side_effect = asyncio.CancelledError
    assert await async_setup_component(hass, "webhook", {})
    await async_process_ha_core_config(hass, {"internal_url": INTERNAL_URL})
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    url = _subscribed_url(mock_onvif_camera)

    client = await hass_client_no_auth()
    resp = await client.post(url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    assert f"Received message for unregistered webhook {url.name}" in caplog.text


async def test_webhook_used_when_pullpoint_transport_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
    notification_manager: MagicMock,
) -> None:
    """Test the webhook is still used when PullPoint fails with a transport error."""
    mock_onvif_camera.create_pullpoint_manager.side_effect = TransportError(
        "error", 500
    )
    await _async_setup(hass, config_entry)
    url = _subscribed_url(mock_onvif_camera)

    client = await hass_client_no_auth()
    resp = await client.post(url.path, data=NOTIFICATION)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    notification_manager.process.assert_called_once_with(NOTIFICATION)


async def test_webhook_external_url_fallback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onvif_camera: MagicMock,
) -> None:
    """Test the external URL is used when no internal URL is available."""
    assert await async_setup_component(hass, "webhook", {})
    # Home Assistant serving TLS itself disables the local IP fallback URL.
    hass.config.api.use_ssl = True
    await async_process_ha_core_config(hass, {"external_url": "https://example.com"})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    url = _subscribed_url(mock_onvif_camera)
    assert str(url.origin()) == "https://example.com"
    assert url.path.startswith("/api/webhook/onvif")
