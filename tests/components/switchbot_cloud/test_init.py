"""Tests for the SwitchBot Cloud integration init."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from switchbot_api import (
    Device,
    PowerState,
    Remote,
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)

from homeassistant.components import cloud
from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.switchbot_cloud.const import (
    CONF_CLOUDHOOK_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

from . import configure_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_cloud_connection_status,
)
from tests.components.cloud import mock_cloud
from tests.typing import ClientSessionGenerator

CLOUDHOOK_URL = "https://hooks.nabu.casa/ABCD"


def _water_detector() -> Device:
    """Return a webhook-manageable device (Water Detector)."""
    return Device(
        version="V1.0",
        deviceId="water-detector-1",
        deviceName="water-detector-name-1",
        deviceType="Water Detector",
        hubDeviceId="test-hub-id",
    )


@pytest.fixture
def mock_list_devices():
    """Mock list_devices."""
    with patch.object(SwitchBotAPI, "list_devices") as mock_list_devices:
        yield mock_list_devices


@pytest.fixture
def mock_get_status():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "get_status") as mock_get_status:
        yield mock_get_status


@pytest.fixture
def mock_get_webook_configuration():
    """Mock get_status."""
    with patch.object(
        SwitchBotAPI, "get_webook_configuration"
    ) as mock_get_webook_configuration:
        yield mock_get_webook_configuration


@pytest.fixture
def mock_delete_webhook():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "delete_webhook") as mock_delete_webhook:
        yield mock_delete_webhook


@pytest.fixture
def mock_setup_webhook():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "setup_webhook") as mock_setup_webhook:
        yield mock_setup_webhook


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test successful setup of entry."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": ["https://example.com"]}
    mock_list_devices.return_value = [
        Remote(
            version="V1.0",
            deviceId="air-conditonner-id-1",
            deviceName="air-conditonner-name-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
        Device(
            version="V1.0",
            deviceId="plug-id-1",
            deviceName="plug-name-1",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="plug-id-2",
            deviceName="plug-name-2",
            remoteType="DIY Plug",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="meter-pro-1",
            deviceName="meter-pro-name-1",
            deviceType="MeterPro(CO2)",
            hubDeviceId="test-hub-id",
        ),
        Remote(
            version="V1.0",
            deviceId="hub2-1",
            deviceName="hub2-name-1",
            deviceType="Hub 2",
            hubDeviceId="test-hub-id",
        ),
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()
    mock_get_webook_configuration.assert_called_once()
    mock_delete_webhook.assert_called_once()
    mock_setup_webhook.assert_called_once()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (SwitchBotAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (SwitchBotConnectionError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_fails_when_listing_devices(
    hass: HomeAssistant,
    error: Exception,
    state: ConfigEntryState,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test error handling when list_devices in setup of entry."""
    mock_list_devices.side_effect = error
    entry = await configure_integration(hass)
    assert entry.state is state

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_not_called()


async def test_setup_entry_fails_when_refreshing(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test error handling in get_status in setup of entry."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="test-id",
            deviceName="test-name",
            deviceType="Plug",
            hubDeviceId="test-hub-id",
        )
    ]
    mock_get_status.side_effect = SwitchBotConnectionError
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    mock_list_devices.assert_called_once()
    mock_get_status.assert_called()


async def test_posting_to_webhook(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test handler webhook call."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": ["https://example.com"]}
    mock_list_devices.return_value = [
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    client = await hass_client_no_auth()
    # fire webhook
    await client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "eventType": "changeReport",
            "eventVersion": "1",
            "context": {"deviceType": "...", "deviceMac": "vacuum-1"},
        },
    )

    await hass.async_block_till_done()

    mock_setup_webhook.assert_called_once()


