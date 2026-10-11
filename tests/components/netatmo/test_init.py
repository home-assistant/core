"""The tests for Netatmo component."""

from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from datetime import timedelta
from functools import partial
from itertools import pairwise
import logging
from time import time
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pyatmo
from pyatmo.const import ALL_SCOPES
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import cloud, webhook
from homeassistant.components.netatmo import DOMAIN, coordinator
from homeassistant.components.netatmo.coordinator import ACCOUNT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_WEBHOOK_ID,
    EVENT_STATE_CHANGED,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    HOME_ID,
    fake_post_request,
    selected_platforms,
    simulate_webhook,
)

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed
from tests.components.cloud import mock_cloud
from tests.typing import WebSocketGenerator

# Fake webhook thermostat mode change to "Max"
FAKE_WEBHOOK = {
    "room_id": "2746182631",
    "home": {
        "id": HOME_ID,
        "name": "MYHOME",
        "country": "DE",
        "rooms": [
            {
                "id": "2746182631",
                "name": "Livingroom",
                "type": "livingroom",
                "therm_setpoint_mode": "max",
                "therm_setpoint_end_time": 1612749189,
            }
        ],
        "modules": [
            {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
        ],
    },
    "mode": "max",
    "event_type": "set_point",
    "push_type": "display_change",
}

SWITCH_ENTITY_ID = "switch.prise"
# The switch's home is polled every 150s with the cloud credentials the test
# config entry uses
HOME_POLL_INTERVAL = 150
# Scheduled updates to drive, enough for the longest failure script to run
# through the escalating retry backoff
SCHEDULED_UPDATES = 80


async def test_setup_component(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup and teardown of the netatmo component."""
    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    mock_auth.assert_called_once()
    mock_impl.assert_called_once()
    mock_webhook.assert_called_once()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_entries(DOMAIN)
    assert len(hass.states.async_all()) > 0

    for entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(entry.entry_id)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_component_with_config(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup of the netatmo component with dev account."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_webhook,
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
        ) as mock_auth,
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", ["sensor"]),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await async_setup_component(
            hass, DOMAIN, {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

        await hass.async_block_till_done()

        assert fake_post_hits >= 8
        mock_impl.assert_called_once()
        mock_webhook.assert_called_once()

    assert hass.config_entries.async_entries(DOMAIN)
    assert len(hass.states.async_all()) > 0


async def test_setup_component_with_webhook(
    hass: HomeAssistant, config_entry, netatmo_auth
) -> None:
    """Test setup and teardown of the netatmo component with webhook registration."""
    with selected_platforms(
        [Platform.CAMERA, Platform.CLIMATE, Platform.LIGHT, Platform.SENSOR]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)

    assert len(hass.states.async_all()) > 0

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)

    # Assert webhook is established successfully
    climate_entity_livingroom = "climate.livingroom_livingroom"
    assert hass.states.get(climate_entity_livingroom).state == "auto"
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK)
    assert hass.states.get(climate_entity_livingroom).state == "heat"

    for entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(entry.entry_id)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_no_deprecation_issue_on_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the automatic webhook lifecycle does not raise the deprecation issue."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_service_register_webhook"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_service_unregister_webhook"
    )


@pytest.mark.parametrize(
    ("service", "expected_registered"),
    [
        pytest.param("register_webhook", True, id="register"),
        pytest.param("unregister_webhook", False, id="unregister"),
    ],
)
async def test_deprecated_webhook_service(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    issue_registry: ir.IssueRegistry,
    service: str,
    expected_registered: bool,
) -> None:
    """Test the deprecated webhook actions still work and raise a repair issue."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        webhook_id = config_entry.data[CONF_WEBHOOK_ID]
        assert webhook_id in hass.data[webhook.DOMAIN]

        # register_webhook re-registers the already-active webhook without
        # raising; unregister_webhook tears it down.
        await hass.services.async_call(DOMAIN, service, blocking=True)

        assert (webhook_id in hass.data[webhook.DOMAIN]) is expected_registered

    assert issue_registry.async_get_issue(DOMAIN, f"deprecated_service_{service}")


@pytest.mark.parametrize("service", ["register_webhook", "unregister_webhook"])
async def test_deprecated_webhook_service_not_loaded(
    hass: HomeAssistant,
    service: str,
) -> None:
    """Test calling a webhook action without a loaded entry raises."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, service, blocking=True)


async def test_setup_without_https(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if set up with cloud link and without https."""
    hass.config.components.add("cloud")
    with (
        patch(
            "homeassistant.helpers.network.get_url",
            return_value="http://example.nabu.casa",
        ),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_async_generate_url,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        mock_async_generate_url.return_value = "http://example.com"
        assert await async_setup_component(
            hass, DOMAIN, {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

        await hass.async_block_till_done()
        mock_auth.assert_called_once()
        mock_async_generate_url.assert_called_once()

    assert "https and port 443 is required to register the webhook" in caplog.text


async def test_setup_with_cloud(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if set up with active cloud subscription."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as fake_delete_cloudhook,
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", []),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url",
        ),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        assert await async_setup_component(
            hass, DOMAIN, {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )
        assert cloud.async_active_subscription(hass) is True
        assert cloud.async_is_connected(hass) is True
        fake_create_cloudhook.assert_called_once()

        assert (
            hass.config_entries.async_entries("netatmo")[0].data["cloudhook_url"]
            == "https://hooks.nabu.casa/ABCD"
        )

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)

        for entry in hass.config_entries.async_entries("netatmo"):
            await hass.config_entries.async_remove(entry.entry_id)
            fake_delete_cloudhook.assert_called_once()

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_with_cloudhook(hass: HomeAssistant) -> None:
    """Test if set up with active cloud subscription and cloud hook."""
    config_entry = MockConfigEntry(
        domain="netatmo",
        data={
            "auth_implementation": "cloud",
            "cloudhook_url": "https://hooks.nabu.casa/ABCD",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 1000,
                "scope": ALL_SCOPES,
            },
        },
    )
    config_entry.add_to_hass(hass)

    await mock_cloud(hass)
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as fake_delete_cloudhook,
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", []),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url",
        ),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await async_setup_component(hass, DOMAIN, {})
        assert cloud.async_active_subscription(hass) is True

        assert (
            hass.config_entries.async_entries("netatmo")[0].data["cloudhook_url"]
            == "https://hooks.nabu.casa/ABCD"
        )

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)
        fake_create_cloudhook.assert_not_called()

        for config_entry in hass.config_entries.async_entries("netatmo"):
            await hass.config_entries.async_remove(config_entry.entry_id)
            fake_delete_cloudhook.assert_called_once()

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_component_with_delay(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup of the netatmo component with delayed startup."""
    hass.set_state(CoreState.not_running)

    with (
        patch(
            "pyatmo.AbstractAsyncAuth.async_addwebhook", side_effect=AsyncMock()
        ) as mock_addwebhook,
        patch(
            "pyatmo.AbstractAsyncAuth.async_dropwebhook", side_effect=AsyncMock()
        ) as mock_dropwebhook,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_webhook,
        patch(
            "pyatmo.AbstractAsyncAuth.async_post_api_request",
            side_effect=partial(fake_post_request, hass),
        ) as mock_post_api_request,
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", ["light"]),
    ):
        assert await async_setup_component(
            hass, DOMAIN, {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

        await hass.async_block_till_done()

        assert mock_post_api_request.call_count == 7

        mock_impl.assert_called_once()
        mock_webhook.assert_not_called()

        await hass.async_start()
        await hass.async_block_till_done()
        mock_webhook.assert_called_once()

        # Fake webhook activation
        await simulate_webhook(
            hass, config_entry.data[CONF_WEBHOOK_ID], FAKE_WEBHOOK_ACTIVATION
        )
        await hass.async_block_till_done()

        mock_addwebhook.assert_called_once()
        mock_dropwebhook.assert_not_awaited()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=60),
        )
        await hass.async_block_till_done()

        assert hass.config_entries.async_entries(DOMAIN)
        assert len(hass.states.async_all()) > 0

        await hass.async_stop()
        mock_dropwebhook.assert_called_once()


async def test_setup_component_invalid_token_scope(hass: HomeAssistant) -> None:
    """Test handling of invalid token scope."""
    config_entry = MockConfigEntry(
        domain="netatmo",
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 1000,
                "scope": "read_smokedetector read_thermostat write_thermostat",
            },
        },
        options={},
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    mock_auth.assert_not_called()
    mock_impl.assert_called_once()
    mock_webhook.assert_not_called()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.async_entries(DOMAIN)

    # Test a reauth flow is initiated
    assert len(list(config_entry.async_get_active_flows(hass, {"reauth"}))) == 1

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)


async def test_setup_component_invalid_token(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test handling of invalid token."""

    async def fake_ensure_valid_token(*args, **kwargs):
        raise OAuth2TokenRequestReauthError(
            request_info=aiohttp.client.RequestInfo(
                url="http://example.com",
                method="GET",
                headers={},
                real_url="http://example.com",
            ),
            status=400,
            history=(),
            domain="netatmo",
        )

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url"
        ) as mock_webhook,
        patch("homeassistant.components.netatmo.OAuth2Session") as mock_session,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = partial(
            fake_post_request, hass
        )
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_session.return_value.async_ensure_token_valid.side_effect = (
            fake_ensure_valid_token
        )
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    mock_auth.assert_not_called()
    mock_impl.assert_called_once()
    mock_webhook.assert_not_called()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.async_entries(DOMAIN)

    # Test a reauth flow is initiated
    assert len(list(config_entry.async_get_active_flows(hass, {"reauth"}))) == 1

    for entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(entry.entry_id)


async def test_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    netatmo_auth: AsyncMock,
) -> None:
    """Test devices are registered."""
    with selected_platforms(
        [
            Platform.CAMERA,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.LIGHT,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert device_entries

    for device_entry in device_entries:
        identifier = list(device_entry.identifiers)[0]
        assert device_entry == snapshot(name=f"{identifier[0]}-{identifier[1]}")


async def test_home_devices_registered(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a device is registered for every home, without the select platform."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None
    assert home_device.name == "MYHOME"
    assert home_device.manufacturer == "Netatmo"
    assert home_device.model == "Home"
    assert home_device.configuration_url == "https://home.netatmo.com/control"
    assert config_entry.runtime_data.parent_device_ids[HOME_ID] == home_device.id

    # A home with no rooms and no modules still gets a device
    empty_home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "91763b24c43d3e344f424e8c"), config_entry.entry_id
    )
    assert empty_home_device is not None
    assert empty_home_device.name == "Unknown"


@contextmanager
def modified_homesdata(
    hass: HomeAssistant, modify: Callable[[dict[str, Any]], None]
) -> Iterator[None]:
    """Patch the API so /homesdata reports a modified topology.

    `modify` is handed MYHOME's modules keyed by id.
    """

    def modifier(payload: dict[str, Any]) -> None:
        body = payload.get("body")
        if not isinstance(body, dict):
            return
        for home in body.get("homes", []):
            if home["id"] == HOME_ID:
                modify({module["id"]: module for module in home["modules"]})

    async def fake_post(*args: Any, **kwargs: Any):
        return await fake_post_request(hass, *args, msg_callback=modifier, **kwargs)

    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
    ) as mock_auth:
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        yield


async def test_bridge_devices_registered(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a device is registered for a gateway that has no entities."""
    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    relay = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:00:fa:d0"), config_entry.entry_id
    )
    assert relay is not None
    assert relay.name == "Thermostat"
    assert relay.manufacturer == "Netatmo"
    assert relay.model == "Smart Thermostat Gateway"

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None
    assert relay.via_device_id == home_device.id


async def test_module_links_to_its_bridge(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a module is linked to its gateway rather than to its home."""
    with selected_platforms([Platform.CLIMATE, Platform.COVER, Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:30:d5:d4"), config_entry.entry_id
    )
    assert gateway is not None

    blinds = device_registry.async_get_device_by_identifier(
        (DOMAIN, "0009999992"), config_entry.entry_id
    )
    assert blinds is not None
    assert blinds.via_device_id == gateway.id

    # "Garden" is reached only through its own `bridge`; its station does not
    # list it as a bridged module
    station = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:80:bb:26"), config_entry.entry_id
    )
    assert station is not None

    garden = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:03:1b:e4"), config_entry.entry_id
    )
    assert garden is not None
    assert garden.via_device_id == station.id

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None
    assert station.via_device_id == home_device.id

    # Rooms keep linking to the home
    livingroom = device_registry.async_get_device_by_identifier(
        (DOMAIN, "2746182631"), config_entry.entry_id
    )
    assert livingroom is not None
    assert livingroom.via_device_id == home_device.id


async def test_nested_bridges(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test a gateway that itself reports through another gateway."""

    def bridge_the_relay(modules: dict[str, Any]) -> None:
        modules["12:34:56:00:fa:d0"]["bridge"] = "12:34:56:80:60:40"

    with (
        modified_homesdata(hass, bridge_the_relay),
        selected_platforms([Platform.CLIMATE]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    relay = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:00:fa:d0"), config_entry.entry_id
    )
    assert relay is not None
    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:80:60:40"), config_entry.entry_id
    )
    assert gateway is not None

    assert relay.via_device_id == gateway.id


async def test_conflicting_claims_resolve_to_the_bridge(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test a child claimed by two parents keeps the one its bridge names."""

    def claim_the_blinds(modules: dict[str, Any]) -> None:
        camera = modules["12:34:56:00:f1:62"]
        camera["modules_bridged"] = [*camera["modules_bridged"], "0009999992"]

    with (
        modified_homesdata(hass, claim_the_blinds),
        selected_platforms([Platform.COVER]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    blinds = device_registry.async_get_device_by_identifier(
        (DOMAIN, "0009999992"), config_entry.entry_id
    )
    assert blinds is not None
    # The blinds name the iDiamant gateway as their bridge, so the camera loses
    gateway = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:30:d5:d4"), config_entry.entry_id
    )
    assert gateway is not None
    assert blinds.via_device_id == gateway.id


async def test_conflicting_claims_without_a_bridge(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test a child that names no bridge stays with its first claimant."""

    def claim_the_bridgeless_blinds(modules: dict[str, Any]) -> None:
        del modules["0009999992"]["bridge"]
        camera = modules["12:34:56:00:f1:62"]
        camera["modules_bridged"] = [*camera["modules_bridged"], "0009999992"]

    with (
        modified_homesdata(hass, claim_the_bridgeless_blinds),
        selected_platforms([Platform.COVER]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    blinds = device_registry.async_get_device_by_identifier(
        (DOMAIN, "0009999992"), config_entry.entry_id
    )
    assert blinds is not None
    # The camera is listed before the iDiamant gateway in the API response
    camera = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:00:f1:62"), config_entry.entry_id
    )
    assert camera is not None
    assert blinds.via_device_id == camera.id


async def test_device_hierarchy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    netatmo_auth: AsyncMock,
) -> None:
    """Test every device is linked to the device it reports through."""
    with selected_platforms(
        [
            Platform.CAMERA,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.LIGHT,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    netatmo_ids = {
        device.id: next(
            identifier[1]
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        )
        for device in device_entries
    }
    hierarchy = {
        netatmo_ids[device.id]: netatmo_ids.get(device.via_device_id)
        for device in device_entries
    }

    assert dict(sorted(hierarchy.items())) == snapshot


async def test_disabled_home_is_not_polled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a home whose device is disabled is not set up or polled."""
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, HOME_ID)},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    data_handler = config_entry.runtime_data
    assert HOME_ID not in data_handler.account.homes
    assert f"home-{HOME_ID}" not in data_handler.publisher
    assert hass.states.get("climate.livingroom_livingroom") is None


async def test_disabled_home_keeps_its_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a disabled home keeps a device so it can be re-enabled."""
    assert await async_setup_component(hass, "config", {})

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, HOME_ID)},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None
    assert home_device.name == "MYHOME"
    assert home_device.model == "Home"
    assert home_device.disabled_by is dr.DeviceEntryDisabler.USER

    # A disabled home is still live, so its device must not be removable
    client = await hass_ws_client(hass)
    response = await client.remove_device(home_device.id)
    assert not response["success"]


async def test_disabled_home_disables_its_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a disabled home disables its devices without touching manual choices."""
    with selected_platforms([Platform.CLIMATE, Platform.COVER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        blinds = device_registry.async_get_device_by_identifier(
            (DOMAIN, "0009999992"), config_entry.entry_id
        )
        assert blinds is not None
        # A device the user disabled by hand, which must survive a home toggle
        device_registry.async_update_device(
            blinds.id, disabled_by=dr.DeviceEntryDisabler.USER
        )

        livingroom = device_registry.async_get_device_by_identifier(
            (DOMAIN, "2746182631"), config_entry.entry_id
        )
        assert livingroom is not None
        assert livingroom.disabled_by is None

        # A grandchild, as a gateway will produce once bridge nesting lands.
        # Without this the recursive walk is never exercised and would regress
        # silently.
        grandchild = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, "grandchild-module-id")},
            via_device_id=livingroom.id,
        )

        home_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, HOME_ID), config_entry.entry_id
        )
        assert home_device is not None
        device_registry.async_update_device(
            home_device.id, disabled_by=dr.DeviceEntryDisabler.USER
        )
        await hass.async_block_till_done()

        livingroom = device_registry.async_get_device_by_identifier(
            (DOMAIN, "2746182631"), config_entry.entry_id
        )
        assert livingroom.disabled_by is dr.DeviceEntryDisabler.INTEGRATION
        entity = entity_registry.async_get("climate.livingroom_livingroom")
        assert entity.disabled_by is er.RegistryEntryDisabler.DEVICE

        # The walk reaches a grandchild, not just direct children
        assert (
            device_registry.async_get(grandchild.id).disabled_by
            is dr.DeviceEntryDisabler.INTEGRATION
        )

        # Re-enabling restores what we disabled, and only what we disabled
        device_registry.async_update_device(home_device.id, disabled_by=None)
        await hass.async_block_till_done()

        livingroom = device_registry.async_get_device_by_identifier(
            (DOMAIN, "2746182631"), config_entry.entry_id
        )
        assert livingroom.disabled_by is None
        entity = entity_registry.async_get("climate.livingroom_livingroom")
        assert entity.disabled_by is None

        blinds = device_registry.async_get_device_by_identifier(
            (DOMAIN, "0009999992"), config_entry.entry_id
        )
        assert blinds.disabled_by is dr.DeviceEntryDisabler.USER

        assert device_registry.async_get(grandchild.id).disabled_by is None


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test we can only remove a device that no longer exists."""

    assert await async_setup_component(hass, "config", {})

    # The sensor platform is what gives account-owned air care modules a device
    with selected_platforms([Platform.CLIMATE, Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    climate_entity_livingroom = "climate.livingroom_livingroom"
    entity = entity_registry.async_get(climate_entity_livingroom)

    device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id)
    assert not response["success"]

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None
    response = await client.remove_device(home_device.id)
    assert not response["success"]

    # Air care modules belong to the account rather than to a home
    air_care_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12:34:56:25:cf:a8"), config_entry.entry_id
    )
    assert air_care_device is not None
    response = await client.remove_device(air_care_device.id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    response = await client.remove_device(dead_device_entry.id)
    assert response["success"]


async def test_disabled_home_keeps_its_descendants(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test a disabled home's rooms and modules cannot be removed."""
    assert await async_setup_component(hass, "config", {})

    with selected_platforms([Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        livingroom = device_registry.async_get_device_by_identifier(
            (DOMAIN, "2746182631"), config_entry.entry_id
        )
        assert livingroom is not None

        home_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, HOME_ID), config_entry.entry_id
        )
        assert home_device is not None
        device_registry.async_update_device(
            home_device.id, disabled_by=dr.DeviceEntryDisabler.USER
        )
        await hass.async_block_till_done()

    # The room is absent from the account now, but its device is still live
    client = await hass_ws_client(hass)
    response = await client.remove_device(livingroom.id)
    assert not response["success"]

    # A hand-disabled device keeps USER, so only the walk up to the home finds it
    device_registry.async_update_device(
        livingroom.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    response = await client.remove_device(livingroom.id)
    assert not response["success"]


async def test_oauth_implementation_not_available(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.netatmo.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("platform", "entity_id", "module_id", "initial_state"),
    [
        pytest.param(
            "switch", "switch.prise", "12:34:56:80:00:12:ac:f2", "on", id="switch"
        ),
        pytest.param(
            "cover", "cover.entrance_blinds", "0009999992", "closed", id="cover"
        ),
        pytest.param(
            "fan",
            "fan.centralized_ventilation_controler",
            "12:34:56:00:01:01:01:b1",
            "on",
            id="fan",
        ),
        pytest.param(
            "light",
            "light.unknown_00_11_22_33_00_11_45_fe",
            "00:11:22:33:00:11:45:fe",
            "off",
            id="light",
        ),
        pytest.param(
            "button",
            "button.entrance_blinds_preferred_position",
            "0009999992",
            STATE_UNKNOWN,
            id="button",
        ),
    ],
)
async def test_entity_unavailable_when_device_unreachable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    platform: str,
    entity_id: str,
    module_id: str,
    initial_state: str,
) -> None:
    """Test that entities become unavailable when their device is unreachable."""
    reachable = True

    def set_reachable(payload: dict) -> None:
        home = payload.get("body", {}).get("home")
        if not isinstance(home, dict):
            return
        for module in home.get("modules", []):
            if module.get("id") == module_id:
                module["reachable"] = reachable

    async def fake_post(*args: Any, **kwargs: Any):
        return await fake_post_request(
            hass, *args, msg_callback=set_reachable, **kwargs
        )

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", [platform]),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.netatmo.webhook.webhook_generate_url"),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == initial_state

    reachable = False
    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def _setup_switch_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_post: Callable[..., Coroutine[Any, Any, Any]],
) -> None:
    """Set up the switch platform with a custom API request side effect."""
    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.coordinator.PLATFORMS", [Platform.SWITCH]
        ),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.netatmo.webhook.webhook_generate_url"),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "failure_script",
    [
        pytest.param((True,), id="single_error"),
        pytest.param((True, True), id="errors_within_tolerance"),
        pytest.param(
            (True, True, False, True, True), id="error_count_reset_by_success"
        ),
    ],
)
async def test_entity_stays_available_through_tolerated_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    failure_script: tuple[bool, ...],
) -> None:
    """Test that entities do not flicker when up to two updates in a row fail."""
    # Scripted per home status request of the switch's home, so that the number
    # of consecutive errors does not depend on when the updates happen to run
    script: Iterator[bool] = iter(())
    failures = 0

    async def fake_post(*args: Any, **kwargs: Any):
        nonlocal failures
        if (
            kwargs.get("endpoint", "").endswith("homestatus")
            and kwargs.get("params", {}).get("home_id") == HOME_ID
            and next(script, False)
        ):
            failures += 1
            raise TimeoutError
        return await fake_post_request(hass, *args, **kwargs)

    await _setup_switch_platform(hass, config_entry, fake_post)

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON

    # Collect every state the entity takes on from here, so that a tolerated
    # error cannot go unnoticed by recovering before the final assertion
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    script = iter(failure_script)
    for _ in range(SCHEDULED_UPDATES):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert failures == sum(failure_script)
    assert not [
        event for event in state_changes if event.data["entity_id"] == SWITCH_ENTITY_ID
    ]


