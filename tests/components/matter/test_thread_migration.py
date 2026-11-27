"""Test moving Matter Thread devices onto another Thread network."""

import asyncio
from base64 import b64encode
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import dataclass_from_dict
from matter_server.common.models import MatterNodeData
import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed

from homeassistant.components.thread import async_add_dataset, dataset_store
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from .common import (
    _setup_integration_with_nodes,
    create_node_from_fixture,
    load_and_parse_node_fixture,
    setup_integration_with_node_fixture,
)

from tests.components.thread import DATASET_1, DATASET_2

pytestmark = pytest.mark.usefixtures(
    "short_border_agent_discovery_timeout", "mock_thread_discovery"
)

# The preferred network, the one the devices are moved to by default
TARGET_ID = bytes.fromhex("1111111122222222")
# The network of the eve_contact_sensor fixture
PREVIOUS_ID = bytes.fromhex("52fe7495632d4fbb")
CONTACT_SENSOR = 9
ENERGY_PLUG = 61

Commands = clusters.NetworkCommissioning.Commands
Commissioning = clusters.GeneralCommissioning.Commands


@pytest.fixture(autouse=True)
async def preferred_network(hass: HomeAssistant) -> None:
    """Have DATASET_1 as the preferred network."""
    await async_add_dataset(hass, "test", DATASET_1)
    store = await dataset_store.async_get_store(hass)
    store.preferred_dataset = next(iter(store.datasets))


@pytest.fixture(autouse=True)
def no_retry_delay() -> Generator[None]:
    """Retry completing at once."""
    with patch(
        "homeassistant.components.matter.thread_migration.COMPLETE_RETRY_DELAY", 0
    ):
        yield


