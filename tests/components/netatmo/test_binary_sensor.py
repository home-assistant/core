"""Support for Netatmo binary sensors."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.netatmo import binary_sensor
from homeassistant.const import CONF_WEBHOOK_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    fake_post_request,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry


def get_netatmo_entity_instance(
    hass: HomeAssistant, config_entry: MockConfigEntry, entity_id: str
) -> object | None:
    """Helper to find the specific entity instance."""
    BINARY_SENSOR_DOMAIN = "binary_sensor"

    # 1. Get the EntityComponent object for the binary_sensor domain
    component = hass.data.get(BINARY_SENSOR_DOMAIN)

    if not component:
        raise ValueError(f"Component not found for {BINARY_SENSOR_DOMAIN}")

    platform_key = config_entry.entry_id

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
        ("invalid_value", BinarySensorDeviceClass.OPENING),
    ],
)
async def test_process_opening_category2class(
    category: str, expected: BinarySensorDeviceClass | None
) -> None:
    """Test opening category translation to class."""
    assert binary_sensor.process_opening_category_string2class(category) == expected


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("door", "door"),
        ("window", "window"),
        ("garage", "garage"),
        ("gate", "gate"),
        ("furniture", "furniture"),
        ("other", "opening_sensor"),
        ("invalid_value", "opening_sensor"),
        (None, "opening_sensor"),
    ],
)
async def test_process_opening_category2key(
    category: str | None, expected: str
) -> None:
    """Test opening category translation to key."""
    assert binary_sensor.process_opening_category_string2key(category) == expected


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
            ["camera", "binary_sensor"],
        ),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
            return_value=AsyncMock(),
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

    # Define variables for the test
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_connectivity = f"binary_sensor.{_doortag_entity}_connectivity"

    # Check opening creation
    assert hass.states.get(_doortag_entity_opening) is not None
    # Check connectivity creation
    assert hass.states.get(_doortag_entity_connectivity) is not None

    # Check opening initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    # Check connectivity initial state
    assert hass.states.get(_doortag_entity_connectivity).state == "off"


async def test_doortag_opening_status_change(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test doortag opening status changes."""
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
            ["camera", "binary_sensor"],
        ),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
            return_value=AsyncMock(),
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

    # Define the variables for the test
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_connectivity = f"binary_sensor.{_doortag_entity}_connectivity"

    # Check opening creation
    assert hass.states.get(_doortag_entity_opening) is not None
    # Check connectivity creation
    assert hass.states.get(_doortag_entity_connectivity) is not None

    # Check opening initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"
    # Check connectivity initial state
    assert hass.states.get(_doortag_entity_connectivity).state == "off"

    # Initial state should be unavailable, need to connect first
    hass.states.async_set(_doortag_entity_connectivity, "on")
    assert hass.states.get(_doortag_entity_connectivity).state == "on"

    # Check if became available (this indicated as unknown state, not as unavailable)
    # NEED TO BE CORRECTED IN THE FUTURE
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"

    # Set state to closed
    await set_netatmo_entity_state(
        hass, config_entry, _doortag_entity_opening, STATE_OFF
    )
    hass.states.async_set(_doortag_entity_opening, STATE_OFF)
    await hass.async_block_till_done()

    # State should be closed
    assert hass.states.get(_doortag_entity_opening).state == "off"

    # Set state to open
    await set_netatmo_entity_state(
        hass, config_entry, _doortag_entity_opening, STATE_ON
    )
    hass.states.async_set(_doortag_entity_opening, STATE_ON)
    await hass.async_block_till_done()

    # State should change to open (as it was closed before)
    assert hass.states.get(_doortag_entity_opening).state == "on"