@pytest.mark.parametrize(
    "error",
    [TimeoutError, pyatmo.ApiError],
    ids=["timeout", "api_error"],
)
async def test_entity_unavailable_after_three_failed_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: type[Exception],
) -> None:
    """Test that entities go unavailable once three updates in a row fail."""
    failing = False
    failures = 0

    async def fake_post(*args: Any, **kwargs: Any):
        nonlocal failures
        if (
            failing
            and kwargs.get("endpoint", "").endswith("homestatus")
            and kwargs.get("params", {}).get("home_id") == HOME_ID
        ):
            failures += 1
            raise error
        return await fake_post_request(hass, *args, **kwargs)

    await _setup_switch_platform(hass, config_entry, fake_post)

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON

    failing = True
    for _ in range(SCHEDULED_UPDATES):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert failures >= 3
    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_failed_updates_are_retried_with_escalating_backoff(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failing home is retried promptly at first, then less often."""
    failing = False
    request_times: list[float] = []

    async def fake_post(*args: Any, **kwargs: Any):
        if (
            failing
            and kwargs.get("endpoint", "").endswith("homestatus")
            and kwargs.get("params", {}).get("home_id") == HOME_ID
        ):
            request_times.append(time())
            raise TimeoutError
        return await fake_post_request(hass, *args, **kwargs)

    with patch.object(coordinator, "MAX_ERROR_BACKOFF", 4 * HOME_POLL_INTERVAL):
        await _setup_switch_platform(hass, config_entry, fake_post)

        failing = True
        for _ in range(SCHEDULED_UPDATES):
            freezer.tick(timedelta(seconds=30))
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)

    gaps = [round(later - earlier) for earlier, later in pairwise(request_times)]

    # The first retry comes at the regular poll interval (rounded up to the next
    # scheduled update), the delay then doubles per consecutive error until the
    # patched cap of 600s is reached
    assert gaps == [180, 300, 600, 600]


async def test_log_when_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unavailability and recovery are each logged exactly once."""
    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.netatmo.webhook.webhook_generate_url"),
    ):
        post_request = mock_auth.return_value.async_post_api_request
        post_request.side_effect = partial(fake_post_request, hass)
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    data_handler = config_entry.runtime_data

    with caplog.at_level(
        logging.INFO, logger="homeassistant.components.netatmo.coordinator"
    ):
        post_request.side_effect = pyatmo.ApiError("boom")
        await data_handler.async_fetch_data(ACCOUNT)
        await data_handler.async_fetch_data(ACCOUNT)

        assert caplog.text.count("Error while fetching") == 1

        post_request.side_effect = partial(fake_post_request, hass)
        await data_handler.async_fetch_data(ACCOUNT)
        await data_handler.async_fetch_data(ACCOUNT)

        assert caplog.text.count("recovered") == 1
