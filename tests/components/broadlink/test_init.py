"""The tests for the broadlink component."""
from base64 import b64decode
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant.components.broadlink import async_setup_service, data_packet
from homeassistant.components.broadlink.const import DOMAIN, SERVICE_LEARN, SERVICE_SEND
from homeassistant.util.dt import utcnow

DUMMY_IR_PACKET = (
    "JgBGAJKVETkRORA6ERQRFBEUERQRFBE5ETkQOhAVEBUQFREUEBUQ"
    "OhEUERQRORE5EBURFBA6EBUQOhE5EBUQFRA6EDoRFBEADQUAAA=="
)
DUMMY_HOST = "192.168.0.2"


@pytest.fixture(autouse=True)
def dummy_broadlink():
    """Mock broadlink module so we don't have that dependency on tests."""
    broadlink = MagicMock()
    with patch.dict("sys.modules", {"broadlink": broadlink}):
        yield broadlink


async def test_padding(hass):
    """Verify that non padding strings are allowed."""
    assert data_packet("Jg") == b"&"
    assert data_packet("Jg=") == b"&"
    assert data_packet("Jg==") == b"&"


async def test_send(hass):
    """Test send service."""
    mock_device = MagicMock()
    mock_device.send_data.return_value = None

    async_setup_service(hass, DUMMY_HOST, mock_device)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_SEND, {"host": DUMMY_HOST, "packet": (DUMMY_IR_PACKET)}
    )
    await hass.async_block_till_done()

    assert mock_device.send_data.call_count == 1
    assert mock_device.send_data.call_args == call(b64decode(DUMMY_IR_PACKET))


async def test_learn(hass):
    """Test learn service."""
    mock_device = MagicMock()
    mock_device.enter_learning.return_value = None
    mock_device.check_data.return_value = b64decode(DUMMY_IR_PACKET)

    with patch.object(
        hass.components.persistent_notification, "async_create"
    ) as mock_create:

        async_setup_service(hass, DUMMY_HOST, mock_device)
        await hass.async_block_till_done()

        await hass.services.async_call(DOMAIN, SERVICE_LEARN, {"host": DUMMY_HOST})
        await hass.async_block_till_done()

        assert mock_device.enter_learning.call_count == 1
        assert mock_device.enter_learning.call_args == call()

        assert mock_create.call_count == 1
        assert mock_create.call_args == call(
            f"Received packet is: {DUMMY_IR_PACKET}", title="Broadlink switch"
        )


async def test_learn_timeout(hass):
    """Test learn service."""
    mock_device = MagicMock()
    mock_device.enter_learning.return_value = None
    mock_device.check_data.return_value = None

    async_setup_service(hass, DUMMY_HOST, mock_device)
    await hass.async_block_till_done()

    now = utcnow()

    with patch.object(
        hass.components.persistent_notification, "async_create"
    ) as mock_create, patch("homeassistant.components.broadlink.utcnow") as mock_utcnow:

        mock_utcnow.side_effect = [now, now + timedelta(20)]

        await hass.services.async_call(DOMAIN, SERVICE_LEARN, {"host": DUMMY_HOST})
        await hass.async_block_till_done()

        assert mock_device.enter_learning.call_count == 1
        assert mock_device.enter_learning.call_args == call()

        assert mock_create.call_count == 1
        assert mock_create.call_args == call(
            "No signal was received", title="Broadlink switch"
        )
