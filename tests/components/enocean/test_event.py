"""Tests for the EnOcean event platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from enocean_async import EURID, Observable, Observation
from enocean_async.eep.device_type import DeviceType
from enocean_async.semantics.device_spec import DeviceSpec
from enocean_async.semantics.entity import Entity
import pytest

from homeassistant.components.enocean.const import DOMAIN
from homeassistant.components.event import ATTR_EVENT_TYPE, DOMAIN as EVENT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

EURID_BYTES = [0xDE, 0xAD, 0xBE, 0xEF]
OTHER_EURID_BYTES = [0x01, 0x01, 0x02, 0x02]


def _make_gateway(device_specs: dict) -> MagicMock:
    """Return a mock EnOcean gateway."""
    version_info = MagicMock()
    version_info.eurid = EURID.from_bytelist(EURID_BYTES)
    version_info.app_description = "TCM300"
    version_info.app_version = MagicMock()
    version_info.app_version.version_string = "1.0.0"

    gw = MagicMock()
    gw.start = AsyncMock()
    gw.stop = MagicMock()
    gw.version_info = AsyncMock(return_value=version_info)
    gw.base_id = AsyncMock(return_value=MagicMock())
    gw.add_observation_callback = MagicMock()
    gw.add_device = MagicMock()
    gw.device_specs = device_specs
    gw.device_spec = MagicMock(return_value=None)
    return gw


@pytest.fixture
def mock_gateway() -> MagicMock:
    """Return a mock gateway with a F6-02 push-button device."""
    eurid = EURID.from_bytelist(EURID_BYTES)
    device_type = MagicMock(spec=DeviceType)
    device_type.manufacturer = None
    device_type.model = "F6-02-01"
    device_type.eep = MagicMock()
    spec = DeviceSpec(
        device_type=device_type,
        entities=[
            Entity(id="a0", observables=frozenset({Observable.BUTTON_EVENT})),
            Entity(id="b0", observables=frozenset({Observable.BUTTON_EVENT})),
        ],
    )
    return _make_gateway({eurid: spec})


async def _setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Set up the EnOcean integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.enocean.Gateway", return_value=mock_gateway):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_event_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that event entities are created for each button entity."""
    await _setup_entry(hass, mock_config_entry, mock_gateway)

    eurid = EURID.from_bytelist(EURID_BYTES)
    assert entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, f"{eurid!s}.a0")
    assert entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, f"{eurid!s}.b0")


async def test_no_event_entities_without_button_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no event entities are created when there are no button devices."""
    gw = _make_gateway({})
    await _setup_entry(hass, mock_config_entry, gw)

    eurid = EURID.from_bytelist(EURID_BYTES)
    assert (
        entity_registry.async_get_entity_id(EVENT_DOMAIN, DOMAIN, f"{eurid!s}.a0")
        is None
    )


async def test_observation_triggers_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a matching observation fires the event entity and updates state."""
    await _setup_entry(hass, mock_config_entry, mock_gateway)

    eurid = EURID.from_bytelist(EURID_BYTES)
    entity_id = entity_registry.async_get_entity_id(
        EVENT_DOMAIN, DOMAIN, f"{eurid!s}.a0"
    )
    assert entity_id is not None

    # Retrieve the registered observation callback and call it directly.
    cb = mock_gateway.add_observation_callback.call_args_list[-1][0][0]
    observation = Observation(
        device=eurid,
        entity="a0",
        values={Observable.BUTTON_EVENT: "clicked"},
    )
    cb(observation)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "clicked"


async def test_observation_for_different_device_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an observation for a different device does not trigger an event."""
    await _setup_entry(hass, mock_config_entry, mock_gateway)

    eurid = EURID.from_bytelist(EURID_BYTES)
    entity_id = entity_registry.async_get_entity_id(
        EVENT_DOMAIN, DOMAIN, f"{eurid!s}.a0"
    )
    assert entity_id is not None

    # Establish a known state with a matching observation.
    cb = mock_gateway.add_observation_callback.call_args_list[-1][0][0]
    cb(
        Observation(
            device=eurid, entity="a0", values={Observable.BUTTON_EVENT: "clicked"}
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes[ATTR_EVENT_TYPE] == "clicked"

    # Observation for a different device must not change state.
    other_eurid = EURID.from_bytelist(OTHER_EURID_BYTES)
    cb(
        Observation(
            device=other_eurid, entity="a0", values={Observable.BUTTON_EVENT: "pressed"}
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes[ATTR_EVENT_TYPE] == "clicked"
