"""Tests for the Withings component."""
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

from aiohttp.hdrs import METH_HEAD
from aiowithings import (
    NotificationCategory,
    WithingsAuthenticationFailedError,
    WithingsUnauthorizedError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.webhook import async_generate_url
from homeassistant.components.withings import CONFIG_SCHEMA, async_setup
from homeassistant.components.withings.const import CONF_USE_WEBHOOK, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import call_webhook, prepare_webhook_setup, setup_integration
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_cloud_connection_status,
)
from tests.components.cloud import mock_cloud
from tests.typing import ClientSessionGenerator


def config_schema_validate(withings_config) -> dict:
    """Assert a schema config succeeds."""
    hass_config = {DOMAIN: withings_config}

    return CONFIG_SCHEMA(hass_config)


def config_schema_assert_fail(withings_config) -> None:
    """Assert a schema config will fail."""
    with pytest.raises(vol.MultipleInvalid):
        config_schema_validate(withings_config)


def test_config_schema_basic_config() -> None:
    """Test schema."""
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_USE_WEBHOOK: True,
        }
    )


def test_config_schema_client_id() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {CONF_CLIENT_SECRET: "my_client_secret", CONF_CLIENT_ID: ""}
    )
    config_schema_validate(
        {CONF_CLIENT_SECRET: "my_client_secret", CONF_CLIENT_ID: "my_client_id"}
    )


def test_config_schema_client_secret() -> None:
    """Test schema."""
    config_schema_assert_fail({CONF_CLIENT_ID: "my_client_id", CONF_CLIENT_SECRET: ""})
    config_schema_validate(
        {CONF_CLIENT_ID: "my_client_id", CONF_CLIENT_SECRET: "my_client_secret"}
    )


def test_config_schema_use_webhook() -> None:
    """Test schema."""
    config_schema_validate(
        {CONF_CLIENT_ID: "my_client_id", CONF_CLIENT_SECRET: "my_client_secret"}
    )
    config = config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_USE_WEBHOOK: True,
        }
    )
    assert config[DOMAIN][CONF_USE_WEBHOOK] is True
    config = config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_USE_WEBHOOK: False,
        }
    )
    assert config[DOMAIN][CONF_USE_WEBHOOK] is False
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_USE_WEBHOOK: "A",
        }
    )


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test method."""
    hass.async_create_task = MagicMock()

    await async_setup(hass, {})

    hass.async_create_task.assert_not_called()


async def test_data_manager_webhook_subscription(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
) -> None:
    """Test data manager webhook subscriptions."""
    await setup_integration(hass, webhook_config_entry)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert withings.subscribe_notification.call_count == 6

    webhook_url = "https://example.com/api/webhook/55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"

    withings.subscribe_notification.assert_any_call(
        webhook_url, NotificationCategory.WEIGHT
    )
    withings.subscribe_notification.assert_any_call(
        webhook_url, NotificationCategory.PRESSURE
    )
    withings.subscribe_notification.assert_any_call(
        webhook_url, NotificationCategory.ACTIVITY
    )
    withings.subscribe_notification.assert_any_call(
        webhook_url, NotificationCategory.SLEEP
    )

    withings.revoke_notification_configurations.assert_any_call(
        webhook_url, NotificationCategory.IN_BED
    )
    withings.revoke_notification_configurations.assert_any_call(
        webhook_url, NotificationCategory.OUT_BED
    )


async def test_webhook_subscription_polling_config(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test webhook subscriptions not run when polling."""
    await setup_integration(hass, polling_config_entry, False)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert withings.revoke_notification_configurations.call_count == 0
    assert withings.subscribe_notification.call_count == 0
    assert withings.list_notification_configurations.call_count == 0