class Devices:
    """Matter devices that answer the way healthy ones do.

    A device reports the network it is on when that is read, and joins the
    network it is told to connect to.
    """

    def __init__(self, matter_client: MagicMock) -> None:
        """Answer the client's commands and reads."""
        # Live network ID by node; a node without one does not answer reads
        # of its networks.
        self.networks: dict[int, bytes] = {}
        self.matter_client = matter_client
        matter_client.send_device_command.side_effect = self.respond
        matter_client.read_attribute.side_effect = self.read

    async def respond(self, command: Any, node_id: int, **kwargs: Any) -> Any:
        """Answer a command."""
        if isinstance(command, Commands.ConnectNetwork):
            self.networks[node_id] = command.networkID
        if isinstance(
            command, (Commissioning.ArmFailSafe, Commissioning.CommissioningComplete)
        ):
            return {"errorCode": 0}
        return {"networkingStatus": 0}

    async def read(self, node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        """Answer a read: the networks as joined, anything else as reported."""
        values: dict[str, Any] = {}
        for path in attribute_path:
            if path in ("0/53/4", "0/49/1"):
                if (network := self.networks.get(node_id)) is None:
                    raise MatterError("no answer")
                values[path] = (
                    int.from_bytes(network, "big")
                    if path == "0/53/4"
                    else [{"0": b64encode(network).decode(), "1": True}]
                )
            else:
                attributes = self.matter_client.get_node(node_id).node_data.attributes
                values[path] = attributes.get(path)
        return values


@pytest.fixture(name="devices")
def devices_fixture(matter_client: MagicMock) -> Devices:
    """Have the devices answer the way healthy ones do."""
    return Devices(matter_client)


def _device_id(hass: HomeAssistant, node_id: int) -> str:
    """Return the device id of a node."""
    return next(
        device.id
        for device in dr.async_get(hass).devices
        if any(
            domain == "matter" and f"-{node_id:016X}-" in value
            for domain, value in device.identifiers
        )
    )


def _commands(matter_client: MagicMock) -> list[Any]:
    """Return the commands sent to devices."""
    return [
        call.kwargs["command"]
        for call in matter_client.send_device_command.call_args_list
    ]


def _disarmed(matter_client: MagicMock) -> bool:
    """Return whether a fail-safe was disarmed."""
    return any(
        isinstance(command, Commissioning.ArmFailSafe)
        and command.expiryLengthSeconds == 0
        for command in _commands(matter_client)
    )


def _answer(
    matter_client: MagicMock, devices: Devices, answers: dict[type, Any]
) -> None:
    """Answer the given command types differently, the rest healthily."""

    async def respond(command: Any, **kwargs: Any) -> Any:
        for command_type, answer in answers.items():
            if isinstance(command, command_type):
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond


async def _migrate(
    hass: HomeAssistant, node_id: int = CONTACT_SENSOR, **data: str
) -> Any:
    """Call the single device migration."""
    return await hass.services.async_call(
        "matter",
        "migrate_thread_device",
        {"device_id": _device_id(hass, node_id), **data},
        blocking=True,
        return_response=True,
    )


async def _migrate_fleet(hass: HomeAssistant, return_response: bool = True) -> Any:
    """Call the fleet migration."""
    return await hass.services.async_call(
        "matter",
        "migrate_thread_fleet",
        {},
        blocking=True,
        return_response=return_response,
    )


@pytest.mark.usefixtures("devices")
async def test_device_is_migrated(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The device is moved under an armed fail-safe."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert await _migrate(hass) == {"result": "migrated"}

    commands = _commands(matter_client)
    assert [type(command) for command in commands] == [
        Commissioning.ArmFailSafe,
        Commands.RemoveNetwork,
        Commands.AddOrUpdateThreadNetwork,
        Commands.ConnectNetwork,
        Commissioning.CommissioningComplete,
    ]
    assert commands[0].expiryLengthSeconds == 900
    assert commands[1].networkID == PREVIOUS_ID
    assert commands[2].operationalDataset == bytes.fromhex(DATASET_1)
    assert commands[3].networkID == TARGET_ID


@pytest.mark.usefixtures("devices")
async def test_a_stored_dataset_is_picked_by_its_id(
    hass: HomeAssistant, matter_client: MagicMock, stored_dataset: str
) -> None:
    """A dataset ID moves the device to that network instead of the preferred one."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert await _migrate(hass, dataset_id=stored_dataset) == {"result": "migrated"}

    commands = _commands(matter_client)
    assert commands[2].operationalDataset == bytes.fromhex(DATASET_2)
    assert commands[3].networkID == bytes.fromhex("1111111122222233")


async def test_a_stale_cache_is_corrected_by_a_live_read(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A device whose cache names another network is not reconfigured."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    devices.networks[CONTACT_SENSOR] = TARGET_ID

    assert await _migrate(hass) == {"result": "already_on_network"}
    assert not matter_client.send_device_command.called


async def test_a_cache_naming_the_target_does_not_skip_the_move(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A cache that outlived a rolled back move does not hide the network in use."""
    await setup_integration_with_node_fixture(
        hass,
        "eve_contact_sensor",
        matter_client,
        override_attributes={"0/53/4": int.from_bytes(TARGET_ID, "big")},
    )
    devices.networks[CONTACT_SENSOR] = PREVIOUS_ID

    assert await _migrate(hass) == {"result": "migrated"}
    assert _commands(matter_client)[1].networkID == PREVIOUS_ID


async def test_the_live_network_is_removed(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """The network the device reports live is the one removed."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    devices.networks[CONTACT_SENSOR] = bytes.fromhex("0102030405060708")

    assert await _migrate(hass) == {"result": "migrated"}
    assert _commands(matter_client)[1].networkID == bytes.fromhex("0102030405060708")


@pytest.mark.usefixtures("devices")
async def test_a_failed_live_read_falls_back_to_the_cache(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device that does not answer the read is moved from its cached network."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert await _migrate(hass) == {"result": "migrated"}
    assert _commands(matter_client)[1].networkID == PREVIOUS_ID


@pytest.mark.parametrize(
    "cached",
    [
        {"0/53/4": int.from_bytes(TARGET_ID, "big")},
        {"0/53/4": NullValue, "0/49/1": []},
    ],
    ids=["target", "nothing"],
)
@pytest.mark.usefixtures("devices")
async def test_a_cache_naming_no_other_network_moves_nothing(
    hass: HomeAssistant, matter_client: MagicMock, cached: dict[str, Any]
) -> None:
    """A device that does not answer may hold a network its cache does not name."""
    await setup_integration_with_node_fixture(
        hass, "eve_contact_sensor", matter_client, override_attributes=cached
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_network_unreadable"
    assert not _commands(matter_client)


@pytest.mark.usefixtures("devices")
async def test_a_border_router_is_refused(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A border router is the network, not a device on it."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _migrate(hass, 90)

    assert exc_info.value.translation_key == "not_a_thread_device"
    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("devices")
async def test_a_device_without_a_thread_interface_is_refused(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device whose network interface is not Thread cannot be moved."""
    await setup_integration_with_node_fixture(
        hass,
        "eve_contact_sensor",
        matter_client,
        # Wi-Fi network interface
        override_attributes={"0/49/65532": 1},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "not_a_thread_device"


async def test_a_network_already_removed_is_a_rerun(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A previous network the device no longer holds does not stop the move."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    not_found = clusters.NetworkCommissioning.Enums.NetworkCommissioningStatusEnum.kNetworkIDNotFound
    _answer(
        matter_client,
        devices,
        {Commands.RemoveNetwork: {"networkingStatus": not_found}},
    )

    assert await _migrate(hass) == {"result": "migrated"}


async def test_a_lost_connect_answer_is_survived(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """The device detaches on ConnectNetwork, so its answer may never come."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    not_yet = iter([MatterError("not reachable yet")])

    async def respond(command: Any, node_id: int, **kwargs: Any) -> Any:
        if isinstance(command, Commands.ConnectNetwork):
            devices.networks[node_id] = command.networkID
            raise MatterError("switching networks")
        if isinstance(command, Commissioning.CommissioningComplete) and (
            error := next(not_yet, None)
        ):
            raise error
        return await devices.respond(command=command, node_id=node_id, **kwargs)

    matter_client.send_device_command.side_effect = respond

    assert await _migrate(hass) == {"result": "migrated"}

    # The controller is made to look the device up on the new network.
    matter_client.ping_node.assert_awaited_once_with(CONTACT_SENSOR)
    assert not _disarmed(matter_client)


async def test_a_lost_connect_the_device_never_acted_on(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A device still on its network when time runs out is disarmed, not completed."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    devices.networks[CONTACT_SENSOR] = PREVIOUS_ID
    _answer(matter_client, devices, {Commands.ConnectNetwork: MatterError("lost")})

    with (
        patch(
            "homeassistant.components.matter.thread_migration.COMPLETE_DEADLINE", 0.05
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_not_switched"
    assert _disarmed(matter_client)
    assert not any(
        isinstance(command, Commissioning.CommissioningComplete)
        for command in _commands(matter_client)
    )


@pytest.mark.parametrize(
    "answers",
    [
        {Commands.ConnectNetwork: {"networkingStatus": 9, "debugText": "no"}},
        {Commands.AddOrUpdateThreadNetwork: {"networkingStatus": 2}},
        {Commands.RemoveNetwork: MatterError("busy")},
    ],
)
async def test_a_refusal_before_the_switch_disarms(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    answers: dict[type, Any],
) -> None:
    """A step refused before the device left its network disarms the fail-safe."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    _answer(matter_client, devices, answers)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_failed"
    command = _commands(matter_client)[-1]
    assert isinstance(command, Commissioning.ArmFailSafe)
    assert command.expiryLengthSeconds == 0


async def test_a_failed_arm_sends_nothing_else(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A fail-safe the device does not arm stops the move."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    _answer(
        matter_client,
        devices,
        {Commissioning.ArmFailSafe: {"errorCode": 4, "debugText": "busy"}},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_placeholders == {
        "error": "ArmFailSafe returned error 4 busy"
    }
    assert len(_commands(matter_client)) == 1


async def test_an_unreachable_device_is_reported_not_disarmed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After ConnectNetwork, the fail-safe takes a lost device back."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    async def respond(command: Any, node_id: int, **kwargs: Any) -> Any:
        if isinstance(command, Commands.ConnectNetwork):
            # Gone from the old network, never seen on the new one
            freezer.tick(841)
            raise MatterError("gone")
        return await devices.respond(command=command, node_id=node_id, **kwargs)

    matter_client.send_device_command.side_effect = respond

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_unreachable"
    assert not _disarmed(matter_client)


async def test_one_transaction_per_node(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A move while another is under way on the device is refused."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        await release.wait()
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    first = hass.async_create_task(_migrate(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "node_reconfiguring"
    release.set()
    assert await first == {"result": "migrated"}


@pytest.mark.parametrize(
    ("action", "with_device"),
    [("migrate_thread_device", True), ("migrate_thread_fleet", False)],
)
@pytest.mark.usefixtures("devices")
async def test_the_actions_are_admin_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_read_only_user: MockUser,
    action: str,
    with_device: bool,
) -> None:
    """Only an administrator can move devices between networks."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    data = {"device_id": _device_id(hass, CONTACT_SENSOR)} if with_device else {}

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "matter",
            action,
            data,
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
            return_response=True,
        )

    assert not matter_client.send_device_command.called


@pytest.mark.usefixtures("devices")
async def test_the_fleet_is_moved_end_devices_first(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """End devices go first and border routers are left alone."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_energy_plug", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )

    response = await _migrate_fleet(hass)

    # The contact sensor is a sleepy end device, the plug a router.
    assert [entry["node_id"] for entry in response["migrated"]] == [
        CONTACT_SENSOR,
        ENERGY_PLUG,
    ]
    assert response["skipped"] == []
    assert response["failed"] == []
    arms = [
        command
        for command in _commands(matter_client)
        if isinstance(command, Commissioning.ArmFailSafe)
    ]
    assert len(arms) == 2


async def test_the_fleet_skips_moved_and_offline_devices(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """Devices on the network are skipped, offline ones reported."""
    moved = create_node_from_fixture(
        "eve_contact_sensor", {"0/53/4": int.from_bytes(TARGET_ID, "big")}
    )
    offline = create_node_from_fixture("eve_energy_plug", override_serial=True)
    offline.node_data.available = False
    await _setup_integration_with_nodes(hass, matter_client, [moved, offline])
    devices.networks[CONTACT_SENSOR] = TARGET_ID

    response = await _migrate_fleet(hass)

    assert [entry["node_id"] for entry in response["skipped"]] == [CONTACT_SENSOR]
    assert response["failed"] == [
        {"name": offline.name, "node_id": ENERGY_PLUG, "reason": "offline"}
    ]
    assert not matter_client.send_device_command.called


async def test_a_failed_end_device_holds_the_routers_back(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """Routers stay on the network an end device that failed to move depends on."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("eve_energy_plug", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )

    async def respond(command: Any, node_id: int, **kwargs: Any) -> Any:
        if node_id == CONTACT_SENSOR and isinstance(command, Commissioning.ArmFailSafe):
            return {"errorCode": 4}
        return await devices.respond(command=command, node_id=node_id, **kwargs)

    matter_client.send_device_command.side_effect = respond

    response = await _migrate_fleet(hass)

    assert response["migrated"] == []
    assert [entry["node_id"] for entry in response["failed"]] == [CONTACT_SENSOR]
    assert [entry["node_id"] for entry in response["held_back"]] == [ENERGY_PLUG]
    assert not any(
        call.kwargs["node_id"] == ENERGY_PLUG
        for call in matter_client.send_device_command.call_args_list
    )

    # Without the response, the failure is the action's.
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate_fleet(hass, return_response=False)

    assert exc_info.value.translation_key == "thread_migration_incomplete"


@pytest.mark.usefixtures("devices")
async def test_an_offline_end_device_does_not_hold_the_routers_back(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device that cannot be moved at all does not block the others."""
    offline = create_node_from_fixture("eve_contact_sensor", override_serial=True)
    offline.node_data.available = False
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [create_node_from_fixture("eve_energy_plug", override_serial=True), offline],
    )

    response = await _migrate_fleet(hass)

    assert [entry["node_id"] for entry in response["migrated"]] == [ENERGY_PLUG]
    assert [entry["reason"] for entry in response["failed"]] == ["offline"]
    assert response["held_back"] == []


@pytest.mark.usefixtures("devices")
async def test_the_leader_is_moved_last(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device without a reported role goes before the leader."""
    leader = clusters.ThreadNetworkDiagnostics.Enums.RoutingRoleEnum.kLeader
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture(
                "eve_contact_sensor", {"0/53/1": leader}, override_serial=True
            ),
            create_node_from_fixture(
                "eve_energy_plug", {"0/53/1": NullValue}, override_serial=True
            ),
        ],
    )

    response = await _migrate_fleet(hass)

    assert [entry["node_id"] for entry in response["migrated"]] == [
        ENERGY_PLUG,
        CONTACT_SENSOR,
    ]


async def test_a_device_without_thread_diagnostics_is_moved(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """The Network Commissioning networks stand in for missing diagnostics."""
    data = load_and_parse_node_fixture("eve_contact_sensor")
    data["attributes"] = {
        path: value
        for path, value in data["attributes"].items()
        if not path.startswith("0/53/")
    }
    await _setup_integration_with_nodes(
        hass, matter_client, [MatterNode(dataclass_from_dict(MatterNodeData, data))]
    )
    devices.networks[CONTACT_SENSOR] = PREVIOUS_ID

    assert await _migrate(hass) == {"result": "migrated"}

    commands = _commands(matter_client)
    assert commands[1].networkID == PREVIOUS_ID
    assert isinstance(commands[-1], Commissioning.CommissioningComplete)
    # Only the networks were read; the device has no diagnostics to read.
    assert all(
        call.args[1] == ["0/49/1"]
        for call in matter_client.read_attribute.call_args_list
    )


@pytest.mark.usefixtures("devices")
async def test_a_device_without_diagnostics_goes_by_its_cached_network(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device that does not answer goes by the network its cache holds."""
    data = load_and_parse_node_fixture("eve_contact_sensor")
    data["attributes"] = {
        path: value
        for path, value in data["attributes"].items()
        if not path.startswith("0/53/")
    }
    data["attributes"]["0/49/1"] = [{"0": b64encode(PREVIOUS_ID).decode(), "1": False}]
    await _setup_integration_with_nodes(
        hass, matter_client, [MatterNode(dataclass_from_dict(MatterNodeData, data))]
    )

    assert await _migrate(hass) == {"result": "migrated"}
    assert _commands(matter_client)[1].networkID == PREVIOUS_ID


async def test_an_undecodable_live_network_names_none(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A networks entry that does not decode names no network; the device did answer."""
    data = load_and_parse_node_fixture("eve_contact_sensor")
    data["attributes"] = {
        path: value
        for path, value in data["attributes"].items()
        if not path.startswith("0/53/")
    }
    await _setup_integration_with_nodes(
        hass, matter_client, [MatterNode(dataclass_from_dict(MatterNodeData, data))]
    )
    garbled = iter([{"0/49/1": [{"0": "%%%", "1": True}]}])

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        if (answer := next(garbled, None)) is not None:
            return answer
        return await devices.read(node_id, attribute_path)

    matter_client.read_attribute.side_effect = read

    assert await _migrate(hass) == {"result": "migrated"}
    assert isinstance(_commands(matter_client)[1], Commands.AddOrUpdateThreadNetwork)


async def test_an_unreachable_device_stays_held_until_its_fail_safe_expires(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry before the fail-safe takes the device back is refused."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    async def respond(command: Any, **kwargs: Any) -> Any:
        if isinstance(command, Commands.ConnectNetwork):
            # The deadline passes unseen on either network.
            freezer.tick(841)
            raise MatterError("gone")
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond
    with pytest.raises(HomeAssistantError):
        await _migrate(hass)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"

    freezer.tick(901)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    matter_client.send_device_command.side_effect = devices.respond
    assert await _migrate(hass) == {"result": "migrated"}


async def test_a_late_lost_arm_holds_the_device_from_its_end(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An arm may have taken until its attempt ended: the hold runs from then."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    async def respond(command: Any, **kwargs: Any) -> Any:
        if isinstance(command, Commissioning.ArmFailSafe):
            freezer.tick(100)
            raise MatterError("lost")
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond
    with pytest.raises(HomeAssistantError):
        await _migrate(hass)

    matter_client.send_device_command.side_effect = devices.respond
    freezer.tick(850)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"

    freezer.tick(51)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert await _migrate(hass) == {"result": "migrated"}


def _complete_with(
    matter_client: MagicMock, devices: Devices, answers: list[Any]
) -> None:
    """Answer the completions with these, in turn, the rest healthily."""
    completions = iter(answers)

    async def respond(command: Any, **kwargs: Any) -> Any:
        if isinstance(command, Commissioning.CommissioningComplete):
            answer = next(completions)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond


async def test_a_lost_completion_answer_is_recognized(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """NoFailSafe after an unanswered completion means it was committed."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    _complete_with(matter_client, devices, [MatterError("lost"), {"errorCode": 3}])

    assert await _migrate(hass) == {"result": "migrated"}


async def test_no_fail_safe_without_a_lost_answer_fails(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """Without an unanswered completion, NoFailSafe is a failure."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    _complete_with(matter_client, devices, [{"errorCode": 3}])

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_failed"


async def test_one_fleet_migration_at_a_time(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A second fleet run, or a single move, waits for the first run."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("eve_energy_plug", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        await release.wait()
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    fleet = hass.async_create_task(_migrate_fleet(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate_fleet(hass)
    assert exc_info.value.translation_key == "thread_migration_running"
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass, ENERGY_PLUG)
    assert exc_info.value.translation_key == "thread_migration_running"

    release.set()
    response = await fleet
    assert [entry["node_id"] for entry in response["migrated"]] == [
        CONTACT_SENSOR,
        ENERGY_PLUG,
    ]


async def test_a_migration_ends_with_the_entry(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """Unloading Matter cancels a move under way and frees the device."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    entry = hass.config_entries.async_entries("matter")[0]
    release = asyncio.Event()

    async def slow(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        await release.wait()
        return await devices.read(node_id, attribute_path)

    # Still reading the device's network: nothing has been sent.
    matter_client.read_attribute.side_effect = slow
    move = hass.async_create_task(_migrate(hass))
    while not matter_client.read_attribute.called:
        await asyncio.sleep(0)

    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(HomeAssistantError) as exc_info:
        await move
    assert exc_info.value.translation_key == "matter_unloaded"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    matter_client.read_attribute.side_effect = devices.read
    assert await _migrate(hass) == {"result": "migrated"}


async def test_a_migration_cancelled_while_arming_holds_the_device(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """An arm whose answer never came may have taken: the device stays held."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    entry = hass.config_entries.async_entries("matter")[0]
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        await release.wait()
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    move = hass.async_create_task(_migrate(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(HomeAssistantError):
        await move

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    matter_client.send_device_command.side_effect = devices.respond
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"


async def test_no_fleet_run_while_a_device_is_moved(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A fleet run waits for a single move under way."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        await release.wait()
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    move = hass.async_create_task(_migrate(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate_fleet(hass)

    assert exc_info.value.translation_key == "node_reconfiguring"
    release.set()
    assert await move == {"result": "migrated"}


@pytest.mark.parametrize(
    "answers",
    [
        # Completion refused outright
        {Commissioning.CommissioningComplete: {"errorCode": 1}},
        # Staging refused, and the rollback too
        {
            Commands.AddOrUpdateThreadNetwork: {"networkingStatus": 2},
            Commissioning.ArmFailSafe: None,
        },
    ],
    ids=["completion-refused", "rollback-refused"],
)
async def test_an_armed_device_stays_held(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    answers: dict[type, Any],
) -> None:
    """A device whose fail-safe may still be armed is held until it expires."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    disarms = iter([{"errorCode": 0}, {"errorCode": 4}])

    async def respond(command: Any, **kwargs: Any) -> Any:
        if (
            isinstance(command, Commissioning.ArmFailSafe)
            and Commissioning.ArmFailSafe in answers
        ):
            return next(disarms)
        for command_type, answer in answers.items():
            if isinstance(command, command_type) and answer is not None:
                return answer
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond
    with pytest.raises(HomeAssistantError):
        await _migrate(hass)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "node_reconfiguring"


async def test_a_stored_target_the_device_is_not_on_is_not_skipped(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A network entry the device holds without being attached to it is no move done."""
    data = load_and_parse_node_fixture("eve_contact_sensor")
    data["attributes"] = {
        path: value
        for path, value in data["attributes"].items()
        if not path.startswith("0/53/")
    }
    await _setup_integration_with_nodes(
        hass, matter_client, [MatterNode(dataclass_from_dict(MatterNodeData, data))]
    )
    attached = False

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        return {"0/49/1": [{"0": b64encode(TARGET_ID).decode(), "1": attached}]}

    async def respond(command: Any, **kwargs: Any) -> Any:
        nonlocal attached
        if isinstance(command, Commands.ConnectNetwork):
            attached = True
        if isinstance(
            command, (Commissioning.ArmFailSafe, Commissioning.CommissioningComplete)
        ):
            return {"errorCode": 0}
        return {"networkingStatus": 0}

    matter_client.read_attribute.side_effect = read
    matter_client.send_device_command.side_effect = respond

    assert await _migrate(hass) == {"result": "migrated"}
    # The entry is the target already: nothing to remove.
    assert not any(
        isinstance(command, Commands.RemoveNetwork)
        for command in _commands(matter_client)
    )


async def test_a_device_answering_without_a_network_does_not_go_by_the_cache(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """The cache stands in only for a device that does not answer."""
    await setup_integration_with_node_fixture(
        hass,
        "eve_contact_sensor",
        matter_client,
        override_attributes={"0/53/4": int.from_bytes(TARGET_ID, "big")},
    )
    first = iter([{"0/53/4": None, "0/49/1": []}])

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        if (answer := next(first, None)) is not None:
            return answer
        return await devices.read(node_id, attribute_path)

    matter_client.read_attribute.side_effect = read

    assert await _migrate(hass) == {"result": "migrated"}


@pytest.mark.parametrize(
    "networks",
    [[{"0": b64encode(TARGET_ID).decode(), "1": False}], []],
    ids=["not-connected", "none"],
)
async def test_a_target_held_but_not_connected_is_no_move_done(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    networks: list[dict[str, Any]],
) -> None:
    """Diagnostics name a network held while detached; the networks tell if connected."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    held = {"0/53/4": int.from_bytes(TARGET_ID, "big"), "0/49/1": networks}
    first = iter([held])

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        if (answer := next(first, None)) is not None:
            return answer
        return await devices.read(node_id, attribute_path)

    matter_client.read_attribute.side_effect = read

    assert await _migrate(hass) == {"result": "migrated"}
    commands = _commands(matter_client)
    assert not any(isinstance(command, Commands.RemoveNetwork) for command in commands)
    assert any(isinstance(command, Commands.ConnectNetwork) for command in commands)


async def test_a_failed_router_holds_back_its_tier(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """Another router may be the failed one's way out: it stays too."""
    router = clusters.ThreadNetworkDiagnostics.Enums.RoutingRoleEnum.kRouter
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("eve_energy_plug", override_serial=True),
            create_node_from_fixture(
                "eve_contact_sensor", {"0/53/1": router}, override_serial=True
            ),
        ],
    )

    async def respond(command: Any, node_id: int, **kwargs: Any) -> Any:
        if node_id == CONTACT_SENSOR and isinstance(command, Commissioning.ArmFailSafe):
            return {"errorCode": 4}
        return await devices.respond(command=command, node_id=node_id, **kwargs)

    matter_client.send_device_command.side_effect = respond

    response = await _migrate_fleet(hass)

    assert [(entry["node_id"], entry["reason"]) for entry in response["failed"]] == [
        (CONTACT_SENSOR, "thread_migration_failed")
    ]
    assert [entry["node_id"] for entry in response["held_back"]] == [ENERGY_PLUG]


@pytest.mark.usefixtures("devices")
async def test_a_device_of_unknown_role_goes_after_the_end_devices(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device that may be a router waits for the end devices that may depend on it."""
    sleepy = clusters.ThreadNetworkDiagnostics.Enums.RoutingRoleEnum.kSleepyEndDevice
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture(
                "eve_contact_sensor", {"0/53/1": NullValue}, override_serial=True
            ),
            create_node_from_fixture(
                "eve_energy_plug", {"0/53/1": sleepy}, override_serial=True
            ),
        ],
    )

    response = await _migrate_fleet(hass)

    assert [entry["node_id"] for entry in response["migrated"]] == [
        ENERGY_PLUG,
        CONTACT_SENSOR,
    ]


@pytest.mark.usefixtures("devices")
async def test_no_move_while_a_network_change_is_pending(
    hass: HomeAssistant, matter_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A pending dataset written here may move the network under the device."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )
    await hass.services.async_call(
        "matter",
        "push_thread_dataset",
        {"device_id": _device_id(hass, 90)},
        blocking=True,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "thread_network_change_pending"
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate_fleet(hass)
    assert exc_info.value.translation_key == "thread_network_change_pending"

    freezer.tick(301)
    async_fire_time_changed(hass)
    assert await _migrate(hass) == {"result": "migrated"}


async def test_no_network_change_while_a_device_is_moved(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A border router's network is not changed under a device being moved."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        await release.wait()
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    move = hass.async_create_task(_migrate(hass))
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": _device_id(hass, 90)},
            blocking=True,
        )

    assert exc_info.value.translation_key == "thread_network_busy"
    release.set()
    assert await move == {"result": "migrated"}


async def test_no_move_while_a_pending_write_is_in_flight(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """The network change counts from before the write, whatever answers it."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        if isinstance(
            command,
            clusters.ThreadBorderRouterManagement.Commands.SetPendingDatasetRequest,
        ):
            await release.wait()
            raise MatterError("lost")
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    push = hass.async_create_task(
        hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": _device_id(hass, 90)},
            blocking=True,
        )
    )
    while not matter_client.send_device_command.called:
        await asyncio.sleep(0)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "thread_network_change_pending"

    # An answer that never came may still mean a write that took.
    release.set()
    with pytest.raises(HomeAssistantError):
        await push
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "thread_network_change_pending"


async def test_no_completion_after_the_deadline(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A read that outlasts the deadline is not followed by a completion."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    reads = 0

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        nonlocal reads
        reads += 1
        if reads > 1:
            # On the new network, but only after the deadline has passed
            await asyncio.sleep(0.2)
        return await devices.read(node_id, attribute_path)

    matter_client.read_attribute.side_effect = read

    with (
        patch(
            "homeassistant.components.matter.thread_migration.COMPLETE_DEADLINE", 0.05
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_unreachable"
    assert not any(
        isinstance(command, Commissioning.CommissioningComplete)
        for command in _commands(matter_client)
    )


@pytest.mark.usefixtures("devices")
async def test_no_second_network_change_while_one_is_pending(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A router may not report a change written through another one yet."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [create_node_from_fixture("thread_border_router", override_serial=True)],
    )

    async def push() -> None:
        await hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": _device_id(hass, 90)},
            blocking=True,
        )

    await push()

    with pytest.raises(HomeAssistantError) as exc_info:
        await push()
    assert exc_info.value.translation_key == "thread_network_change_pending"


async def test_the_network_change_runs_from_when_the_write_is_done(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A slow write keeps moves off for the whole delay after it."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )

    async def slow(command: Any, **kwargs: Any) -> Any:
        if isinstance(
            command,
            clusters.ThreadBorderRouterManagement.Commands.SetPendingDatasetRequest,
        ):
            # Longer than the whole delay below
            await asyncio.sleep(0.15)
            return None
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    with patch(
        "homeassistant.components.matter.thread_border_router.PENDING_DATASET_DELAY",
        100,
    ):
        await hass.services.async_call(
            "matter",
            "push_thread_dataset",
            {"device_id": _device_id(hass, 90)},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)
    assert exc_info.value.translation_key == "thread_network_change_pending"


async def test_no_move_while_a_network_change_is_written(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A write outlasting the delay keeps moves off until it is done."""
    await _setup_integration_with_nodes(
        hass,
        matter_client,
        [
            create_node_from_fixture("thread_border_router", override_serial=True),
            create_node_from_fixture("eve_contact_sensor", override_serial=True),
        ],
    )
    sent = asyncio.Event()
    release = asyncio.Event()

    async def slow(command: Any, **kwargs: Any) -> Any:
        if isinstance(
            command,
            clusters.ThreadBorderRouterManagement.Commands.SetPendingDatasetRequest,
        ):
            sent.set()
            await release.wait()
            return None
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = slow
    with patch(
        "homeassistant.components.matter.thread_border_router.PENDING_DATASET_DELAY",
        100,
    ):
        push = hass.async_create_task(
            hass.services.async_call(
                "matter",
                "push_thread_dataset",
                {"device_id": _device_id(hass, 90)},
                blocking=True,
            )
        )
        await sent.wait()
        # Longer than the whole delay
        await asyncio.sleep(0.15)

        with pytest.raises(HomeAssistantError) as exc_info:
            await _migrate(hass)
        assert exc_info.value.translation_key == "thread_network_change_pending"

        release.set()
        await push


async def test_no_switch_once_staging_took_the_deadline(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A switch that could no longer be completed is not started; the device reverts."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    async def respond(command: Any, **kwargs: Any) -> Any:
        if isinstance(command, Commands.AddOrUpdateThreadNetwork):
            freezer.tick(841)
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_not_switched"
    assert not any(
        isinstance(command, Commands.ConnectNetwork)
        for command in _commands(matter_client)
    )
    assert _disarmed(matter_client)


@pytest.mark.parametrize(("limit", "window"), [(300, 280), (60, 56)])
async def test_the_fail_safe_fits_the_device_limit(
    hass: HomeAssistant,
    matter_client: MagicMock,
    devices: Devices,
    freezer: FrozenDateTimeFactory,
    limit: int,
    window: int,
) -> None:
    """A device ends a fail-safe at its cumulative limit: arm and deadline fit it."""
    await setup_integration_with_node_fixture(
        hass,
        "eve_contact_sensor",
        matter_client,
        override_attributes={"0/48/1": {"0": 60, "1": limit}},
    )

    async def respond(command: Any, **kwargs: Any) -> Any:
        if isinstance(command, Commands.AddOrUpdateThreadNetwork):
            freezer.tick(window + 1)
        return await devices.respond(command=command, **kwargs)

    matter_client.send_device_command.side_effect = respond
    with pytest.raises(HomeAssistantError) as exc_info:
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_not_switched"
    assert _commands(matter_client)[0].expiryLengthSeconds == limit


@pytest.mark.usefixtures("devices")
async def test_a_short_device_limit_leaves_time_to_complete(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A device allowing only a minute's fail-safe can still be moved."""
    await setup_integration_with_node_fixture(
        hass,
        "eve_contact_sensor",
        matter_client,
        override_attributes={"0/48/1": {"0": 60, "1": 60}},
    )

    assert await _migrate(hass) == {"result": "migrated"}


async def test_an_unanswered_completion_is_reported_unconfirmed(
    hass: HomeAssistant, matter_client: MagicMock, devices: Devices
) -> None:
    """A device on the new network whose completion went unanswered may have committed."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    _answer(
        matter_client,
        devices,
        {Commissioning.CommissioningComplete: MatterError("lost")},
    )

    with (
        patch(
            "homeassistant.components.matter.thread_migration.COMPLETE_DEADLINE", 0.05
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _migrate(hass)

    assert exc_info.value.translation_key == "thread_migration_unconfirmed"
    assert not _disarmed(matter_client)
