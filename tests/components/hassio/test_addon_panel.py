"""Test add-on panel."""

from datetime import timedelta
from http import HTTPStatus
import os
from unittest.mock import AsyncMock, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import IngressPanel
import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.const import (
    MAIN_COORDINATOR,
    REQUEST_REFRESH_DELAY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser, async_fire_time_changed
from tests.typing import ClientSessionGenerator, WebSocketGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(all_setup_requests: None) -> None:
    """Mock all setup requests."""


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_registered_on_setup(
    hass: HomeAssistant, ingress_panels: AsyncMock
) -> None:
    """Test enabled panels are registered as part of config entry setup.

    Regression test for https://github.com/home-assistant/supervisor/issues/7015:
    registration must not depend on the one-shot EVENT_HOMEASSISTANT_START handler
    that used to swallow Supervisor timeouts and never retry.
    """
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        "test2": IngressPanel(
            enable=False, title="Test 2", icon="mdi:test2", admin=True
        ),
    }

    with (
        patch(
            "homeassistant.components.hassio.addon_panel._register_panel"
        ) as mock_panel,
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_panel.assert_called_once_with(
        hass,
        "test1",
        IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    )


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

    with (
        patch(
            "homeassistant.components.hassio.addon_panel.frontend.async_register_built_in_panel"
        ) as mock_register,
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_register.assert_any_call(
        hass,
        "app",
        frontend_url_path="test_addon",
        sidebar_title="Test Addon",
        sidebar_icon="mdi:test-tube",
        require_admin=True,
        config={"addon": "test_addon"},
        update=True,
    )


async def test_hassio_addon_panel_setup_retries_after_transient_error(
    hass: HomeAssistant, ingress_panels: AsyncMock
) -> None:
    """Test a transient Supervisor error fetching panels causes setup to retry.

    Regression test for https://github.com/home-assistant/supervisor/issues/7015:
    previously a timeout fetching panels at startup was logged and swallowed,
    leaving panels missing forever with no retry. Panel data is now fetched as
    part of the main coordinator's first refresh, so a transient failure causes
    the whole config entry setup to retry until Supervisor is reachable again.
    """
    ingress_panels.side_effect = SupervisorError("Timeout connecting to Supervisor")

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert result
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY

    ingress_panels.side_effect = None
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel"
    ) as mock_panel:
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_panel.assert_called_once_with(
        hass,
        "test1",
        IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    )


async def test_hassio_addon_panel_recovers_after_supervisor_restart(
    hass: HomeAssistant,
    hass_supervisor_ws_client: WebSocketGenerator,
    ingress_panels: AsyncMock,
) -> None:
    """Test panels are refreshed when Supervisor reports it has restarted.

    Regression test for the "Supervisor restarts while Core keeps running"
    scenario: Supervisor fires a supervisor_update/startup:complete event on
    every one of its own (re)starts, which the main coordinator already listens
    for and uses to trigger a refresh.
    """
    ingress_panels.return_value = {}

    with (
        patch(
            "homeassistant.components.hassio.addon_panel._register_panel"
        ) as mock_panel,
        patch.dict(os.environ, MOCK_ENVIRON),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        mock_panel.assert_not_called()

        ingress_panels.return_value = {
            "test1": IngressPanel(
                enable=True, title="Test", icon="mdi:test", admin=False
            ),
        }

        client = await hass_supervisor_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "supervisor/event",
                "data": {
                    "event": "supervisor_update",
                    "update_key": "supervisor",
                    "data": {"startup": "complete"},
                },
            }
        )
        await client.receive_json()

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=REQUEST_REFRESH_DELAY + 1)
        )
        await hass.async_block_till_done()

        mock_panel.assert_called_once_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_post(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ingress_panels: AsyncMock
) -> None:
    """Test posting a panel push registers it via the coordinator cache."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        "test2": IngressPanel(
            enable=False, title="Test 2", icon="mdi:test2", admin=True
        ),
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel"
    ) as mock_panel:
        # Panel is not enabled yet according to Supervisor
        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == HTTPStatus.BAD_REQUEST
        mock_panel.assert_not_called()

        # Supervisor enables the panel and pushes the change
        ingress_panels.return_value["test2"] = IngressPanel(
            enable=True, title="Test 2", icon="mdi:test2", admin=True
        )
        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == HTTPStatus.OK
        mock_panel.assert_called_once_with(
            hass,
            "test2",
            IngressPanel(enable=True, title="Test 2", icon="mdi:test2", admin=True),
        )

        # Posting again for an already-registered, unchanged panel is a no-op
        mock_panel.reset_mock()
        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        mock_panel.assert_not_called()


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_before_coordinator_ready(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ingress_panels: AsyncMock
) -> None:
    """Test panel push api falls back to a fresh Supervisor call before setup completes.

    Other callers besides Supervisor may rely on this API before the config
    entry (and its main coordinator) finishes setting up, so it must keep
    working via a direct Supervisor call and frontend registration instead of
    failing with a 503.
    """
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    hass_client = await hass_client()

    # Simulate the main coordinator not being ready yet
    del hass.data[MAIN_COORDINATOR]

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel"
    ) as mock_panel:
        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        mock_panel.assert_called_once_with(
            hass,
            "test1",
            IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
        )

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_remove_panel"
    ) as mock_remove:
        resp = await hass_client.delete("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        mock_remove.assert_called_once_with(hass, "test1", warn_if_unknown=False)


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
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    hass_admin_user.groups = []
    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel"
    ) as mock_panel:
        # Both should return unauthorized regardless of enabled as the endpoint requires
        # admin and the user is not admin
        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == HTTPStatus.UNAUTHORIZED

        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.UNAUTHORIZED

        mock_panel.assert_not_called()


@pytest.mark.usefixtures("supervisor_client")
async def test_hassio_addon_panel_api_delete(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ingress_panels: AsyncMock
) -> None:
    """Test panel api delete removes it via the coordinator cache."""
    ingress_panels.return_value = {
        "test1": IngressPanel(enable=True, title="Test", icon="mdi:test", admin=False),
    }
    with patch.dict(os.environ, MOCK_ENVIRON):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_remove_panel"
    ) as mock_remove:
        resp = await hass_client.delete("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        mock_remove.assert_called_once_with(hass, "test1", warn_if_unknown=False)


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
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    hass_admin_user.groups = []
    hass_client = await hass_client()

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_remove_panel"
    ) as mock_remove:
        resp = await hass_client.delete("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.UNAUTHORIZED
        mock_remove.assert_not_called()
