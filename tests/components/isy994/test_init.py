"""Test the Universal Devices ISY/IoX integration init."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

from pyisy.constants import (
    CMD_BACKLIGHT,
    CMD_ON,
    PROP_ON_LEVEL,
    PROP_RAMP_RATE,
    TAG_ENABLED,
)
from pyisy.helpers import EventEmitter, NodeProperty
from pyisy.variables import Variable
import pytest

from homeassistant.components.isy994.const import DOMAIN, EVENT_ISY994_CONTROL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from . import entity_listeners
from .conftest import MOCK_UUID as MOCK_ISY_UUID

from tests.common import MockConfigEntry, async_capture_events

MOCK_UUID = "ce:fb:72:31:b7:b9"


async def test_migrate_minor_version_drops_tls(
    hass: HomeAssistant,
) -> None:
    """Test minor migration drops legacy "tls" and seeds verify_ssl."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            "tls": 1.1,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert "tls" not in entry.data
    assert entry.data[CONF_VERIFY_SSL] is False


async def test_setup_invalid_host(hass: HomeAssistant) -> None:
    """Test setup fails when the host has an unsupported scheme."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_HOST: "ftp://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: True,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "The ISY/IoX host value in configuration is invalid"


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_forwards_verify_ssl_to_pyisy(
    hass: HomeAssistant,
    mock_isy: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the verify_ssl entry option is forwarded to the pyisy ISY constructor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_HOST: "https://1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_VERIFY_SSL: verify_ssl,
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.isy994.ISY", return_value=mock_isy
    ) as isy_constructor:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isy_constructor.call_args.kwargs["verify_ssl"] is verify_ssl


async def test_node_device_linked_to_isy_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
) -> None:
    """Test a root node's device is linked to the ISY device via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    node = mock_node(mock_isy, "22 22 22 1", "Test Node", "GenericNode")
    mock_isy.nodes.__iter__.return_value = [("Test Node", node)]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    isy_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_isy.uuid), mock_config_entry.entry_id
    )
    node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_isy.uuid}_{node.address}"), mock_config_entry.entry_id
    )
    assert isy_device is not None
    assert node_device is not None
    assert node_device.via_device_id == isy_device.id