async def test_polling_is_only_disabled_after_webhook_delivery(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling stays enabled until a webhook is received."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": ["https://example.com"]}
    mock_list_devices.return_value = [
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {
        "battery": 71,
        "deviceId": "vacuum-1",
        "onlineStatus": "online",
        "workingStatus": "Paused",
    }
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    # Validate the state is fetched initially
    entity_id = "vacuum.vacuum_name_1"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["battery_level"] == 71

    # Change API return values and wait for update
    mock_get_status.return_value = {
        "battery": 60,
        "deviceId": "vacuum-1",
        "onlineStatus": "online",
        "workingStatus": "Paused",
    }

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Validate that the state was updated again via fetch
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["battery_level"] == 60

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    client = await hass_client_no_auth()
    await client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "eventType": "changeReport",
            "eventVersion": "1",
            "context": {
                "battery": 74,
                "deviceType": "WoSweeperMini",
                "deviceMac": "vacuum-1",
                "onlineStatus": "online",
                "workingStatus": "Clearing",
            },
        },
    )

    await hass.async_block_till_done()

    mock_get_status.reset_mock()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # After receiving a webhook, no fetch should happen
    mock_get_status.assert_not_called()


async def test_setup_entry_skips_webhook_without_external_url(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test webhook registration is skipped without an external URL."""
    mock_list_devices.return_value = [
        Device(
            deviceId="vacuum-1",
            deviceName="vacuum-name-1",
            deviceType="K10+",
            hubDeviceId=None,
        ),
    ]
    mock_get_status.return_value = {"power": PowerState.ON.value}

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_get_webook_configuration.assert_not_called()
    mock_delete_webhook.assert_not_called()
    mock_setup_webhook.assert_not_called()
    assert entry.data[CONF_WEBHOOK_ID] not in hass.data.get(WEBHOOK_DOMAIN, {})
    assert "no external URL is available" in caplog.text


async def test_setup_creates_cloudhook_when_cloud_active(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test a cloudhook is created and registered when cloud is active.

    This is the local-only-HA case: no external_url is configured, but a Nabu
    Casa subscription is active, so SwitchBot should be given the cloudhook URL.
    """
    await mock_cloud(hass)
    await hass.async_block_till_done()

    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as fake_create_cloudhook,
        patch("homeassistant.components.cloud.async_delete_cloudhook"),
    ):
        entry = await configure_integration(hass)
        assert entry.state is ConfigEntryState.LOADED

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # Cloudhook was created and persisted in entry.data ...
        fake_create_cloudhook.assert_called_once()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL
        # ... and registered with SwitchBot's cloud.
        mock_setup_webhook.assert_called_once_with(CLOUDHOOK_URL)


