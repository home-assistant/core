"""Test add-on panel."""

from http import HTTPStatus
import os
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models import IngressPanel
import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.typing import ClientSessionGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(all_setup_requests: None) -> None:
    """Mock all setup requests."""


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_startup(
    hass: HomeAssistant, ingress_panels: AsyncMock
) -> None:
    """Test startup and panel setup after event."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        "test2": IngressPanel(
            enable=False, title="Test 2", icon="mdi:test2", admin=True
        ),
    }

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        with patch.dict(os.environ, MOCK_ENVIRON):
            await async_setup_component(hass, "hassio", {})
            await hass.async_block_till_done()

        ingress_panels.assert_not_called()
        mock_panel.assert_not_called()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        ingress_panels.assert_called_once()
        assert mock_panel.called
        mock_panel.assert_called_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ingress_panels: AsyncMock
) -> None:
    """Test panel api after event."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        "test2": IngressPanel(
            enable=False, title="Test 2", icon="mdi:test2", admin=True
        ),
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        ingress_panels.assert_called_once()
        assert mock_panel.called
        mock_panel.assert_called_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )

        hass_client = await hass_client()

        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == HTTPStatus.BAD_REQUEST

        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        assert mock_panel.call_count == 2

        mock_panel.assert_called_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_non_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ingress_panels: AsyncMock,
    hass_admin_user: MockUser,
) -> None:
    """Test register panel api fails with non admin user."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        ingress_panels.assert_called_once()
        mock_panel.assert_called_once()

        mock_panel.reset_mock()
        hass_admin_user.groups = []
        hass_client = await hass_client()

        # Both should return unauthorized regardless of enabled as the endpoint requires
        # admin and the user is not admin
        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == HTTPStatus.UNAUTHORIZED

        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.UNAUTHORIZED

        mock_panel.assert_not_called()


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_registration(
    hass: HomeAssistant, ingress_panels: AsyncMock
) -> None:
    """Test panel registration calls frontend.async_register_built_in_panel."""
    ingress_panels.return_value = {
        "test_addon": IngressPanel(
            enable=True, title="Test Addon", icon="mdi:test-tube", admin=True
        ),
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_register_built_in_panel"
    ) as mock_register:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Verify that async_register_built_in_panel was called with correct arguments
        # for our test addon
        mock_register.assert_any_call(
            hass,
            "app",
            frontend_url_path="test_addon",
            sidebar_title="Test Addon",
            sidebar_icon="mdi:test-tube",
            require_admin=True,
            config={"addon": "test_addon"},
        )


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_delete(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ingress_panels: AsyncMock
) -> None:
    """Test panel api delete."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }
    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_remove_panel"
    ) as mock_remove:
        resp = await hass_client.delete("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        mock_remove.assert_called_once_with(hass, "test1")


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_delete_non_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ingress_panels: AsyncMock,
    hass_admin_user: MockUser,
) -> None:
    """Test panel api delete fails with non admin user."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }
    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

    hass_admin_user.groups = []
    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_remove_panel"
    ) as mock_remove:
        resp = await hass_client.delete("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        mock_remove.assert_not_called()
