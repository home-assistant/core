"""Test the repairs of the Hikvision integration."""

from typing import Any
from unittest.mock import MagicMock, patch
import uuid

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.components.hikvision.identity import (
    async_earlier_entities,
    decode_ambiguous_identities,
)
from homeassistant.components.hikvision.repairs import async_create_fix_flow
from homeassistant.config_entries import ConfigEntryState, OperationNotAllowed
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

MOTION = "_Motion_1"
LINE_CROSSING = "_Line Crossing_1"
TAMPER = "_Tamper Detection_1"


class Earlier:
    """The identities of a camera registered under earlier made-up IDs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MockConfigEntry,
        rests: tuple[str, ...],
        with_devices: bool,
    ) -> None:
        """Register two copies of each, as two setups of older versions did."""
        self.made_up = [str(uuid.uuid4()) for _ in range(2)]
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        self.devices = [
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id, identifiers={(DOMAIN, made_up)}
            )
            for made_up in self.made_up
            if with_devices
        ]
        self.entities = {
            rest: [
                entity_registry.async_get_or_create(
                    "binary_sensor",
                    DOMAIN,
                    f"{made_up}{rest}",
                    config_entry=entry,
                    device_id=self.devices[index].id if with_devices else None,
                )
                for index, made_up in enumerate(self.made_up)
            ]
            for rest in rests
        }


@pytest.fixture
async def own_id(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> str:
    """Return the made-up ID the entry was created with."""
    assert await async_setup_component(hass, "repairs", {})
    own = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=own)
    # pyHik before 0.5.1 makes up another one at each connection.
    mock_hikcamera.return_value.get_id = uuid.uuid4()
    return own


def _register_ties(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    rests: tuple[str, ...] = (MOTION,),
    with_devices: bool = True,
) -> Earlier:
    """Register earlier identities that share their date of creation."""
    now = dt_util.utcnow()
    freezer.move_to("2024-01-01T00:00:00+00:00")
    earlier = Earlier(hass, entry, rests, with_devices)
    # Back to now: the client's access token is from now.
    freezer.move_to(now)
    return earlier


async def _set_up_with_ties(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    rests: tuple[str, ...] = (MOTION,),
) -> Earlier:
    """Register tied earlier identities, then set the entry up."""
    earlier = _register_ties(hass, freezer, entry, rests)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return earlier


def _registries(
    hass: HomeAssistant, entry: MockConfigEntry
) -> tuple[dict[str, set[tuple[str, str]]], dict[str, str]]:
    """Return the identifiers of the entry's devices and its entities' unique IDs."""
    return (
        {
            device.id: set(device.identifiers)
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), entry.entry_id
            )
        },
        {
            entity.entity_id: entity.unique_id
            for entity in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        },
    )


def _current_device(hass: HomeAssistant, entry: MockConfigEntry) -> dr.DeviceEntry:
    """Return the device the setup registered under the entry's ID."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, str(entry.unique_id)), entry.entry_id
    )
    assert device is not None
    return device


def _current_entity(hass: HomeAssistant, entry: MockConfigEntry, rest: str) -> str:
    """Return the entity the setup registered under the entry's ID."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.unique_id}{rest}"
    )
    assert entity_id is not None
    return entity_id


def _current_entity_id(hass: HomeAssistant, entry: MockConfigEntry, rest: str) -> str:
    """Return the registry ID of the entity the setup registered under the entry's ID."""
    return er.async_get(hass).async_get(_current_entity(hass, entry, rest)).id


def _replace_issue_without_data(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Store the issue of the entry as it would be without its questions."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry),
        config_entry_id=entry.entry_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="ambiguous_identities",
        translation_placeholders={"name": entry.title},
    )


def _issue_id(entry: MockConfigEntry) -> str:
    return f"ambiguous_identities_{entry.entry_id}"


