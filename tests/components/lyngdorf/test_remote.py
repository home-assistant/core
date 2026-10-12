"""Tests for the Lyngdorf remote platform."""

from unittest.mock import MagicMock, patch

from lyngdorf import LyngdorfModel
from lyngdorf.exceptions import LyngdorfUnsupportedError
from lyngdorf.remote import RemoteKey, resolve_remote_key
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

REMOTE = "remote.mock_lyngdorf"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the remote platform."""
    return [Platform.REMOTE]


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the remote entity."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_send_command(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test sending a sequence of remote keys."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: REMOTE,
            ATTR_COMMAND: [RemoteKey.MENU, RemoteKey.DOWN, RemoteKey.ENTER],
        },
        blocking=True,
    )

    mock_receiver.remote.send.assert_awaited_once_with(
        [RemoteKey.MENU, RemoteKey.DOWN, RemoteKey.ENTER], num_repeats=1
    )


@pytest.mark.usefixtures("init_integration")
async def test_send_command_repeats(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test the repeat count is passed through to the library."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: REMOTE,
            ATTR_COMMAND: [RemoteKey.DOWN],
            ATTR_NUM_REPEATS: 3,
        },
        blocking=True,
    )

    mock_receiver.remote.send.assert_awaited_once_with([RemoteKey.DOWN], num_repeats=3)


@pytest.mark.usefixtures("init_integration")
async def test_send_unsupported_command(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test a key the model does not have is reported to the user."""
    mock_receiver.remote.send.side_effect = LyngdorfUnsupportedError("no such key")

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: REMOTE, ATTR_COMMAND: ["nonsense"]},
            blocking=True,
        )

    assert err.value.translation_key == "unsupported_remote_key"
    # Every key named in the message must be one the library will accept.
    listed = err.value.translation_placeholders["keys"].split(", ")
    assert listed
    assert all(resolve_remote_key(key) is not None for key in listed)


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    service: str,
    expected: bool,
) -> None:
    """Test turning the device on and off from the remote."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: REMOTE},
        blocking=True,
    )

    mock_receiver.set_power.assert_awaited_once_with(expected)


@pytest.mark.usefixtures("mock_receiver")
async def test_no_entity_for_model_without_remote_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no remote entity is created for a model with no remote keys."""
    mock_receiver.remote = None
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lyngdorf.lookup_model",
            return_value=LyngdorfModel.TDAI_3400,
        ),
        patch("homeassistant.components.lyngdorf.PLATFORMS", [Platform.REMOTE]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(REMOTE) is None
    assert entity_registry.async_get(REMOTE) is None
