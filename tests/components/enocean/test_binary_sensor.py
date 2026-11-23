"""Tests for the EnOcean binary sensor platform."""

from types import MappingProxyType
from typing import Any
from unittest.mock import Mock, patch

from enocean_async import EURID
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.enocean import DOMAIN
from homeassistant.components.enocean.const import (
    CONF_DEVICE_TYPE_ID,
    DEVICE_TYPE_ROCKER_SWITCH,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_DEVICE, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import TelegramReceiver

DEVICE_ID = [0xDE, 0xAD, 0xBE, 0xEF]
DEVICE_ADDRESS = "DE:AD:BE:EF"
LEGACY_UNIQUE_ID = "3735928559-None"


def _yaml_config(**options: Any) -> dict[str, Any]:
    """Return the YAML configuration of one EnOcean binary sensor."""
    return {
        BINARY_SENSOR_DOMAIN: [
            {"platform": DOMAIN, "id": DEVICE_ID, "name": "button", **options}
        ]
    }


def _stored_device(device_type_id: str, title: str = "button") -> ConfigSubentryData:
    """Return a device as it is stored in the config entry."""
    return ConfigSubentryData(
        data={CONF_ID: DEVICE_ADDRESS, CONF_DEVICE_TYPE_ID: device_type_id},
        subentry_type=SUBENTRY_TYPE_DEVICE,
        title=title,
        unique_id=DEVICE_ADDRESS,
    )


def _config_entry(*devices: ConfigSubentryData) -> MockConfigEntry:
    """Return a config entry with stored devices."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyUSB0"}, subentries_data=devices
    )


@pytest.mark.parametrize(
    ("data", "status", "expected"),
    [
        pytest.param(
            b"\x70", 0x30, {"pushed": 1, "which": 0, "onoff": 0}, id="pressed"
        ),
        pytest.param(
            b"\x10", 0x30, {"pushed": 1, "which": 1, "onoff": 1}, id="other_button"
        ),
        pytest.param(
            b"\x00", 0x20, {"pushed": 0, "which": -1, "onoff": -1}, id="released"
        ),
    ],
)
async def test_button_event(
    hass: HomeAssistant,
    receive_telegram: TelegramReceiver,
    data: bytes,
    status: int,
    expected: dict[str, int],
) -> None:
    """Test that a rocker switch telegram fires a button event."""
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: [
                {"platform": DOMAIN, "id": DEVICE_ID, "name": "button"}
            ]
        },
    )
    await hass.async_block_till_done()
    events = async_capture_events(hass, "button_pressed")

    await receive_telegram(
        ERP1Telegram(RORG.RORG_RPS, data, EURID("DE:AD:BE:EF"), status)
    )

    assert len(events) == 1
    assert events[0].data == {"id": DEVICE_ID, **expected}


@pytest.mark.parametrize(
    ("yaml_options", "expected_unique_id"),
    [
        pytest.param({}, LEGACY_UNIQUE_ID, id="without_device_class"),
        pytest.param(
            {"device_class": "door"}, "3735928559-door", id="with_device_class"
        ),
    ],
)
@pytest.mark.usefixtures("mock_gateway")
async def test_yaml_binary_sensor_is_imported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    yaml_options: dict[str, str],
    expected_unique_id: str,
) -> None:
    """Test that a YAML binary sensor becomes a device of the config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass, BINARY_SENSOR_DOMAIN, _yaml_config(**yaml_options)
    )
    await hass.async_block_till_done()

    (subentry,) = mock_config_entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.title == "button"
    assert subentry.unique_id == DEVICE_ADDRESS
    assert subentry.data == {
        CONF_ID: DEVICE_ADDRESS,
        CONF_DEVICE_TYPE_ID: DEVICE_TYPE_ROCKER_SWITCH,
        **yaml_options,
    }

    entity = entity_registry.async_get("binary_sensor.button")
    assert entity is not None
    assert entity.unique_id == expected_unique_id
    assert entity.config_entry_id == mock_config_entry.entry_id
    assert entity.config_subentry_id == subentry.subentry_id
    state = hass.states.get("binary_sensor.button")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == yaml_options.get("device_class")

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")


@pytest.mark.usefixtures("mock_gateway")
async def test_yaml_import_keeps_the_existing_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entity of a YAML binary sensor keeps its entity ID."""
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        LEGACY_UNIQUE_ID,
        suggested_object_id="hallway_switch",
    )
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, _yaml_config())
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert [entity.entity_id for entity in entities] == ["binary_sensor.hallway_switch"]
    assert hass.states.get("binary_sensor.hallway_switch") is not None
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1


@pytest.mark.usefixtures("mock_gateway")
async def test_yaml_import_is_not_repeated(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that a device is left as it is when its YAML is still there."""
    config_entry = _config_entry(_stored_device(DEVICE_TYPE_ROCKER_SWITCH, "renamed"))
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, _yaml_config())
    await hass.async_block_till_done()

    (subentry,) = config_entry.subentries.values()
    assert subentry.title == "renamed"
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")


