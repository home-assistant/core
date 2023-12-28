"""Tests for tedee lock."""
from unittest.mock import MagicMock

from pytedee_async.exception import (
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.components.tedee.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_lock(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tedee lock."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot
    assert entry.device_id

    device = device_registry.async_get(entry.device_id)
    assert device == snapshot

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.lock.mock_calls) == 1
    mock_tedee.lock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_LOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.unlock.mock_calls) == 1
    mock_tedee.unlock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_UNLOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.open.mock_calls) == 1
    mock_tedee.open.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_errors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
) -> None:
    """Test event errors."""
    mock_tedee.lock.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError, match="Failed to lock the door. Lock 12345"):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )

    mock_tedee.unlock.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlock the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )

    mock_tedee.open.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlatch the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )


async def test_lock_without_pullspring(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tedee lock without pullspring."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_2c3d")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-2C3D"
    assert state.state == STATE_UNLOCKED

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "98765-lock"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "98765")}
    assert device.manufacturer == "Tedee"
    assert device.name == "Lock-2C3D"
    assert device.model == "Tedee GO"

    with pytest.raises(
        HomeAssistantError,
        match="Entity lock.lock_2c3d does not support this service.",
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_2c3d",
            },
            blocking=True,
        )

    assert len(mock_tedee.open.mock_calls) == 0


@pytest.mark.parametrize(
    ("side_effect", "result_exception", "reason"),
    [
        (
            TedeeClientException("Boom."),
            UpdateFailed,
            "Querying API failed. Error: Boom.",
        ),
        (
            TedeeLocalAuthException(""),
            ConfigEntryError,
            "Authentication failed. Local access token is invalid",
        ),
        (
            TedeeDataUpdateException("Boom."),
            UpdateFailed,
            "Error while updating data: Boom.",
        ),
        (TimeoutError("Boom."), UpdateFailed, "Querying API failed. Error: Boom."),
    ],
)
async def test_coordinator_data_update_failures(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    result_exception: type,
    reason: str,
) -> None:
    """Test coordinator data update fails."""
    mock_tedee.sync.side_effect = side_effect
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    with pytest.raises(result_exception) as exc:
        await coordinator._async_update_data()
    assert str(exc.value) == reason

    mock_tedee.get_locks.side_effect = side_effect
    with pytest.raises(result_exception) as exc:
        await coordinator._async_update_data()
    assert str(exc.value) == reason


async def test_coordinator_no_locks(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator no locks."""
    mock_tedee.locks_dict = {}
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    with pytest.raises(UpdateFailed) as exc:
        await coordinator._async_update_data()
    assert str(exc.value) == "No locks found in your account"