@pytest.mark.usefixtures("own_id")
async def test_an_earlier_device_and_entity_are_kept(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the chosen earlier device and entity take the place of the current ones.

    The device the setup registered is removed, after its entities move to the
    kept one; the entity it registered is removed, and the kept one gets its
    unique ID, with its own entity ID.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    own = str(mock_config_entry.unique_id)
    current_device = _current_device(hass, mock_config_entry)
    current_entity = _current_entity(hass, mock_config_entry, MOTION)
    kept_device, other_device = earlier.devices[1], earlier.devices[0]
    kept_entity, other_entity = earlier.entities[MOTION][1], earlier.entities[MOTION][0]

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    assert data["step_id"] == "choose_device"
    assert data["description_placeholders"]["name"] == mock_config_entry.title
    flow_id = data["flow_id"]
    data = await process_repair_fix_flow(client, flow_id, json={"keep": kept_device.id})
    assert data["step_id"] == "choose_entity"
    assert data["description_placeholders"]["current"].endswith(f"({current_entity})")
    data = await process_repair_fix_flow(client, flow_id, json={"keep": kept_entity.id})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert device_registry.async_get(current_device.id) is None
    assert device_registry.async_get(kept_device.id).identifiers == {(DOMAIN, own)}
    assert device_registry.async_get(other_device.id).identifiers == {
        (DOMAIN, earlier.made_up[0])
    }
    assert entity_registry.async_get(current_entity) is None
    kept = entity_registry.async_get(kept_entity.entity_id)
    assert kept.unique_id == f"{own}{MOTION}"
    assert kept.device_id == kept_device.id
    assert entity_registry.async_get(other_entity.entity_id).unique_id == (
        f"{earlier.made_up[0]}{MOTION}"
    )
    # The entry was reloaded: the kept entity is the camera's motion sensor now.
    assert hass.states.get(kept_entity.entity_id).state != STATE_UNAVAILABLE
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry)) is None


@pytest.mark.usefixtures("own_id")
async def test_keeping_the_ones_set_up_now_changes_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the default choice, the ones the setup registered, changes nothing."""
    await _set_up_with_ties(hass, freezer, mock_config_entry)
    before = _registries(hass, mock_config_entry)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(
        client, flow_id, json={"keep": _current_device(hass, mock_config_entry).id}
    )
    data = await process_repair_fix_flow(
        client,
        flow_id,
        json={"keep": _current_entity_id(hass, mock_config_entry, MOTION)},
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert _registries(hass, mock_config_entry) == before
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry)) is None


@pytest.mark.usefixtures("own_id")
@pytest.mark.parametrize(
    ("device", "entity", "unloaded_first"),
    [
        ("current", "current", False),
        ("earlier", "current", True),
        ("current", "earlier", True),
        # Nothing holds the entry's ID any more: the earlier one takes it. Removing
        # a device removes its entities.
        ("removed", "removed", True),
        ("current", "removed", True),
    ],
)
async def test_the_entry_is_unloaded_before_what_it_uses_is_replaced(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    device: str,
    entity: str,
    unloaded_first: bool,
) -> None:
    """Test the entry is unloaded first only when an answer replaces something.

    Keeping the current device and entity needs no unload, nor any reload.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    keep_device = (
        _current_device(hass, mock_config_entry).id
        if device == "current"
        else earlier.devices[0].id
    )
    keep_entity = (
        _current_entity_id(hass, mock_config_entry, MOTION)
        if entity == "current"
        else earlier.entities[MOTION][0].id
    )
    if entity == "removed":
        entity_registry.async_remove(_current_entity(hass, mock_config_entry, MOTION))
    if device == "removed":
        device_registry.async_remove_device(_current_device(hass, mock_config_entry).id)
    before = _registries(hass, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": keep_device})
    unload = hass.config_entries.async_unload
    seen: list[bool] = []

    async def unload_and_look(entry_id: str, **kwargs: Any) -> bool:
        # Whether nothing was replaced yet when the entry is unloaded.
        seen.append(_registries(hass, mock_config_entry) == before)
        return await unload(entry_id, **kwargs)

    with patch.object(hass.config_entries, "async_unload", unload_and_look):
        data = await process_repair_fix_flow(
            client, flow_id, json={"keep": keep_entity}
        )
        await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert seen[:1] == ([True] if unloaded_first else [])
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("own_id")
async def test_the_choices_show_names_and_keep_the_current_one_by_default(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test each choice shows its name, and the one set up now is the default."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    device_registry.async_update_device(earlier.devices[0].id, name="Old camera")
    entity_registry.async_update_entity(
        earlier.entities[MOTION][0].entity_id, name="Old motion"
    )
    current_device = _current_device(hass, mock_config_entry)
    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    [field] = data["data_schema"]
    assert field["default"] == current_device.id
    labels = {
        option["value"]: option["label"]
        for option in field["selector"]["select"]["options"]
    }
    assert labels[earlier.devices[0].id] == "Old camera"
    # The description names the first earlier copy.
    first = field["selector"]["select"]["options"][0]
    assert data["description_placeholders"]["device"] == first["label"]

    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"keep": current_device.id}
    )
    [field] = data["data_schema"]
    assert field["default"] == _current_entity_id(hass, mock_config_entry, MOTION)
    labels = {
        option["value"]: option["label"]
        for option in field["selector"]["select"]["options"]
    }
    entity = earlier.entities[MOTION][0]
    assert labels[entity.id] == f"Old motion ({entity.entity_id})"
    first = field["selector"]["select"]["options"][0]
    assert data["description_placeholders"]["entity"] == first["label"]


