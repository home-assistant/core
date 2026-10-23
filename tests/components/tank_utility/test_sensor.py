"""Tests for the Tank Utility sensor platform."""

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.tank_utility.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_ATTRS,
)
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import DEVICE_DATA, MOCK_DEVICE_ID, TEST_EMAIL, TEST_PASSWORD

YAML_CONFIG = {
    "sensor": {
        "platform": "tank_utility",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }
}


def _mock_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Create a mock HTTPError with a response."""
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


@pytest.mark.usefixtures("mock_get_data")
async def test_sensor_setup_and_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of Tank Utility sensor entity and attributes."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.my_propane_tank"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "78.4"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["state_class"] is SensorStateClass.MEASUREMENT

    for attr in SENSOR_ATTRS:
        assert attr in state.attributes
    assert state.attributes["capacity"] == 500
    assert state.attributes["fuelType"] == "propane"

    # Entity registry checks
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == f"{MOCK_DEVICE_ID}_tank"

    # Device registry checks
    assert entry.device_id is not None
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert (DOMAIN, MOCK_DEVICE_ID) in device.identifiers
    assert device.name == "My Propane Tank"
    assert device.manufacturer == "Tank Utility"
    assert device.model == "Propane Monitor"
    assert device.configuration_url == "https://data.tankutility.com"


@pytest.mark.usefixtures("mock_get_data")
async def test_sensor_polling_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor value updates via coordinator periodic polling."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.my_propane_tank"
    assert hass.states.get(entity_id).state == "78.4"

    updated_device = dict(DEVICE_DATA)
    updated_device["lastReading"] = dict(DEVICE_DATA["lastReading"])
    updated_device["lastReading"]["tank"] = 65.23
    mock_get_data.return_value = {MOCK_DEVICE_ID: updated_device}

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # Critical: wait_background_tasks=True ensures polling task completes before assertions
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "65.2"


@pytest.mark.usefixtures("mock_get_data")
async def test_sensor_dynamic_device_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test discovery of a new device during a coordinator refresh."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_propane_tank") is not None
    assert hass.states.get("sensor.tank_utility_device_2") is None

    device_2_data = {
        "name": "",
        "address": "456 Oak St",
        "capacity": 250,
        "fuelType": "propane",
        "orientation": "vertical",
        "status": "ok",
        "lastReading": {
            "tank": 42.0,
            "time": 1600000000,
            "time_iso": "2020-09-13T12:00:00Z",
        },
    }
    mock_get_data.return_value = {
        MOCK_DEVICE_ID: dict(DEVICE_DATA),
        "device_2": device_2_data,
    }

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_2 = hass.states.get("sensor.tank_utility_device_2")
    assert state_2 is not None
    assert state_2.state == "42.0"


@pytest.mark.usefixtures("mock_get_data")
async def test_sensor_none_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
) -> None:
    """Test sensor state when reading has no tank percentage."""
    no_reading_data = dict(DEVICE_DATA)
    no_reading_data["lastReading"] = {}
    mock_get_data.return_value = {MOCK_DEVICE_ID: no_reading_data}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_propane_tank")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_get_data")
async def test_sensor_device_removal_and_reappearance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor availability when a device disappears and reappears."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.my_propane_tank"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "78.4"

    # Device disappears from coordinator data on next refresh
    mock_get_data.return_value = {}
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Device reappears on subsequent refresh
    mock_get_data.return_value = {MOCK_DEVICE_ID: dict(DEVICE_DATA)}
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "78.4"


@pytest.mark.usefixtures("mock_get_token", "mock_get_data")
async def test_yaml_import_success(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing configuration from YAML creates an entry and deprecation issue."""
    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    # Verify deprecation issue was created
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


@pytest.mark.usefixtures("mock_get_token")
async def test_yaml_import_device_selection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test YAML import fetches selected tanks, skips missing 404 tanks, and propagates other errors."""
    should_fail = False

    def fake_get_device_data(token: str, dev_id: str, **kwargs: Any) -> dict[str, Any]:
        if should_fail:
            raise _mock_http_error(requests.codes.internal_server_error)
        if dev_id == MOCK_DEVICE_ID:
            return dict(DEVICE_DATA)
        raise _mock_http_error(requests.codes.not_found)

    yaml_with_devices = {
        "sensor": {
            "platform": "tank_utility",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "devices": [MOCK_DEVICE_ID, "missing_device"],
        }
    }

    with (
        patch(
            "homeassistant.components.tank_utility.coordinator.auth.get_token",
            return_value="mock_token",
        ),
        patch(
            "homeassistant.components.tank_utility.coordinator.device.get_device_data",
            side_effect=fake_get_device_data,
        ) as mock_device_data,
    ):
        assert await async_setup_component(hass, "sensor", yaml_with_devices)
        await hass.async_block_till_done()

        assert mock_device_data.call_count == 2
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].data == {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            "devices": [MOCK_DEVICE_ID, "missing_device"],
        }

        state = hass.states.get("sensor.my_propane_tank")
        assert state is not None
        assert state.state == "78.4"
        assert hass.states.get("sensor.tank_utility_missing_device") is None

        should_fail = True
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("sensor.my_propane_tank")
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_get_token")
async def test_yaml_import_multiple_blocks_merge_devices(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test multiple YAML blocks for the same account merge device selections."""
    device_2_data: dict[str, Any] = {
        "device": {
            "name": "Second Tank",
            "address": "456 Other St",
            "capacity": 250,
            "fuelType": "propane",
            "orientation": "vertical",
        },
        "status": "ok",
        "lastReading": {
            "tank": 42.0,
            "time": 1600000000,
            "time_iso": "2020-09-13T12:00:00Z",
        },
    }
    device_3_data: dict[str, Any] = {
        "device": {
            "name": "Third Tank",
            "address": "789 Extra Rd",
            "capacity": 500,
            "fuelType": "propane",
            "orientation": "horizontal",
        },
        "status": "ok",
        "lastReading": {
            "tank": 88.0,
            "time": 1600000000,
            "time_iso": "2020-09-13T12:00:00Z",
        },
    }
    mock_get_data.return_value = {
        MOCK_DEVICE_ID: dict(DEVICE_DATA),
        "device_2": device_2_data,
        "device_3": device_3_data,
    }

    yaml_multiple_blocks = {
        "sensor": [
            {
                "platform": "tank_utility",
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "devices": [MOCK_DEVICE_ID],
            },
            {
                "platform": "tank_utility",
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "devices": ["device_2"],
            },
        ]
    }

    assert await async_setup_component(hass, "sensor", yaml_multiple_blocks)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        "devices": [MOCK_DEVICE_ID, "device_2"],
    }

    assert hass.states.get("sensor.my_propane_tank") is not None
    assert hass.states.get("sensor.second_tank") is not None
    assert hass.states.get("sensor.third_tank") is None