async def test_head_request(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test we handle head requests Withings sends."""
    await setup_integration(hass, webhook_config_entry)
    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)

    response = await client.request(
        method=METH_HEAD,
        path=urlparse(webhook_url).path,
    )
    assert response.status == 200


async def test_webhooks_request_data(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test calling a webhook requests data."""
    await setup_integration(hass, webhook_config_entry)
    await prepare_webhook_setup(hass, freezer)

    client = await hass_client_no_auth()

    assert withings.get_measurement_since.call_count == 0
    assert withings.get_measurement_in_period.call_count == 1

    await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotificationCategory.WEIGHT},
        client,
    )
    assert withings.get_measurement_since.call_count == 1
    assert withings.get_measurement_in_period.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        WithingsUnauthorizedError(401),
        WithingsAuthenticationFailedError(500),
    ],
)
async def test_triggering_reauth(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    error: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test triggering reauth."""
    await setup_integration(hass, polling_config_entry, False)

    withings.get_measurement_since.side_effect = error
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH


@pytest.mark.parametrize(
    ("config_entry"),
    [
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123",
            data={
                "token": {"userid": 123},
                "profile": "henk",
                "use_webhook": False,
                "webhook_id": "3290798afaebd28519c4883d3d411c7197572e0cc9b8d507471f59a700a61a55",
            },
        ),
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123",
            data={
                "token": {"userid": 123},
                "profile": "henk",
                "use_webhook": False,
            },
        ),
    ],
)
async def test_config_flow_upgrade(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test config flow upgrade."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(config_entry.entry_id)

    assert entry.unique_id == "123"
    assert entry.data["token"]["userid"] == 123
    assert CONF_WEBHOOK_ID in entry.data


async def test_setup_with_cloudhook(
    hass: HomeAssistant, cloudhook_config_entry: MockConfigEntry, withings: AsyncMock
) -> None:
    """Test if set up with active cloud subscription and cloud hook."""

    await mock_cloud(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ) as fake_create_cloudhook, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.cloud.async_delete_cloudhook"
    ) as fake_delete_cloudhook, patch(
        "homeassistant.components.withings.webhook_generate_url"
    ):
        await setup_integration(hass, cloudhook_config_entry)
        assert hass.components.cloud.async_active_subscription() is True

        assert (
            hass.config_entries.async_entries(DOMAIN)[0].data["cloudhook_url"]
            == "https://hooks.nabu.casa/ABCD"
        )

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)
        fake_create_cloudhook.assert_not_called()

        for config_entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(config_entry.entry_id)
            fake_delete_cloudhook.assert_called_once()

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_removing_entry_with_cloud_unavailable(
    hass: HomeAssistant, cloudhook_config_entry: MockConfigEntry, withings: AsyncMock
) -> None:
    """Test handling cloud unavailable when deleting entry."""

    await mock_cloud(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.cloud.async_delete_cloudhook",
        side_effect=CloudNotAvailable(),
    ), patch(
        "homeassistant.components.withings.webhook_generate_url",
    ):
        await setup_integration(hass, cloudhook_config_entry)
        assert hass.components.cloud.async_active_subscription() is True

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)

        for config_entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(config_entry.entry_id)

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_with_cloud(
    hass: HomeAssistant,
    webhook_config_entry: MockConfigEntry,
    withings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if set up with active cloud subscription."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ) as fake_create_cloudhook, patch(
        "homeassistant.components.withings.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.cloud.async_delete_cloudhook"
    ) as fake_delete_cloudhook, patch(
        "homeassistant.components.withings.webhook_generate_url"
    ):
        await setup_integration(hass, webhook_config_entry)
        await prepare_webhook_setup(hass, freezer)

        assert hass.components.cloud.async_active_subscription() is True
        assert hass.components.cloud.async_is_connected() is True
        fake_create_cloudhook.assert_called_once()
        fake_delete_cloudhook.assert_called_once()

        assert (
            hass.config_entries.async_entries("withings")[0].data["cloudhook_url"]
            == "https://hooks.nabu.casa/ABCD"
        )

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)

        for config_entry in hass.config_entries.async_entries("withings"):
            await hass.config_entries.async_remove(config_entry.entry_id)
            fake_delete_cloudhook.call_count == 2

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("url", ["http://example.com", "https://example.com:444"])
async def test_setup_no_webhook(
    hass: HomeAssistant,
    webhook_config_entry: MockConfigEntry,
    withings: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    url: str,
) -> None:
    """Test if set up with cloud link and without https."""
    hass.config.components.add("cloud")
    with patch(
        "homeassistant.helpers.network.get_url",
        return_value="http://example.nabu.casa",
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.withings.webhook_generate_url"
    ) as mock_async_generate_url:
        mock_async_generate_url.return_value = url
        await setup_integration(hass, webhook_config_entry)
        await prepare_webhook_setup(hass, freezer)

        await hass.async_block_till_done()
        mock_async_generate_url.assert_called_once()

    assert "https and port 443 is required to register the webhook" in caplog.text


async def test_cloud_disconnect(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test disconnecting from the cloud."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ), patch(
        "homeassistant.components.withings.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.cloud.async_delete_cloudhook",
    ), patch(
        "homeassistant.components.withings.webhook_generate_url",
    ):
        await setup_integration(hass, webhook_config_entry)
        await prepare_webhook_setup(hass, freezer)
        assert hass.components.cloud.async_active_subscription() is True
        assert hass.components.cloud.async_is_connected() is True

        await hass.async_block_till_done()

        withings.list_notification_configurations.return_value = []

        assert withings.subscribe_notification.call_count == 6

        async_mock_cloud_connection_status(hass, False)
        await hass.async_block_till_done()

        assert withings.revoke_notification_configurations.call_count == 3

        async_mock_cloud_connection_status(hass, True)
        await hass.async_block_till_done()

        assert withings.subscribe_notification.call_count == 12


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        [{"userid": 0, "appli": NotificationCategory.WEIGHT.value}, 0],  # Success
        [{"userid": None, "appli": 1}, 0],  # Success, we ignore the user_id.
        [{}, 12],  # No request body.
        [{"userid": "GG"}, 20],  # appli not provided.
        [{"userid": 0}, 20],  # appli not provided.
        [
            {"userid": 11, "appli": NotificationCategory.WEIGHT.value},
            0,
        ],  # Success, we ignore the user_id
    ],
)
async def test_webhook_post(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    body: dict[str, Any],
    expected_code: int,
    current_request_with_host: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test webhook callback."""
    await setup_integration(hass, webhook_config_entry)
    await prepare_webhook_setup(hass, freezer)
    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)

    resp = await client.post(urlparse(webhook_url).path, data=body)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data = await resp.json()
    resp.close()

    assert data["code"] == expected_code
