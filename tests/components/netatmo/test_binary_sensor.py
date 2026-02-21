"""Support for Netatmo binary sensors."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .common import (
    FAKE_WEBHOOK_ACTIVATION,
    fake_post_request,
    simulate_webhook,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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


@pytest.mark.parametrize(
    ("doortag_status", "expected"),
    [
        ("no_news", "unknown"),
        ("calibrating", "unknown"),
        ("undefined", "unknown"),
        ("closed", "off"),
        ("open", "on"),
        ("calibration_failed", "unknown"),
        ("maintenance", "unknown"),
        ("weak_signal", "unknown"),
        ("invalid_value", "unknown"),
    ],
)
async def test_doortag_opening_status_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    freezer: FrozenDateTimeFactory,
    doortag_status: str,
    expected: str,
) -> None:
    """Test doortag opening status changes."""
    fake_post_hits = 0
    # Repeatedly used variables for the test and initial value from fixture
    # Use nonexistent ID to prevent matching during initial setup
    doortag_entity_id = "aa:bb:cc:dd:ee:ff"
    doortag_connectivity = False
    doortag_opening = "no_news"
    doortag_timestamp = None

    def tag_modifier(payload):
        """This function will be called by common.py during ANY homestatus call."""
        nonlocal doortag_connectivity, doortag_opening, doortag_timestamp

        if doortag_timestamp is not None:
            payload["time_server"] = doortag_timestamp
        body = payload.get("body", {})

        # Handle both structures: {"home": {...}} AND {"homes": [{...}]}
        homes_to_check = []
        if "home" in body and isinstance(body["home"], dict):
            homes_to_check.append(body["home"])
        elif "homes" in body and isinstance(body["homes"], list):
            homes_to_check.extend(body["homes"])

        for home_data in homes_to_check:
            # Safety check: ensure home_data is actually a dictionary
            if not isinstance(home_data, dict):
                continue

            modules = home_data.get("modules", [])
            for module in modules:
                if isinstance(module, dict) and module.get("id") == doortag_entity_id:
                    module["reachable"] = doortag_connectivity
                    module["status"] = doortag_opening
                    if doortag_timestamp is not None:
                        module["last_seen"] = doortag_timestamp
                    break

    async def fake_tag_post(*args, **kwargs):
        """Fake tag status during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, msg_callback=tag_modifier, **kwargs)

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
        mock_auth.return_value.async_post_api_request.side_effect = fake_tag_post
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

    # Check connectivity creation
    assert hass.states.get(_doortag_entity_connectivity) is not None
    # Check opening creation
    assert hass.states.get(_doortag_entity_opening) is not None

    # Check connectivity initial state
    assert hass.states.get(_doortag_entity_connectivity).state == "off"
    # Check opening initial state
    assert hass.states.get(_doortag_entity_opening).state == "unavailable"

    # Trigger some polling cycle to let API throttling work
    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # Change mocked status
    doortag_entity_id = "12:34:56:00:86:99"
    doortag_connectivity = True
    doortag_opening = doortag_status
    doortag_timestamp = int(dt_util.utcnow().timestamp())

    # Trigger some polling cycle to let status change be picked up

    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # Check connectivity mocked state
    assert hass.states.get(_doortag_entity_connectivity).state == "on"
    # Check opening mocked state
    assert hass.states.get(_doortag_entity_opening).state == expected


@pytest.mark.parametrize(
    ("doortag_category", "expected_key", "expected_class"),
    [
        ("door", "door", BinarySensorDeviceClass.DOOR),
        ("furniture", "furniture", BinarySensorDeviceClass.OPENING),
        ("garage", "garage_door", BinarySensorDeviceClass.GARAGE_DOOR),
        ("gate", "gate", BinarySensorDeviceClass.OPENING),
        ("other", "opening", BinarySensorDeviceClass.OPENING),
        ("window", "window", BinarySensorDeviceClass.WINDOW),
        ("invalid_value", "opening", BinarySensorDeviceClass.OPENING),
    ],
)
async def test_doortag_opening_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    doortag_category: str,
    expected_key: str,
    expected_class: BinarySensorDeviceClass,
) -> None:
    """Test doortag opening status changes."""
    fake_post_hits = 0
    # Repeatedly used variables for the test and initial value from fixture
    doortag_entity_id = "12:34:56:00:86:99"
    doortag_connectivity = False
    doortag_opening = "no_news"

    def tag_modifier(payload):
        """This function will be called by common.py during ANY homestatus call."""
        nonlocal doortag_connectivity, doortag_opening
        payload["time_server"] = int(dt_util.utcnow().timestamp())
        body = payload.get("body", {})

        # Handle both structures: {"home": {...}} AND {"homes": [{...}]}
        homes_to_check = []
        if "home" in body and isinstance(body["home"], dict):
            homes_to_check.append(body["home"])
        elif "homes" in body and isinstance(body["homes"], list):
            homes_to_check.extend(body["homes"])

        for home_data in homes_to_check:
            # Safety check: ensure home_data is actually a dictionary
            if not isinstance(home_data, dict):
                continue

            modules = home_data.get("modules", [])
            for module in modules:
                if isinstance(module, dict) and module.get("id") == doortag_entity_id:
                    module["category"] = doortag_category
                    break

    async def fake_tag_post(*args, **kwargs):
        """Fake tag status during requesting backend data."""
        nonlocal fake_post_hits
        fake_post_hits += 1
        return await fake_post_request(hass, *args, msg_callback=tag_modifier, **kwargs)

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
        mock_auth.return_value.async_post_api_request.side_effect = fake_tag_post
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
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_{expected_key}"

    # Check opening creation with right key
    assert hass.states.get(_doortag_entity_opening) is not None
    # Check opening device class
    assert (
        hass.states.get(_doortag_entity_opening).attributes.get("device_class")
        == expected_class.value
    )
    # Check opening device name
    assert (
        hass.states.get(_doortag_entity_opening).attributes.get("friendly_name")
        == _doortag_entity.replace("_", " ").title()
        + " "
        + expected_key.replace("_", " ").capitalize()
    )