async def test_setup_reuses_persisted_cloudhook(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test a previously persisted cloudhook is reused, not recreated."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    # SwitchBot already has the cloudhook registered (so nothing to re-add).
    mock_get_webook_configuration.return_value = {"urls": [CLOUDHOOK_URL]}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_setup_webhook.return_value = {}

    # An entry that already has both a webhook id and a persisted cloudhook.
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "test-token",
            CONF_API_KEY: "test-api-key",
            CONF_WEBHOOK_ID: "test-webhook-id",
            CONF_CLOUDHOOK_URL: CLOUDHOOK_URL,
        },
        entry_id="123456",
        unique_id="123456",
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as fake_create_cloudhook,
        patch("homeassistant.components.cloud.async_delete_cloudhook"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # No new cloudhook should have been created and SwitchBot's already-set
        # URL (the cloudhook) needs no re-registration.
        fake_create_cloudhook.assert_not_called()
        mock_setup_webhook.assert_not_called()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL


async def test_setup_falls_back_to_local_url_without_cloud(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test the local external URL is used when no cloud subscription exists."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    with patch.object(cloud, "async_active_subscription", return_value=False):
        entry = await configure_integration(hass)
        assert entry.state is ConfigEntryState.LOADED

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert CONF_CLOUDHOOK_URL not in entry.data
    mock_setup_webhook.assert_called_once()
    registered_url = mock_setup_webhook.call_args[0][0]
    assert registered_url.startswith("https://example.com")


async def test_cloud_connects_after_setup(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test a cloudhook is created when the cloud connects after setup.

    On a local-only install the cloud may only become available after the entry
    has already been set up; the integration must react to the connection
    change and register the cloudhook with SwitchBot.
    """
    await mock_cloud(hass)
    await hass.async_block_till_done()

    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    # Cloud is not active at setup time.
    with patch.object(cloud, "async_active_subscription", return_value=False):
        entry = await configure_integration(hass)
        assert entry.state is ConfigEntryState.LOADED
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert CONF_CLOUDHOOK_URL not in entry.data

    # Cloud becomes active and connects.
    with (
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as fake_create_cloudhook,
        patch("homeassistant.components.cloud.async_delete_cloudhook"),
    ):
        async_mock_cloud_connection_status(hass, True)
        await hass.async_block_till_done()

        fake_create_cloudhook.assert_called_once()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL
        mock_setup_webhook.assert_called_with(CLOUDHOOK_URL)


async def test_setup_active_subscription_not_connected(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test no cloudhook is created while the cloud is not yet connected.

    ``async_active_subscription`` is true as soon as the user is logged in with a
    valid subscription, but ``async_create_cloudhook`` raises ``CloudNotConnected``
    until the cloud connection is established. Setup must not call it (which would
    propagate and abort setup); the connection-change listener creates the
    cloudhook once connected.
    """
    await mock_cloud(hass)
    await hass.async_block_till_done()

    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    # Subscription active, but the cloud connection is not established yet.
    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=False),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            side_effect=cloud.CloudNotConnected,
        ) as fake_create_cloudhook,
        patch("homeassistant.components.cloud.async_delete_cloudhook"),
    ):
        entry = await configure_integration(hass)
        await hass.async_block_till_done()

        # Setup completed without aborting, and no cloudhook was created.
        assert entry.state is ConfigEntryState.LOADED
        fake_create_cloudhook.assert_not_called()
        assert CONF_CLOUDHOOK_URL not in entry.data

    # Once the cloud connects, the cloudhook is created and registered.
    with (
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ) as fake_create_cloudhook,
        patch("homeassistant.components.cloud.async_delete_cloudhook"),
    ):
        async_mock_cloud_connection_status(hass, True)
        await hass.async_block_till_done()

        fake_create_cloudhook.assert_called_once()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL
        mock_setup_webhook.assert_called_with(CLOUDHOOK_URL)


async def test_cloudhook_deleted_on_entry_removal(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test the cloudhook is deleted when the config entry is removed."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as fake_delete_cloudhook,
    ):
        entry = await configure_integration(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL

        # Ignore the pre-create cleanup delete that happened during setup; we
        # only care that removal deletes the cloudhook.
        fake_delete_cloudhook.reset_mock()

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        fake_delete_cloudhook.assert_called_once_with(hass, entry.data[CONF_WEBHOOK_ID])


async def test_remove_entry_without_cloudhook_skips_delete(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test no cloudhook delete is attempted when none was created."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    with (
        patch.object(cloud, "async_active_subscription", return_value=False),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as fake_delete_cloudhook,
    ):
        entry = await configure_integration(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert CONF_CLOUDHOOK_URL not in entry.data

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        fake_delete_cloudhook.assert_not_called()


async def test_remove_entry_with_cloud_unavailable(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    mock_get_webook_configuration,
    mock_delete_webhook,
    mock_setup_webhook,
) -> None:
    """Test CloudNotAvailable is handled gracefully on entry removal."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [_water_detector()]
    mock_get_status.return_value = {"battery": 100}
    mock_delete_webhook.return_value = {}
    mock_setup_webhook.return_value = {}

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value=CLOUDHOOK_URL,
        ),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook",
            side_effect=CloudNotAvailable(),
        ),
    ):
        entry = await configure_integration(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert entry.data[CONF_CLOUDHOOK_URL] == CLOUDHOOK_URL

        # Should not raise even though delete raises CloudNotAvailable.
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert not hass.config_entries.async_entries("switchbot_cloud")
