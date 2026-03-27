"""Test add-on panel."""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models import IngressPanel
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_all(
    supervisor_is_connected: AsyncMock,
    homeassistant_info: AsyncMock,
    ingress_panels: AsyncMock,
) -> None:
    """Mock all setup requests."""


@pytest.mark.usefixtures("hassio_env")
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
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        ingress_panels.assert_called_once()
        assert mock_panel.called
        mock_panel.assert_called_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )


@pytest.mark.usefixtures("hassio_env")
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

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        await async_setup_component(hass, "hassio", {})
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


@pytest.mark.usefixtures("hassio_env")
async def test_hassio_addon_panel_registration(
    hass: HomeAssistant, ingress_panels: AsyncMock
) -> None:
    """Test panel registration calls frontend.async_register_built_in_panel."""
    ingress_panels.return_value = {
        "test_addon": IngressPanel(
            enable=True, title="Test Addon", icon="mdi:test-tube", admin=True
        ),
    }

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_register_built_in_panel"
    ) as mock_register:
        await async_setup_component(hass, "hassio", {})
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
