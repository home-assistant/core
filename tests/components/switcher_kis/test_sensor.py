"""Test the Switcher Sensor Platform."""

from datetime import timedelta

from aioswitcher.device import SwitcherBase
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.switcher_kis.const import DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    Platform,
    UnitOfTime,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from . import init_integration
from .consts import (
    DUMMY_AUTO_SHUT_DOWN,
    DUMMY_HEATER_DEVICE,
    DUMMY_PLUG_DEVICE,
    DUMMY_REMAINING_TIME,
    DUMMY_SWITCHER_SENSORS_DEVICES,
    DUMMY_THERMOSTAT_DEVICE,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
    DUMMY_WATER_HEATER_DEVICE,
)

DEVICE_SENSORS_TUPLE = (
    (
        DUMMY_PLUG_DEVICE,
        [
            ("power", "power_consumption"),
            ("current", "electric_current"),
        ],
    ),
    (
        DUMMY_WATER_HEATER_DEVICE,
        [
            ("power", "power_consumption"),
            ("current", "electric_current"),
        ],
    ),
    (
        DUMMY_THERMOSTAT_DEVICE,
        [
            ("temperature", "temperature"),
        ],
    ),
)

DEVICE_SENSORS_TOKEN_NEEDED_TUPLE = (
    (
        DUMMY_HEATER_DEVICE,
        [
            ("power", "power_consumption"),
            ("current", "electric_current"),
        ],
    ),
)


@pytest.mark.parametrize("mock_bridge", [DUMMY_SWITCHER_SENSORS_DEVICES], indirect=True)
async def test_sensor_platform(hass: HomeAssistant, mock_bridge) -> None:
    """Test sensor platform."""
    entry = await init_integration(hass)
    assert mock_bridge

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 3

    for device, sensors in DEVICE_SENSORS_TUPLE:
        for sensor, field in sensors:
            entity_id = f"sensor.{slugify(device.name)}_{sensor}"
            state = hass.states.get(entity_id)
            assert state.state == str(getattr(device, field))