@pytest.mark.usefixtures("own_id")
async def test_a_repair_whose_entry_lost_its_id_ends(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry with no ID left has nothing its identities are made from."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=None)

    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"keep": earlier.devices[0].id}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "entry_removed"


@pytest.mark.usefixtures("own_id")
async def test_a_repair_left_halfway_changes_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing is changed until every question is answered.

    Here the user keeps earlier ones for the device and the first entity, then
    leaves the repair: the current entities keep running, and the issue stays.
    """
    earlier = await _set_up_with_ties(
        hass, freezer, mock_config_entry, rests=(MOTION, LINE_CROSSING)
    )
    before = _registries(hass, mock_config_entry)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    assert data["step_id"] == "choose_entity"
    await hass.async_block_till_done()

    assert _registries(hass, mock_config_entry) == before
    current = _current_entity(hass, mock_config_entry, MOTION)
    assert hass.states.get(current).state != STATE_UNAVAILABLE
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))


@pytest.mark.usefixtures("own_id")
async def test_copies_of_a_device_are_told_apart(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test each device to choose from has its own label: name, area, ID."""
    earlier = _register_ties(hass, freezer, mock_config_entry)
    area = area_registry.async_create("Garage")
    device_registry.async_update_device(
        earlier.devices[0].id, name_by_user="Driveway", area_id=area.id
    )
    device_registry.async_update_device(earlier.devices[1].id, name_by_user="Driveway")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))

    (keep,) = data["data_schema"]
    labels = {
        option["value"]: option["label"]
        for option in keep["selector"]["select"]["options"]
    }
    assert labels[earlier.devices[0].id] == "Driveway (Garage)"
    assert labels[earlier.devices[1].id] == "Driveway"
    assert len(set(labels.values())) == len(labels) == 3


@pytest.mark.usefixtures("own_id")
async def test_only_what_still_has_copies_is_asked(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity whose earlier copies were deleted is not asked about."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    for entity in earlier.entities[MOTION]:
        entity_registry.async_remove(entity.entity_id)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    assert data["step_id"] == "choose_device"
    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"keep": earlier.devices[0].id}
    )

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()


