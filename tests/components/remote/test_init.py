"""The tests for the Remote component, adapted from Light Test."""

import pytest

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import (
    async_mock_service,
    help_test_all,
    import_and_test_deprecated_constant_enum,
)

TEST_PLATFORM = {DOMAIN: {CONF_PLATFORM: "test"}}
SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_DELETE_COMMAND = "delete_command"
ENTITY_ID = "entity_id_val"


async def test_is_on(hass: HomeAssistant) -> None:
    """Test is_on."""
    hass.states.async_set("remote.test", STATE_ON)
    assert remote.is_on(hass, "remote.test")

    hass.states.async_set("remote.test", STATE_OFF)
    assert not remote.is_on(hass, "remote.test")


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn_on."""
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID})

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    call = turn_on_calls[-1]

    assert call.domain == DOMAIN


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn_off."""
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}
    )

    await hass.async_block_till_done()

    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_send_command(hass: HomeAssistant) -> None:
    """Test send_command."""
    send_command_calls = async_mock_service(hass, DOMAIN, SERVICE_SEND_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
        ATTR_NUM_REPEATS: "4",
        ATTR_DELAY_SECS: "0.6",
    }

    await hass.services.async_call(DOMAIN, SERVICE_SEND_COMMAND, data)

    await hass.async_block_till_done()

    assert len(send_command_calls) == 1
    call = send_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_SEND_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_learn_command(hass: HomeAssistant) -> None:
    """Test learn_command."""
    learn_command_calls = async_mock_service(hass, DOMAIN, SERVICE_LEARN_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
        ATTR_COMMAND_TYPE: "rf",
        ATTR_ALTERNATIVE: True,
        ATTR_TIMEOUT: 20,
    }
    await hass.services.async_call(DOMAIN, SERVICE_LEARN_COMMAND, data)

    await hass.async_block_till_done()

    assert len(learn_command_calls) == 1
    call = learn_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_LEARN_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_delete_command(hass: HomeAssistant) -> None:
    """Test delete_command."""
    delete_command_calls = async_mock_service(
        hass, remote.DOMAIN, SERVICE_DELETE_COMMAND
    )

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
    }

    await hass.services.async_call(DOMAIN, SERVICE_DELETE_COMMAND, data)

    await hass.async_block_till_done()

    assert len(delete_command_calls) == 1
    call = delete_command_calls[-1]

    assert call.domain == remote.DOMAIN
    assert call.service == SERVICE_DELETE_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(remote)


@pytest.mark.parametrize(("enum"), list(remote.RemoteEntityFeature))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: remote.RemoteEntityFeature,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(caplog, remote, enum, "SUPPORT_", "2025.1")


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockRemote(remote.RemoteEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockRemote()
    assert entity.supported_features_compat is remote.RemoteEntityFeature(1)
    assert "MockRemote" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "RemoteEntityFeature.LEARN_COMMAND" in caplog.text
    caplog.clear()
    assert entity.supported_features_compat is remote.RemoteEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text