@pytest.mark.parametrize(
    ("platform", "node_def_id"),
    [
        pytest.param(Platform.SWITCH, "RelayLampSwitch_ADV", id="switch"),
        pytest.param(Platform.SENSOR, "GenericSensor", id="sensor"),
    ],
)
async def test_node_listeners_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    platform: Platform,
    node_def_id: str,
) -> None:
    """Test removing an entity unsubscribes it from its node's event emitters."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "22 22 22 1", "Test Node", node_def_id)
    node.status_events = EventEmitter()
    node.control_events = EventEmitter()
    mock_isy.nodes.__iter__.return_value = [("Test Node", node)]
    events = async_capture_events(hass, EVENT_ISY994_CONTROL)

    with patch("homeassistant.components.isy994.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"{platform}.test_node"
    assert hass.states.get(entity_id) is not None
    assert node.status_events._subscribers
    assert node.control_events._subscribers

    node.control_events.notify(NodeProperty(node.address, CMD_ON))
    await hass.async_block_till_done()
    assert len(events) == 1

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert not node.status_events._subscribers
    assert not node.control_events._subscribers

    node.control_events.notify(NodeProperty(node.address, CMD_ON))
    await hass.async_block_till_done()
    assert len(events) == 1


@pytest.mark.parametrize(
    ("platform", "node_attrs", "unique_id_suffix", "expected_listeners"),
    [
        pytest.param(
            Platform.NUMBER,
            {"aux_properties": {PROP_ON_LEVEL: NodeProperty(PROP_ON_LEVEL)}},
            f"_{PROP_ON_LEVEL}",
            {"status": 0, "control": 1, "isy": 1},
            id="aux_control_number",
        ),
        pytest.param(
            Platform.SELECT,
            {"aux_properties": {PROP_RAMP_RATE: NodeProperty(PROP_RAMP_RATE)}},
            f"_{PROP_RAMP_RATE}",
            {"status": 0, "control": 1, "isy": 1},
            id="ramp_rate_select",
        ),
        pytest.param(
            Platform.SWITCH,
            {},
            f"_{TAG_ENABLED}",
            {"status": 0, "control": 0, "isy": 1},
            id="enable_switch",
        ),
        pytest.param(
            Platform.NUMBER,
            {"is_backlight_supported": True},
            f"_{CMD_BACKLIGHT}",
            {"status": 0, "control": 1, "isy": 2},
            id="backlight_number",
        ),
        pytest.param(
            Platform.SELECT,
            {"is_backlight_supported": True, "node_def_id": "KeypadDimmer"},
            f"_{CMD_BACKLIGHT}",
            {"status": 0, "control": 1, "isy": 2},
            id="backlight_select",
        ),
        pytest.param(
            Platform.SENSOR,
            {"aux_properties": {"TPW": NodeProperty("TPW")}},
            "_TPW",
            {"status": 0, "control": 1, "isy": 1},
            id="aux_sensor",
        ),
        pytest.param(
            Platform.BUTTON,
            {},
            "_query",
            {"status": 0, "control": 0, "isy": 1},
            id="query_button",
        ),
        pytest.param(
            Platform.BUTTON,
            {},
            "_beep",
            {"status": 0, "control": 0, "isy": 1},
            id="beep_button",
        ),
    ],
)
async def test_overridden_listeners_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    mock_node: Callable[..., Any],
    platform: Platform,
    node_attrs: dict[str, Any],
    unique_id_suffix: str,
    expected_listeners: dict[str, int],
) -> None:
    """Test entities overriding the node subscriptions unsubscribe on removal."""
    mock_config_entry.add_to_hass(hass)
    node = mock_node(mock_isy, "22 22 22 1", "Test Node", "DimmerLampSwitch")
    for attr, value in node_attrs.items():
        setattr(node, attr, value)
    node.status_events = EventEmitter()
    node.control_events = EventEmitter()
    mock_isy.nodes.status_events = EventEmitter()
    mock_isy.nodes.__iter__.return_value = [("Test Node", node)]
    emitters = {
        "status": node.status_events,
        "control": node.control_events,
        "isy": mock_isy.nodes.status_events,
    }

    with patch("homeassistant.components.isy994.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        platform, DOMAIN, f"{MOCK_ISY_UUID}_{node.address}{unique_id_suffix}"
    )
    assert entity_id is not None
    entity = hass.data[DATA_INSTANCES][platform].get_entity(entity_id)
    assert entity is not None
    assert {
        name: len(entity_listeners(emitter, entity))
        for name, emitter in emitters.items()
    } == expected_listeners
    # Listeners of sibling entities sharing these emitters must survive.
    remaining = {
        name: [
            listener
            for listener in emitter._subscribers
            if listener not in entity_listeners(emitter, entity)
        ]
        for name, emitter in emitters.items()
    }

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert {
        name: emitter._subscribers for name, emitter in emitters.items()
    } == remaining


@pytest.mark.parametrize(
    "unique_id_suffix",
    [pytest.param("", id="value"), pytest.param("_init", id="initial_value")],
)
async def test_variable_listener_removed_with_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_isy: MagicMock,
    unique_id_suffix: str,
) -> None:
    """Test removing a variable number entity unsubscribes it from the variable."""
    mock_config_entry.add_to_hass(hass)
    variable = MagicMock(
        spec=Variable,
        address="1.1",
        prec="0",
        status=1,
        init=0,
        last_edited=None,
        status_events=EventEmitter(),
    )
    variable.name = "HA.Test Variable"
    mock_isy.variables.children = [(1, variable.name, 1)]
    mock_isy.variables.__getitem__.return_value = {1: variable}

    with patch("homeassistant.components.isy994.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER,
        DOMAIN,
        f"{MOCK_ISY_UUID}_{variable.address}{unique_id_suffix}",
    )
    assert entity_id is not None
    entity = hass.data[DATA_INSTANCES][Platform.NUMBER].get_entity(entity_id)
    assert entity is not None
    assert len(entity_listeners(variable.status_events, entity)) == 1
    # The sibling value/initial value entity also listens to the variable.
    assert len(variable.status_events._subscribers) == 2

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert not entity_listeners(variable.status_events, entity)
    assert len(variable.status_events._subscribers) == 1
