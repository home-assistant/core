"""The tests for Netatmo doortag."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.netatmo import DOMAIN, binary_sensor, sensor
from homeassistant.const import CONF_WEBHOOK_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    fake_post_request,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse


def get_netatmo_entity_instance(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_id: str
) -> object | None:
    """Helper to find the specific entity instance."""
    BINARY_SENSOR_DOMAIN = "binary_sensor"

    # 1. Get the EntityComponent object for the binary_sensor domain
    component = hass.data.get(BINARY_SENSOR_DOMAIN)

    if not component:
        raise ValueError(f"Component not found for {BINARY_SENSOR_DOMAIN}")

    platform_key = config_entry.entry_id  # This should be '01K7CGMWD2YW4XNXS0P0C2CK5N'

    platform_instance = component._platforms.get(platform_key)

    if not platform_instance:
        raise ValueError(
            f"Netatmo platform not loaded for {BINARY_SENSOR_DOMAIN} with key {platform_key}"
        )

    platform_entities = platform_instance.entities

    if not platform_entities:
        raise ValueError(f"No Netatmo entities found for {BINARY_SENSOR_DOMAIN}")

    entity_instance = platform_entities.get(entity_id)

    if entity_instance:
        return entity_instance

    return None


async def set_netatmo_entity_state(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_id: str, ha_state: str
) -> None:
    """Sets the HA state and synchronizes the underlying mocked Pyatmo data."""
    # Get the actual entity object instance
    entity_instance = get_netatmo_entity_instance(hass, config_entry, entity_id)

    if entity_instance is None:
        raise ValueError(f"Entity instance with ID {entity_id} not found.")

    # Modify the underlying Pyatmo data to reflect the new state
    if ha_state == STATE_ON:
        pyatmo_status = "open"
    elif ha_state == STATE_OFF:
        pyatmo_status = "closed"
    else:
        pyatmo_status = "undefined"

    # Update the entity's state and ensure Home Assistant is aware of the change
    setattr(entity_instance.device, "status", pyatmo_status)
    entity_instance.async_update_callback()
    entity_instance.async_write_ha_state()

    # Wait for the state to be fully processed
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.BINARY_SENSOR,
        entity_registry,
        snapshot,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("no_news", None),
        ("calibrating", None),
        ("undefined", None),
        ("closed", False),
        ("open", True),
        ("calibration_failed", None),
        ("maintenance", None),
        ("weak_signal", None),
        ("invalid_value", None),
    ],
)
async def test_process_opening_status(status: str, expected: bool | None) -> None:
    """Test opening status translation."""
    assert binary_sensor.process_opening_status_string(status) == expected


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("door", BinarySensorDeviceClass.DOOR),
        ("window", BinarySensorDeviceClass.WINDOW),
        ("garage", BinarySensorDeviceClass.GARAGE_DOOR),
        ("gate", BinarySensorDeviceClass.OPENING),
        ("furniture", BinarySensorDeviceClass.OPENING),
        ("other", BinarySensorDeviceClass.OPENING),
        ("invalid_value", None),
    ],
)
async def test_process_opening_category(
    category: str, expected: BinarySensorDeviceClass | None
) -> None:
    """Test opening category translation."""
    assert binary_sensor.process_opening_category_string(category) == expected


@pytest.mark.parametrize(
    ("battery_state", "expected"),
    [
        ("max", 100),
        ("full", 90),
        ("high", 75),
        ("medium", 50),
        ("low", 25),
        ("very_low", 10),
        ("invalid_value", None),
    ],
)
async def test_process_battery_state(battery_state: str, expected: int) -> None:
    """Test battery state translation."""
    assert sensor.process_battery_state_string(battery_state) == expected


@pytest.mark.parametrize(
    ("rf_strength", "expected"),
    [
        (95, "Low"),
        (90, "Low"),
        (80, "Medium"),
        (76, "Medium"),
        (66, "High"),
        (60, "High"),
        (59, "Full"),
        (10, "Full"),
        (0, "Full"),
        ("invalid_value", None),
    ],
)
async def test_process_rf_strength(rf_strength: int, expected: str) -> None:
    """Test RF strength translation."""
    assert sensor.process_rf_strength_string(rf_strength) == expected


async def test_doortag_setup_and_webhook_reconnect(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test doortag setup and services."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.data_handler.PLATFORMS",
            ["camera", "binary_sensor", "sensor"],
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake webhook activation
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    # Define the mock home_id, camera_id and doortag_id for the test
    _home_id = "91763b24c43d3e344f424e8b"
    _camera_id_indoor = "12:34:56:00:f1:62"
    _camera_entity_indoor = "camera.hall"
    _doortag_entity_id = "12:34:56:00:86:99"
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_reachability = f"binary_sensor.{_doortag_entity}_reachability"
    _doortag_entity_battery = f"sensor.{_doortag_entity}_battery"
    _doortag_entity_rf_status = f"sensor.{_doortag_entity}_rf_status"

    # Check entity creation
    assert hass.states.get(_doortag_entity_opening) is not None
    assert hass.states.get(_doortag_entity_battery) is not None
    # Check non-creation of other entities
    assert hass.states.get(_doortag_entity_reachability) is None
    assert hass.states.get(_doortag_entity_rf_status) is None
    # Check initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"

    # Fake camera connection
    response = {
        "user_id": "1234567890",
        "event_type": "connection",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-connection",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(_camera_entity_indoor).state == "streaming"

    # Fake module connect
    response = {
        "user_id": "1234567890",
        "event_type": "module_connect",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-module_connect",
        "module_id": _doortag_entity_id,
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    # Check if doortab became available (this indicated as unknown state, not as unavailable)
    assert hass.states.get(_doortag_entity_opening).state == "unknown"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Fake module disconnect
    response = {
        "user_id": "1234567890",
        "event_type": "module_disconnect",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-module_disconnect",
        "module_id": _doortag_entity_id,
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    # Check if became unavailable
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"


async def test_doortag_setup_and_webhook_open(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test doortag setup and open on big_move and small_move when closed."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.data_handler.PLATFORMS",
            ["camera", "binary_sensor", "sensor"],
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        await async_setup_component(hass, "binary_sensor", {})
        await async_setup_component(hass, "sensor", {})
        await async_setup_component(hass, "camera", {})
        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake webhook activation
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    # Define the mock home_id, camera_id and doortag_id for the test
    _home_id = "91763b24c43d3e344f424e8b"
    _camera_id_indoor = "12:34:56:00:f1:62"
    _camera_entity_indoor = "camera.hall"
    _doortag_entity_id = "12:34:56:00:86:99"
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_reachability = f"binary_sensor.{_doortag_entity}_reachability"
    _doortag_entity_battery = f"sensor.{_doortag_entity}_battery"
    _doortag_entity_rf_status = f"sensor.{_doortag_entity}_rf_status"
    _doortag_entity_unique_id = f"{_doortag_entity_id}-opening"

    # Check entity creation
    assert hass.states.get(_doortag_entity_opening) is not None
    assert hass.states.get(_doortag_entity_battery) is not None
    # Check non-creation of other entities
    assert hass.states.get(_doortag_entity_reachability) is None
    assert hass.states.get(_doortag_entity_rf_status) is None
    # Check initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"

    # Fake camera connection
    response = {
        "user_id": "1234567890",
        "event_type": "connection",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-connection",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(_camera_entity_indoor).state == "streaming"

    # Fake module connect
    response = {
        "user_id": "1234567890",
        "event_type": "module_connect",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-module_connect",
        "module_id": _doortag_entity_id,
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    # Check if became available (this indicated as unknown state, not as unavailable)
    assert hass.states.get(_doortag_entity_opening).state == "unknown"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Set state to closed
    await set_netatmo_entity_state(
        hass, config_entry, _doortag_entity_opening, STATE_OFF
    )
    hass.states.async_set(_doortag_entity_opening, STATE_OFF)
    await hass.async_block_till_done()

    # State should be closed
    assert hass.states.get(_doortag_entity_opening).state == "off"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Trigger open change with erroneous webhook data
    response = {
        "event_type": "tag_big_move",
        "module_id": _doortag_entity_id,
    }
    await simulate_webhook(hass, webhook_id, response)

    # State should not change
    assert hass.states.get(_doortag_entity_opening).state == "off"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Trigger open change by tag_big_move webhook
    response = {
        "event_type": "tag_big_move",
        "module_id": _doortag_entity_id,
        "device_id": _camera_id_indoor,
        "camera_id": _camera_id_indoor,
        "home_id": _home_id,
        "event_id": "601dce1560abca1ebad9b723",
        "message": "Movement detected by Window Hall",
        "push_type": "NACamera-tag_big_move",
    }
    await simulate_webhook(hass, webhook_id, response)

    # State should change to open (as it was closed before)
    assert hass.states.get(_doortag_entity_opening).state == "on"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Trigger change by tag_big_move webhook
    response = {
        "event_type": "tag_big_move",
        "module_id": _doortag_entity_id,
        "device_id": _camera_id_indoor,
        "camera_id": _camera_id_indoor,
        "home_id": _home_id,
        "event_id": "601dce1560abca1ebad9b723",
        "message": "Movement detected by Window Hall",
        "push_type": "NACamera-tag_big_move",
    }
    await simulate_webhook(hass, webhook_id, response)

    # State should remain open (as we don't know the move closed it)
    assert hass.states.get(_doortag_entity_opening).state == "on"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Set state to closed
    hass.states.async_set(_doortag_entity_opening, STATE_OFF)
    await set_netatmo_entity_state(
        hass, config_entry, _doortag_entity_opening, STATE_OFF
    )
    await hass.async_block_till_done()

    # State should be closed
    assert hass.states.get(_doortag_entity_opening).state == "off"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Trigger open change by tag_small_move webhook
    response = {
        "event_type": "tag_small_move",
        "module_id": _doortag_entity_id,
        "device_id": _camera_id_indoor,
        "camera_id": _camera_id_indoor,
        "home_id": _home_id,
        "event_id": "601dce1560abca1ebad9b723",
        "message": "Movement detected by Window Hall",
        "push_type": "NACamera-tag_small_move",
    }
    await simulate_webhook(hass, webhook_id, response)

    # State should change to open (as it was closed before)
    assert hass.states.get(_doortag_entity_opening).state == "on"
    assert hass.states.get(_doortag_entity_battery).state == "75"


async def test_setup_component_no_devices(hass: HomeAssistant, config_entry) -> None:
    """Test setup with no devices."""
    fake_post_hits = 0

    async def fake_post_request_no_data(*args, **kwargs):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return AiohttpClientMockResponse(
            method="POST",
            url=kwargs["endpoint"],
            json={},
        )

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.data_handler.PLATFORMS", ["binary_sensor"]
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ),
    ):
        mock_auth.return_value.async_post_api_request.side_effect = (
            fake_post_request_no_data
        )
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Fake webhook activation
        await simulate_webhook(
            hass, config_entry.data[CONF_WEBHOOK_ID], FAKE_WEBHOOK_ACTIVATION
        )
        await hass.async_block_till_done()

        assert fake_post_hits == 3

        assert hass.config_entries.async_entries(DOMAIN)
        assert len(hass.states.async_all()) == 0


async def test_doortag_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test doortag setup."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.data_handler.PLATFORMS",
            ["camera", "binary_sensor", "sensor"],
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake webhook activation
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    # Define the mock home_id, camera_id and doortag_id for the test
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_reachability = f"binary_sensor.{_doortag_entity}_reachability"
    _doortag_entity_battery = f"sensor.{_doortag_entity}_battery"
    _doortag_entity_rf_status = f"sensor.{_doortag_entity}_rf_status"

    # Check entity creation
    assert hass.states.get(_doortag_entity_opening) is not None
    assert hass.states.get(_doortag_entity_battery) is not None
    # Check non-creation of other entities
    assert hass.states.get(_doortag_entity_reachability) is None
    assert hass.states.get(_doortag_entity_rf_status) is None
    # Check initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"


async def test_camera_disconnects_doortag(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test camera disconnection that disconnects doortag too."""
    fake_post_hits = 0

    async def fake_post(*args: Any, **kwargs: Any):
        """Fake error during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, **kwargs)

    with (
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
        patch(
            "homeassistant.components.netatmo.data_handler.PLATFORMS",
            ["camera", "binary_sensor", "sensor"],
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook_generate_url",
        ) as mock_webhook,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        mock_webhook.return_value = "https://example.com"
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake webhook activation
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)
    await hass.async_block_till_done()

    # Define the mock home_id, camera_id and doortag_id for the test
    _home_id = "91763b24c43d3e344f424e8b"
    _camera_id_indoor = "12:34:56:00:f1:62"
    _camera_entity_indoor = "camera.hall"
    _doortag_entity_id = "12:34:56:00:86:99"
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_reachability = f"binary_sensor.{_doortag_entity}_reachability"
    _doortag_entity_battery = f"sensor.{_doortag_entity}_battery"
    _doortag_entity_rf_status = f"sensor.{_doortag_entity}_rf_status"

    # Check entity creation
    assert hass.states.get(_doortag_entity_opening) is not None
    assert hass.states.get(_doortag_entity_battery) is not None
    # Check non-creation of other entities
    assert hass.states.get(_doortag_entity_reachability) is None
    assert hass.states.get(_doortag_entity_rf_status) is None
    # Check initial state - yet not loaded from fixtures
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"

    # Fake camera connection
    response = {
        "user_id": "1234567890",
        "event_type": "connection",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-connection",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(_camera_entity_indoor).state == "streaming"

    # Fake module reconnect
    response = {
        "user_id": "1234567890",
        "event_type": "module_connect",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-module_connect",
        "module_id": _doortag_entity_id,
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    # Check if became available (this indicated as unknown state, not as unavailable)
    assert hass.states.get(_doortag_entity_opening).state == "unknown"
    assert hass.states.get(_doortag_entity_battery).state == "75"

    # Fake camera disconnection that should disconnect doortag too
    response = {
        "user_id": "1234567890",
        "event_type": "disconnection",
        "event_id": "1234567890",
        "camera_id": _camera_id_indoor,
        "device_id": _camera_id_indoor,
        "home_id": _home_id,
        "push_type": "NACamera-disconnection",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert hass.states.get(_camera_entity_indoor).state == "idle"
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    assert hass.states.get(_doortag_entity_battery).state == "unavailable"