@pytest.mark.parametrize("mock_bridge", [[DUMMY_HEATER_DEVICE]], indirect=True)
async def test_sensor_platform_token_needed(hass: HomeAssistant, mock_bridge) -> None:
    """Test sensor platform."""
    entry = await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    assert mock_bridge.is_running is True
    assert len(entry.runtime_data) == 1

    for device, sensors in DEVICE_SENSORS_TOKEN_NEEDED_TUPLE:
        for sensor, field in sensors:
            entity_id = f"sensor.{slugify(device.name)}_{sensor}"
            state = hass.states.get(entity_id)
            assert state.state == str(getattr(device, field))


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_sensor_update(
    hass: HomeAssistant, mock_bridge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sensor update."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    field = "power_consumption"
    entity_id = f"sensor.{slugify(device.name)}_power"

    state = hass.states.get(entity_id)
    assert state.state == str(getattr(device, field))

    monkeypatch.setattr(device, field, 1431)
    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1431"


@pytest.mark.parametrize("mock_bridge", [[DUMMY_HEATER_DEVICE]], indirect=True)
async def test_sensor_update_token_needed(
    hass: HomeAssistant, mock_bridge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sensor update."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    device = DUMMY_HEATER_DEVICE
    field = "power_consumption"
    entity_id = f"sensor.{slugify(device.name)}_power"

    state = hass.states.get(entity_id)
    assert state.state == str(getattr(device, field))

    monkeypatch.setattr(device, field, 1431)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1431"


@pytest.mark.parametrize(
    ("mock_bridge", "device", "username", "token"),
    [
        pytest.param(
            [DUMMY_WATER_HEATER_DEVICE],
            DUMMY_WATER_HEATER_DEVICE,
            None,
            None,
            id="water_heater",
        ),
        pytest.param(
            [DUMMY_HEATER_DEVICE], DUMMY_HEATER_DEVICE, USERNAME, TOKEN, id="heater"
        ),
    ],
    indirect=["mock_bridge"],
)
@pytest.mark.usefixtures("mock_bridge", "entity_registry_enabled_by_default")
async def test_time_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: SwitcherBase,
    username: str | None,
    token: str | None,
) -> None:
    """Test the shutdown time and auto-off sensors."""
    await init_integration(hass, username, token)

    state = hass.states.get(f"sensor.{slugify(device.name)}_shutdown_time")
    assert state.state == (
        dt_util.utcnow() + timedelta(hours=1, minutes=29, seconds=32)
    ).isoformat(timespec="seconds")

    state = hass.states.get(f"sensor.{slugify(device.name)}_auto_off")
    assert state.state == "120.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.MINUTES


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_shutdown_time_update(
    hass: HomeAssistant,
    mock_bridge,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the shutdown time sensor ignores jitter and resets when the timer ends."""
    await init_integration(hass)

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"sensor.{slugify(device.name)}_shutdown_time"
    shutdown_time = (
        dt_util.utcnow() + timedelta(hours=1, minutes=29, seconds=32)
    ).isoformat(timespec="seconds")
    assert hass.states.get(entity_id).state == shutdown_time

    # The next broadcast, 4 seconds later, is within the ignored variance.
    freezer.tick(timedelta(seconds=4))
    monkeypatch.setattr(device, "remaining_time", "01:29:27")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == shutdown_time

    monkeypatch.setattr(device, "remaining_time", "02:00:00")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == (
        dt_util.utcnow() + timedelta(hours=2)
    ).isoformat(timespec="seconds")

    monkeypatch.setattr(device, "remaining_time", "00:00:00")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # A new timer is not compared against the previous one.
    monkeypatch.setattr(device, "remaining_time", "01:59:50")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == (
        dt_util.utcnow() + timedelta(hours=1, minutes=59, seconds=50)
    ).isoformat(timespec="seconds")


DEPRECATED_SENSORS = [
    pytest.param(
        "remaining_time", "remaining_time", "remaining_time", id="remaining_time"
    ),
    pytest.param("auto_off_set", "auto_shutdown", "auto_shutdown", id="auto_shutdown"),
]


def _create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Switcher config entry without setting it up."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    return entry


def _register_deprecated_sensor(
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    key: str,
    object_id: str,
    disabled_by: er.RegistryEntryDisabler | None = None,
) -> str:
    """Register a deprecated sensor of the water heater device."""
    device = DUMMY_WATER_HEATER_DEVICE
    return entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{device.device_id}-{device.mac_address}-{key}",
        config_entry=entry,
        suggested_object_id=f"{slugify(device.name)}_{object_id}",
        disabled_by=disabled_by,
    ).entity_id


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.parametrize(("key", "translation_key", "object_id"), DEPRECATED_SENSORS)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_not_created_for_new_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    key: str,
    translation_key: str,
    object_id: str,
) -> None:
    """Test deprecated sensors are not created on a fresh install."""
    await init_integration(hass)

    device = DUMMY_WATER_HEATER_DEVICE
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{device.device_id}-{device.mac_address}-{key}"
        )
        is None
    )
    assert not issue_registry.issues


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.parametrize(
    ("key", "translation_key", "object_id", "expected_state"),
    [
        pytest.param(
            "remaining_time",
            "remaining_time",
            "remaining_time",
            DUMMY_REMAINING_TIME,
            id="remaining_time",
        ),
        pytest.param(
            "auto_off_set",
            "auto_shutdown",
            "auto_shutdown",
            DUMMY_AUTO_SHUT_DOWN,
            id="auto_shutdown",
        ),
    ],
)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_existing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    key: str,
    translation_key: str,
    object_id: str,
    expected_state: str,
) -> None:
    """Test an existing deprecated sensor is kept and a repair issue is created."""
    entry = _create_entry(hass)
    entity_id = _register_deprecated_sensor(entity_registry, entry, key, object_id)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = DUMMY_WATER_HEATER_DEVICE
    assert hass.states.get(entity_id).state == expected_state
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_{translation_key}_{device.device_id}"
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_{translation_key}"
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.config_entry_id == entry.entry_id


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.parametrize(("key", "translation_key", "object_id"), DEPRECATED_SENSORS)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_used_in_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    key: str,
    translation_key: str,
    object_id: str,
) -> None:
    """Test the repair issue lists automations using a deprecated sensor."""
    entry = _create_entry(hass)
    entity_id = _register_deprecated_sensor(
        entity_registry,
        entry,
        key,
        object_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "id": "with_id",
                    "alias": "With id",
                    "trigger": {"platform": "state", "entity_id": entity_id},
                    "action": {"action": "notify.notify", "data": {}},
                },
                {
                    "alias": "Without id",
                    "trigger": {"platform": "state", "entity_id": entity_id},
                    "action": {"action": "notify.notify", "data": {}},
                },
            ]
        },
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Still used by an automation, so the disabled sensor is kept.
    assert entity_registry.async_get(entity_id) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_{translation_key}_{DUMMY_WATER_HEATER_DEVICE.device_id}"
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_{translation_key}_scripts"
    assert issue.translation_placeholders["items"] == (
        "- [With id](/config/automation/edit/with_id)\n- `automation.without_id`"
    )


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.parametrize(("key", "translation_key", "object_id"), DEPRECATED_SENSORS)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_removed_when_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    key: str,
    translation_key: str,
    object_id: str,
) -> None:
    """Test a disabled, unused deprecated sensor is removed."""
    entry = _create_entry(hass)
    entity_id = _register_deprecated_sensor(
        entity_registry,
        entry,
        key,
        object_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
    assert not issue_registry.issues


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.parametrize(("key", "translation_key", "object_id"), DEPRECATED_SENSORS)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_check_deferred_until_started(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    key: str,
    translation_key: str,
    object_id: str,
) -> None:
    """Test the deprecation check waits for Home Assistant to start."""
    entry = _create_entry(hass)
    entity_id = _register_deprecated_sensor(
        entity_registry,
        entry,
        key,
        object_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    hass.set_state(CoreState.starting)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Automations may not be loaded yet, so nothing is removed during startup.
    assert entity_registry.async_get(entity_id) is not None

    await hass.async_start()
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
    assert not issue_registry.issues


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.usefixtures("mock_bridge")
async def test_deprecated_sensor_removed_during_startup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deferred check handles a sensor removed before startup finished."""
    entry = _create_entry(hass)
    entity_id = _register_deprecated_sensor(
        entity_registry, entry, "remaining_time", "remaining_time"
    )
    hass.set_state(CoreState.starting)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_registry.async_remove(entity_id)

    await hass.async_start()
    await hass.async_block_till_done()

    assert not issue_registry.issues


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_auto_off_invalid(
    hass: HomeAssistant, mock_bridge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the auto-off sensor with an unparsable value."""
    await init_integration(hass)

    device = DUMMY_WATER_HEATER_DEVICE
    monkeypatch.setattr(device, "auto_shutdown", "invalid")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{slugify(device.name)}_auto_off")
    assert state.state == STATE_UNKNOWN