@pytest.mark.usefixtures("own_id")
async def test_a_sole_earlier_copy_is_kept_without_asking(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a copy left alone, with nothing under the entry's ID, takes its place.

    The user removed the ones set up now and all but one earlier copy.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    own = str(mock_config_entry.unique_id)
    entity_registry.async_remove(_current_entity(hass, mock_config_entry, MOTION))
    entity_registry.async_remove(earlier.entities[MOTION][0].entity_id)
    device_registry.async_remove_device(_current_device(hass, mock_config_entry).id)
    device_registry.async_remove_device(earlier.devices[0].id)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    survivor = earlier.entities[MOTION][1]
    assert entity_registry.async_get(survivor.entity_id).unique_id == f"{own}{MOTION}"
    assert device_registry.async_get(earlier.devices[1].id).identifiers == {
        (DOMAIN, own)
    }
    # Reloaded: the survivor is the camera's motion sensor again.
    assert hass.states.get(survivor.entity_id).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("own_id")
async def test_questions_added_while_the_repair_is_open_are_asked(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a setup that adds questions meanwhile does not have them dropped.

    Finishing the repair removes the issue, and the next setups do not ask again.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    added = _register_ties(
        hass, freezer, mock_config_entry, rests=(TAMPER,), with_devices=False
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    assert data["step_id"] == "choose_earlier_entity"
    options = {
        option["value"]
        for option in data["data_schema"][0]["selector"]["select"]["options"]
    }
    assert options == {entity.id for entity in added.entities[TAMPER]}
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": added.entities[TAMPER][0].id}
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()


@pytest.mark.usefixtures("own_id")
async def test_a_kept_entity_takes_the_device_of_the_one_it_replaces(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a kept entity is on the camera's device, though no setup moves it.

    The camera no longer has the sensor, so the reload does not set it up.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    current = entity_registry.async_get(
        _current_entity(hass, mock_config_entry, MOTION)
    )
    mock_hikcamera.return_value.current_event_states = {"Line Crossing": [(False, 1)]}

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(
        client, flow_id, json={"keep": _current_device(hass, mock_config_entry).id}
    )
    await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    await hass.async_block_till_done()

    kept = entity_registry.async_get(earlier.entities[MOTION][0].entity_id)
    assert kept.device_id == current.device_id


@pytest.mark.usefixtures("own_id")
@pytest.mark.parametrize("identified_by", ["connection", "identifier"])
async def test_what_else_is_on_the_current_device_is_kept(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identified_by: str,
) -> None:
    """Test the current device gives up only the identifier of the entry's ID.

    It stays for what else identifies it, a connection or an identifier of another
    integration, with the entities of other entries; the entry's own entities, and
    the channel devices linked through it, move to the kept one.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    own = str(mock_config_entry.unique_id)
    current = _current_device(hass, mock_config_entry)
    # One the camera no longer has: no reload moves it.
    gone = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{own}_Gone_1",
        config_entry=mock_config_entry,
        device_id=current.id,
    )
    connection = (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    other_identifier = ("other", "camera")
    if identified_by == "connection":
        device_registry.async_update_device(current.id, new_connections={connection})
    else:
        device_registry.async_update_device(
            current.id, new_identifiers={*current.identifiers, other_identifier}
        )
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    others = entity_registry.async_get_or_create(
        "sensor", "other", "other", config_entry=other_entry, device_id=current.id
    )
    channel = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{own}_2")},
        via_device_id=current.id,
    )
    assert channel.via_device_id == current.id
    # Linked through it by another integration: it stays linked to it.
    linked = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "linked")},
        via_device_id=current.id,
    )
    # A channel of an earlier setup, which the camera no longer has: it moves too.
    old_channel = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{earlier.made_up[1]}_3")},
        via_device_id=current.id,
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    await process_repair_fix_flow(
        client,
        flow_id,
        json={"keep": _current_entity_id(hass, mock_config_entry, MOTION)},
    )
    await hass.async_block_till_done()

    kept_current = device_registry.async_get(current.id)
    if identified_by == "connection":
        assert kept_current.identifiers == set()
        assert kept_current.connections == {connection}
    else:
        assert kept_current.identifiers == {other_identifier}
    assert entity_registry.async_get(others.entity_id).device_id == current.id
    assert entity_registry.async_get(gone.entity_id).device_id == (
        earlier.devices[0].id
    )
    assert device_registry.async_get(channel.id).via_device_id == earlier.devices[0].id
    assert device_registry.async_get(linked.id).via_device_id == current.id
    assert device_registry.async_get(old_channel.id).via_device_id == (
        earlier.devices[0].id
    )


@pytest.mark.usefixtures("own_id")
async def test_a_choice_removed_before_it_is_kept_is_asked_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device chosen, then removed before the answers apply, is asked again.

    Finishing would remove the issue, which no setup raises again. An entity
    that has nothing left to choose from is not asked again.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    # Removing the device removes its entity too: one earlier entity is left.
    device_registry.async_remove_device(earlier.devices[0].id)
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][1].id}
    )
    assert data["step_id"] == "choose_device"
    options = {
        option["value"]
        for option in data["data_schema"][0]["selector"]["select"]["options"]
    }
    assert options == {
        earlier.devices[1].id,
        _current_device(hass, mock_config_entry).id,
    }
    entity_registry.async_remove(earlier.entities[MOTION][1].entity_id)
    before = _registries(hass, mock_config_entry)
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": _current_device(hass, mock_config_entry).id}
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert _registries(hass, mock_config_entry) == before


@pytest.mark.usefixtures("own_id")
async def test_an_entity_of_another_entry_is_not_replaced(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entity of another entry with the unique ID is left alone.

    It is not this camera's: neither offered as the current one nor removed.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    own = str(mock_config_entry.unique_id)
    # The entry's own is gone, and another entry has its unique ID now.
    entity_registry.async_remove(_current_entity(hass, mock_config_entry, MOTION))
    other_entry = MockConfigEntry(domain=DOMAIN, unique_id="other")
    other_entry.add_to_hass(hass)
    others = entity_registry.async_get_or_create(
        "binary_sensor", DOMAIN, f"{own}{MOTION}", config_entry=other_entry
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": _current_device(hass, mock_config_entry).id}
    )
    assert data["step_id"] == "choose_earlier_entity"
    options = {
        option["value"]
        for option in data["data_schema"][0]["selector"]["select"]["options"]
    }
    assert others.id not in options
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entity_registry.async_get(others.entity_id).config_entry_id == (
        other_entry.entry_id
    )
    assert entity_registry.async_get(
        earlier.entities[MOTION][0].entity_id
    ).unique_id == (f"{earlier.made_up[0]}{MOTION}")


@pytest.mark.usefixtures("own_id")
async def test_the_issue_goes_with_its_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test removing the entry removes the issue about it."""
    await _set_up_with_ties(hass, freezer, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry)) is None


@pytest.mark.usefixtures("own_id")
async def test_a_repair_whose_entry_is_removed_meanwhile_ends(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the repair says so when its entry is removed while it is open."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"keep": earlier.devices[0].id}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "entry_removed"


@pytest.mark.usefixtures("own_id")
async def test_a_repair_after_a_failed_unload_waits_for_a_restart(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the answers are not applied while the entry failed to unload.

    Its entities still run, and it cannot be reloaded to load the ones kept: the
    issue stays, for after the restart.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    before = _registries(hass, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    mock_config_entry.mock_state(hass, ConfigEntryState.FAILED_UNLOAD)

    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    await hass.async_block_till_done()

    assert data["type"] == "abort"
    assert data["reason"] == "restart_required"
    assert _registries(hass, mock_config_entry) == before
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)


@pytest.mark.usefixtures("own_id")
async def test_a_repair_whose_unload_fails_changes_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the answers are not applied when the entry cannot be unloaded first.

    The entities kept would not be set up: the issue stays, for after a restart.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    before = _registries(hass, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})

    with patch(
        "homeassistant.components.hikvision.async_unload_entry", return_value=False
    ):
        data = await process_repair_fix_flow(
            client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
        )
    await hass.async_block_till_done()

    assert data["type"] == "abort"
    assert data["reason"] == "restart_required"
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert _registries(hass, mock_config_entry) == before
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)


@pytest.mark.usefixtures("own_id")
async def test_a_repair_while_the_entry_cannot_be_unloaded_yet_waits(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the answers are not applied while another operation holds the entry.

    The issue stays, for another try.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    before = _registries(hass, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})

    with patch.object(
        hass.config_entries,
        "async_unload",
        side_effect=OperationNotAllowed("busy"),
    ):
        data = await process_repair_fix_flow(
            client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
        )
    await hass.async_block_till_done()

    assert data["type"] == "abort"
    assert data["reason"] == "entry_busy"
    assert _registries(hass, mock_config_entry) == before
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))


@pytest.mark.usefixtures("own_id")
@pytest.mark.parametrize(
    "state",
    [ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.UNLOAD_IN_PROGRESS],
)
async def test_a_repair_while_the_entry_is_set_up_or_unloaded_waits(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    state: ConfigEntryState,
) -> None:
    """Test the answers wait for a setup or an unload that is under way."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    before = _registries(hass, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    mock_config_entry.mock_state(hass, state)

    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "entry_busy"
    assert _registries(hass, mock_config_entry) == before
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)


@pytest.mark.usefixtures("own_id")
async def test_a_choice_removed_while_the_entry_unloads_is_asked_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device removed during the unload is not applied, but asked about again.

    The entry is set up again meanwhile, and the answers wait for the new choice.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    unload = hass.config_entries.async_unload

    async def unload_and_remove(entry_id: str, **kwargs: Any) -> bool:
        unloaded = await unload(entry_id, **kwargs)
        if device_registry.async_get(earlier.devices[0].id) is not None:
            device_registry.async_remove_device(earlier.devices[0].id)
        return unloaded

    with patch.object(hass.config_entries, "async_unload", unload_and_remove):
        data = await process_repair_fix_flow(
            client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
        )
    await hass.async_block_till_done()

    assert data["step_id"] == "choose_device"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.devices[1].id}
    )
    # Its entity went with it.
    assert data["step_id"] == "choose_entity"
    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][1].id}
    )
    await hass.async_block_till_done()
    assert data["type"] == "create_entry"
    assert device_registry.async_get(earlier.devices[1].id).identifiers == {
        (DOMAIN, str(mock_config_entry.unique_id))
    }


@pytest.mark.usefixtures("own_id")
@pytest.mark.parametrize("replaced", ["device", "entity"])
async def test_a_repair_of_an_entry_that_is_not_loaded_sets_it_up(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    replaced: str,
) -> None:
    """Test the answers are applied at once, and the entry is set up with them."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(
        client,
        flow_id,
        json={
            "keep": earlier.devices[0].id
            if replaced == "device"
            else _current_device(hass, mock_config_entry).id
        },
    )

    data = await process_repair_fix_flow(
        client,
        flow_id,
        json={
            "keep": earlier.entities[MOTION][0].id
            if replaced == "entity"
            else _current_entity_id(hass, mock_config_entry, MOTION)
        },
    )
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    own = str(mock_config_entry.unique_id)
    if replaced == "device":
        assert device_registry.async_get(earlier.devices[0].id).identifiers == {
            (DOMAIN, own)
        }
    else:
        kept = entity_registry.async_get(earlier.entities[MOTION][0].entity_id)
        assert kept.unique_id == f"{own}{MOTION}"


