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
        await hass.async_block_till_done(wait_background_tasks=True)

    # Change mocked status
    doortag_entity_id = "12:34:56:00:86:99"
    doortag_connectivity = True
    doortag_opening = doortag_status
    doortag_timestamp = int(dt_util.utcnow().timestamp())

    # Trigger some polling cycle to let status change be picked up

    for _ in range(11):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

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


@pytest.mark.parametrize(
    ("netatmo_event", "expected"),
    [
        ("tag_big_move", "on"),
        ("tag_small_move", "on"),
        ("invalid_move", "off"),
    ],
)
async def test_doortag_opening_webhook(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    freezer: FrozenDateTimeFactory,
    netatmo_event: str,
    expected: str,
) -> None:
    """Test doortag opening status changes on webhook."""
    fake_post_hits = 0

    # ID-s to use
    doortag_id = "12:34:56:00:86:99"
    camera_id = "12:34:56:00:f1:62"

    # Repeatedly used variables for the test and initial value from fixture
    doortag_entity_id = doortag_id
    doortag_connectivity = True
    doortag_opening = "closed"
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

    # Change mocked data to prevent further matching during the test
    doortag_entity_id = "aa:bb:cc:dd:ee:ff"

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
    assert hass.states.get(_doortag_entity_connectivity).state == "on"
    # Check opening initial state
    assert hass.states.get(_doortag_entity_opening).state == "off"

    # Note: module event is reported by the gateway, so push_type is
    # related to the gateway (camera) and not the module (doortag)
    response = {
        "event_type": netatmo_event,
        "device_id": doortag_id,
        "module_id": doortag_id,
        "camera_id": camera_id,
        "event_id": "646227f1dc0dfa000ec5f350",
        "push_type": f"NACamera-{netatmo_event}",
    }
    await simulate_webhook(hass, webhook_id, response)

    # Check connectivity state after webhook event
    assert hass.states.get(_doortag_entity_connectivity).state == "on"
    # Check opening state after webhook event
    assert hass.states.get(_doortag_entity_opening).state == expected


@pytest.mark.parametrize(
    ("doortag_id", "home_id"),
    [
        # From the fixture the following combination is the only right one
        # doortag_id, home_id
        # "12:34:56:00:86:99", "91763b24c43d3e344f424e8b"
        # will test all the wrong combinations to be sure that the validation works
        # Test1: wrong home_id
        ("12:34:56:00:86:99", "91763b24c43d3e344f424e80"),
        # Test2: wrong doortag_id (id of NACamera)
        ("12:34:56:00:f1:62", "91763b24c43d3e344f424e8b"),
        # Test3: missing doortag_id
        (None, "91763b24c43d3e344f424e8b"),
        # Note: missing home_id is not possible as it's mandatory in the webhook payload
        # (by experience it is filled by some logic even if missing)
    ],
)
async def test_opening_webhook_consistency(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    doortag_id: str | None,
    home_id: str,
) -> None:
    """Test webhook event on doortag big_move."""
    fake_post_hits = 0

    # ID-s to use
    camera_id = "12:34:56:00:f1:62"

    # Repeatedly used variables for the test and initial value from fixture
    doortag_entity_id = "12:34:56:00:86:99"
    doortag_connectivity = True
    doortag_opening = "closed"
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

    # Change mocked data to prevent further matching during the test
    doortag_entity_id = "aa:bb:cc:dd:ee:ff"

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Define the variables for the test
    _doortag_entity = "window_hall"
    _doortag_entity_opening = f"binary_sensor.{_doortag_entity}_window"
    _doortag_entity_connectivity = f"binary_sensor.{_doortag_entity}_connectivity"

    # Check connectivity creation
    assert hass.states.get(_doortag_entity_connectivity) is not None
    # Check opening creation
    assert hass.states.get(_doortag_entity_opening) is not None

    # Check connectivity initial state
    assert hass.states.get(_doortag_entity_connectivity).state == "on"
    # Check opening initial state
    assert hass.states.get(_doortag_entity_opening).state == "off"

    # Fake webhook activation
    response = {
        "push_type": "webhook_activation",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    assert fake_post_hits == 8

    calls = fake_post_hits

    # Fake camera reconnect
    if doortag_id is None:
        response = {
            "event_type": "tag_big_move",
            "home_id": home_id,
            "device_id": camera_id,
            "push_type": "NACamera-tag_big_move",
        }
    else:
        response = {
            "event_type": "tag_big_move",
            "home_id": home_id,
            "module_id": doortag_id,
            "device_id": camera_id,
            "camera_id": camera_id,
            "push_type": "NACamera-tag_big_move",
        }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=60),
    )
    await hass.async_block_till_done()
    assert fake_post_hits >= calls

    assert hass.states.get(_doortag_entity_opening).state == "off"