async def test_yaml_import_without_gateway(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that the user is told when there is no gateway to import devices into."""
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, _yaml_config())
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_no_gateway_binary_sensor"
    )
    assert not issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")


@pytest.mark.usefixtures("mock_gateway")
async def test_yaml_import_with_invalid_id(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a YAML binary sensor whose ID no device can have is not imported."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass, BINARY_SENSOR_DOMAIN, _yaml_config(id=[0x01, 0x02, 0x03])
    )
    await hass.async_block_till_done()

    assert not mock_config_entry.subentries
    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_id_binary_sensor_button"
    )


@pytest.mark.parametrize(
    ("device_type_id", "expected_entity_ids"),
    [
        pytest.param(
            DEVICE_TYPE_ROCKER_SWITCH, ["binary_sensor.button"], id="rocker_switch"
        ),
        pytest.param("EEP/A5-02-05", [], id="other_device_type"),
    ],
)
async def test_binary_sensor_of_stored_device(
    hass: HomeAssistant,
    mock_gateway: Mock,
    device_type_id: str,
    expected_entity_ids: list[str],
) -> None:
    """Test that a stored rocker switch gets a binary sensor without any YAML."""
    config_entry = _config_entry(_stored_device(device_type_id))
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == expected_entity_ids

    events = async_capture_events(hass, "button_pressed")
    mock_gateway.add_erp1_received_callback.call_args.args[0](
        ERP1Telegram(RORG.RORG_RPS, b"\x70", EURID(DEVICE_ADDRESS), 0x30)
    )
    await hass.async_block_till_done()

    assert len(events) == len(expected_entity_ids)


@pytest.mark.parametrize("count", [1, 30])
async def test_yaml_import_does_not_restart_the_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: Mock,
    count: int,
) -> None:
    """Test that imported devices get their entities without reloading the entry."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: [
                {"platform": DOMAIN, "id": [0xDE, 0xAD, 0xBE, n], "name": f"button {n}"}
                for n in range(count)
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(mock_config_entry.subentries) == count
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == count
    assert mock_gateway.start.call_count == 1
    mock_gateway.stop.assert_not_called()


async def test_removing_a_device_removes_its_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_gateway: Mock
) -> None:
    """Test that the entity of a removed device goes without reloading the entry."""
    config_entry = _config_entry(_stored_device(DEVICE_TYPE_ROCKER_SWITCH))
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.button") is not None

    (subentry_id,) = config_entry.subentries
    hass.config_entries.async_remove_subentry(config_entry, subentry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.button") is None
    assert entity_registry.async_get("binary_sensor.button") is None
    assert mock_gateway.start.call_count == 1
    mock_gateway.stop.assert_not_called()


async def test_yaml_import_skips_an_ignored_gateway(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that devices are not stored on a gateway the user chose to ignore."""
    ignored_entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE)
    ignored_entry.add_to_hass(hass)

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, _yaml_config())
    await hass.async_block_till_done()

    assert not ignored_entry.subentries
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_no_gateway_binary_sensor"
    )
    assert not issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")


@pytest.mark.usefixtures("mock_gateway")
async def test_yaml_import_of_two_sensors_with_the_same_id(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the user is told when a second sensor of a device is not imported."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: [
                {"platform": DOMAIN, "id": DEVICE_ID, "name": "button"},
                {
                    "platform": DOMAIN,
                    "id": DEVICE_ID,
                    "name": "door",
                    "device_class": "door",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    (subentry,) = mock_config_entry.subentries.values()
    assert subentry.title == "button"
    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == [
        "binary_sensor.button"
    ]
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_already_configured_binary_sensor_door"
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "platform": "binary_sensor",
        "name": "door",
        "id": DEVICE_ADDRESS,
    }
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_binary_sensor")


@pytest.mark.usefixtures("mock_gateway")
async def test_device_added_while_the_platforms_are_set_up(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a device added right after the platform read the devices is not missed."""
    mock_config_entry.add_to_hass(hass)
    forward_entry_setups = hass.config_entries.async_forward_entry_setups

    async def forward_then_add_device(*args: Any) -> None:
        await forward_entry_setups(*args)
        hass.config_entries.async_add_subentry(
            mock_config_entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {
                        CONF_ID: DEVICE_ADDRESS,
                        CONF_DEVICE_TYPE_ID: DEVICE_TYPE_ROCKER_SWITCH,
                    }
                ),
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="button",
                unique_id=DEVICE_ADDRESS,
            ),
        )

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=forward_then_add_device,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == [
        "binary_sensor.button"
    ]