@pytest.mark.usefixtures("own_id")
async def test_a_repair_whose_issue_lost_its_questions_applies_its_answers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an issue left without its data meanwhile adds no question."""
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    _replace_issue_without_data(hass, mock_config_entry)

    data = await process_repair_fix_flow(
        client, flow_id, json={"keep": earlier.entities[MOTION][0].id}
    )
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"


@pytest.mark.usefixtures("own_id")
async def test_a_setup_replaces_an_issue_without_its_questions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a stored issue that has no questions is asked again in full."""
    _replace_issue_without_data(hass, mock_config_entry)

    await _set_up_with_ties(hass, freezer, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    assert issue.data is not None
    assert decode_ambiguous_identities(issue.data) == (
        [""],
        [["binary_sensor", MOTION]],
    )


@pytest.mark.parametrize("data", [None, {"devices": "[]", "entities": "[]"}])
async def test_a_repair_without_its_data_cannot_start(
    hass: HomeAssistant, data: dict[str, str] | None
) -> None:
    """Test the repair needs the data of its issue, the entry included."""
    with pytest.raises(ValueError, match="Missing data"):
        await async_create_fix_flow(hass, "ambiguous_identities_x", data)


@pytest.mark.usefixtures("own_id")
async def test_a_repair_finished_in_another_window_changes_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a second open repair does not apply its answers once the first finished.

    Its answers would undo what the first one kept.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    client = await hass_client()
    first = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    second = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    await process_repair_fix_flow(
        client, first["flow_id"], json={"keep": earlier.devices[0].id}
    )
    data = await process_repair_fix_flow(
        client, first["flow_id"], json={"keep": earlier.entities[MOTION][0].id}
    )
    await hass.async_block_till_done()
    assert data["type"] == "create_entry"
    kept = _registries(hass, mock_config_entry)

    await process_repair_fix_flow(
        client, second["flow_id"], json={"keep": earlier.devices[1].id}
    )
    data = await process_repair_fix_flow(
        client, second["flow_id"], json={"keep": earlier.entities[MOTION][1].id}
    )
    await hass.async_block_till_done()

    assert data["type"] == "abort"
    assert data["reason"] == "already_finished"
    assert _registries(hass, mock_config_entry) == kept


@pytest.mark.usefixtures("own_id")
async def test_a_later_setup_adds_to_what_the_issue_asks(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a setup that finds other ties keeps what the issue already asks.

    The camera does not have this sensor, so nothing takes its place, and each
    setup finds it again: it is asked once.
    """
    await _set_up_with_ties(hass, freezer, mock_config_entry)
    _register_ties(
        hass, freezer, mock_config_entry, rests=(TAMPER,), with_devices=False
    )

    for _ in range(2):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    assert issue.data["entities"] == (
        f'[["binary_sensor", "{MOTION}"], ["binary_sensor", "{TAMPER}"]]'
    )


@pytest.mark.usefixtures("own_id")
async def test_the_next_setup_does_not_ask_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a reload keeps what the issue asks, without asking it twice."""
    await _set_up_with_ties(hass, freezer, mock_config_entry)
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry)) == issue