@pytest.mark.parametrize(
    "blocks",
    [
        pytest.param(
            [
                {
                    "platform": "tank_utility",
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "devices": [MOCK_DEVICE_ID],
                },
                {
                    "platform": "tank_utility",
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                },
            ],
            id="restricted_then_unrestricted",
        ),
        pytest.param(
            [
                {
                    "platform": "tank_utility",
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                },
                {
                    "platform": "tank_utility",
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "devices": [MOCK_DEVICE_ID],
                },
            ],
            id="unrestricted_then_restricted",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_token")
async def test_yaml_import_restricted_and_unrestricted_blocks(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
    blocks: list[dict[str, Any]],
) -> None:
    """Test unrestricted YAML block clears device filter regardless of block order."""
    device_2_data: dict[str, Any] = {
        "device": {
            "name": "Second Tank",
            "address": "456 Other St",
            "capacity": 250,
            "fuelType": "propane",
            "orientation": "vertical",
        },
        "status": "ok",
        "lastReading": {
            "tank": 42.0,
            "time": 1600000000,
            "time_iso": "2020-09-13T12:00:00Z",
        },
    }
    mock_get_data.return_value = {
        MOCK_DEVICE_ID: dict(DEVICE_DATA),
        "device_2": device_2_data,
    }

    assert await async_setup_component(hass, "sensor", {"sensor": blocks})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    assert hass.states.get("sensor.my_propane_tank") is not None
    assert hass.states.get("sensor.second_tank") is not None


@pytest.mark.usefixtures("mock_get_data")
async def test_yaml_import_concurrent_blocks_merge_devices(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test concurrent YAML imports merge device selections when first is in progress."""
    in_validation = threading.Event()
    release_validation = threading.Event()

    def slow_get_token(*args: Any, **kwargs: Any) -> str:
        in_validation.set()
        release_validation.wait(timeout=5)
        return "mock_token"

    mock_get_token.side_effect = slow_get_token

    task_1 = hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
                "devices": [MOCK_DEVICE_ID],
            },
        )
    )
    while not in_validation.is_set():
        await asyncio.sleep(0.005)

    result_2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            "devices": ["device_2"],
        },
    )
    assert result_2["type"] is FlowResultType.ABORT
    assert result_2["reason"] == "already_in_progress"

    release_validation.set()
    result_1 = await task_1

    assert result_1["type"] is FlowResultType.CREATE_ENTRY
    assert result_1["data"]["devices"] == [MOCK_DEVICE_ID, "device_2"]


@pytest.mark.usefixtures("mock_get_data")
async def test_yaml_import_concurrent_mixed_credentials(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test concurrent YAML imports succeed when first has stale password and second is valid."""
    in_validation = threading.Event()
    release_validation = threading.Event()

    def check_get_token(email: str, password: str, **kwargs: Any) -> str:
        if password == "stale_password":
            in_validation.set()
            release_validation.wait(timeout=5)
            raise _mock_http_error(requests.codes.unauthorized)
        return "mock_token"

    mock_get_token.side_effect = check_get_token

    task_1 = hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_EMAIL: TEST_EMAIL,
                CONF_PASSWORD: "stale_password",
                "devices": [MOCK_DEVICE_ID],
            },
        )
    )
    while not in_validation.is_set():
        await asyncio.sleep(0.005)

    result_2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            "devices": ["device_2"],
        },
    )
    assert result_2["type"] is FlowResultType.ABORT
    assert result_2["reason"] == "already_in_progress"

    release_validation.set()
    result_1 = await task_1

    assert result_1["type"] is FlowResultType.CREATE_ENTRY
    assert result_1["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        "devices": [MOCK_DEVICE_ID, "device_2"],
    }


@pytest.mark.usefixtures("mock_get_token", "mock_get_data")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import when entry already exists still creates deprecation issue."""
    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


@pytest.mark.usefixtures("mock_get_data")
async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import connection error creates specific repair issue."""
    mock_get_token.side_effect = requests.exceptions.ConnectTimeout

    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


@pytest.mark.usefixtures("mock_get_data")
async def test_yaml_import_invalid_auth(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import invalid auth creates specific repair issue."""
    mock_get_token.side_effect = _mock_http_error(requests.codes.unauthorized)

    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)

    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_auth"
    )
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_yaml_import_already_in_progress(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test YAML import already in progress creates no repair issue."""

    async def mock_async_init(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"type": FlowResultType.ABORT, "reason": "already_in_progress"}

    monkeypatch.setattr(hass.config_entries.flow, "async_init", mock_async_init)

    assert await async_setup_component(hass, "sensor", YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert not issue_registry.issues