@pytest.mark.usefixtures("own_id")
async def test_a_removed_device_hands_over_what_other_entries_have_on_it(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entities and devices of other entries move off a removed device.

    Removing a device would remove their entities and unlink their devices, so
    a helper the user put on the camera stays on the camera.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    current = _current_device(hass, mock_config_entry)
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    helper = entity_registry.async_get_or_create(
        "sensor", "other", "helper", config_entry=other_entry, device_id=current.id
    )
    linked = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "linked")},
        via_device_id=current.id,
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    await process_repair_fix_flow(
        client,
        flow_id,
        json={"keep": _current_entity_id(hass, mock_config_entry, MOTION)},
    )
    await hass.async_block_till_done()

    assert device_registry.async_get(current.id) is None
    assert (
        entity_registry.async_get(helper.entity_id).device_id == earlier.devices[0].id
    )
    assert device_registry.async_get(linked.id).via_device_id == earlier.devices[0].id


@pytest.mark.usefixtures("own_id")
async def test_a_chosen_entity_renamed_meanwhile_is_kept(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a choice is kept by registry ID, which a rename does not change."""
    earlier = await _set_up_with_ties(
        hass, freezer, mock_config_entry, rests=(MOTION, LINE_CROSSING)
    )
    own = str(mock_config_entry.unique_id)
    chosen = earlier.entities[MOTION][0]

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(
        client, flow_id, json={"keep": _current_device(hass, mock_config_entry).id}
    )
    await process_repair_fix_flow(client, flow_id, json={"keep": chosen.id})
    entity_registry.async_update_entity(
        chosen.entity_id, new_entity_id="binary_sensor.driveway_motion"
    )
    data = await process_repair_fix_flow(
        client,
        flow_id,
        json={"keep": _current_entity_id(hass, mock_config_entry, LINE_CROSSING)},
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    renamed = entity_registry.async_get("binary_sensor.driveway_motion")
    assert renamed.id == chosen.id
    assert renamed.unique_id == f"{own}{MOTION}"


@pytest.mark.usefixtures("own_id")
async def test_a_kept_entity_without_a_current_one_moves_to_the_kept_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity kept from another setup than the kept device is put on it.

    The camera no longer has the sensor: no reload moves it, and removing the
    duplicate device it was on would remove it.
    """
    earlier = await _set_up_with_ties(hass, freezer, mock_config_entry)
    entity_registry.async_remove(_current_entity(hass, mock_config_entry, MOTION))
    entity_registry.async_remove(earlier.entities[MOTION][0].entity_id)
    mock_hikcamera.return_value.current_event_states = {"Line Crossing": [(False, 1)]}

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    # Not left to the setup of the reload, which does it too.
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        data = await process_repair_fix_flow(
            client, data["flow_id"], json={"keep": earlier.devices[0].id}
        )
    assert data["type"] == "create_entry"
    reload.assert_called_once_with(mock_config_entry.entry_id)

    survivor = earlier.entities[MOTION][1]
    assert entity_registry.async_get(survivor.entity_id).device_id == (
        earlier.devices[0].id
    )
    device_registry.async_remove_device(earlier.devices[1].id)
    assert entity_registry.async_get(survivor.entity_id) is not None


@pytest.mark.usefixtures("own_id")
async def test_finishing_reads_the_registries_once_per_pass(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the answers are checked, then applied, each reading the copies once.

    Not once per answer: a large registry would hold the event loop for each.
    """
    earlier = await _set_up_with_ties(
        hass, freezer, mock_config_entry, rests=(MOTION, LINE_CROSSING, TAMPER)
    )
    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": earlier.devices[0].id})
    for rest in (MOTION, LINE_CROSSING):
        await process_repair_fix_flow(
            client, flow_id, json={"keep": earlier.entities[rest][0].id}
        )

    with patch(
        "homeassistant.components.hikvision.repairs.async_earlier_entities",
        wraps=async_earlier_entities,
    ) as read:
        data = await process_repair_fix_flow(
            client, flow_id, json={"keep": earlier.entities[TAMPER][0].id}
        )
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    # Once per pass, not per answer: to check the answers, to check them again
    # once the entry is unloaded, and to apply them.
    assert read.call_count == 3


async def test_a_channel_kept_before_its_nvr_is_not_linked_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    own_id: str,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a channel device removed by one answer is skipped by the next.

    Its copies were registered before the NVR's, so the channel is asked first:
    the channel device it replaces is gone when the NVR's devices move.
    """
    now = dt_util.utcnow()
    freezer.move_to("2024-01-01T00:00:00+00:00")
    made_up = [str(uuid.uuid4()) for _ in range(2)]
    channels = [
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, f"{earlier}_1")},
        )
        for earlier in made_up
    ]
    nvrs = [
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, earlier)},
        )
        for earlier in made_up
    ]
    freezer.move_to(now)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    nvr = _current_device(hass, mock_config_entry)
    # As the channel's entities register it.
    channel = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{own_id}_1")},
        via_device_id=nvr.id,
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, _issue_id(mock_config_entry))
    flow_id = data["flow_id"]
    await process_repair_fix_flow(client, flow_id, json={"keep": channels[0].id})
    data = await process_repair_fix_flow(client, flow_id, json={"keep": nvrs[0].id})
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert device_registry.async_get(channel.id) is None
    assert device_registry.async_get(nvr.id) is None
    assert device_registry.async_get(channels[0].id).via_device_id == nvrs[0].id
    assert not issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
