"""Test the UPB Control config flow."""

import asyncio

from asynctest import MagicMock, PropertyMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.upb.const import DOMAIN


def upb_lib_connect(callback):
    """Mock UPB connect."""
    callback()


def mock_upb(sync_complete=True):
    """Mock UPB lib."""
    mocked_upb = MagicMock()
    type(mocked_upb).network_id = PropertyMock(return_value="42")
    if sync_complete:
        mocked_upb.connect.side_effect = upb_lib_connect
    return mocked_upb


async def test_form_user_with_serial_upb(hass):
    """Test we can setup a serial upb."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mocked_upb = mock_upb()

    with patch(
        "homeassistant.components.upb.config_flow.upb_lib.UpbPim",
        return_value=mocked_upb,
    ), patch(
        "homeassistant.components.upb.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.upb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "Serial port",
                "address": "/dev/ttyS0:115200",
                "file_path": "upb.upe",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "UPB"
    assert result2["data"] == {
        "host": "serial:///dev/ttyS0:115200",
        "file_path": "upb.upe",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_tcp_upb(hass):
    """Test we can setup a TCP upb."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mocked_upb = mock_upb()

    with patch(
        "homeassistant.components.upb.config_flow.upb_lib.UpbPim",
        return_value=mocked_upb,
    ), patch(
        "homeassistant.components.upb.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.upb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"protocol": "TCP", "address": "1.2.3.4", "file_path": "upb.upe"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "UPB"
    assert result2["data"] == {"host": "tcp://1.2.3.4", "file_path": "upb.upe"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_upb = mock_upb(sync_complete=False)

    with patch(
        "homeassistant.components.upb.config_flow.upb_lib.UpbPim",
        return_value=mocked_upb,
    ), patch(
        "homeassistant.components.upb.config_flow.async_timeout.timeout",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"protocol": "TCP", "address": "1.2.3.4", "file_path": "upb.upe"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_missing_file(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_upb = mock_upb(sync_complete=False)
    type(mocked_upb).config_ok = PropertyMock(return_value=False)

    with patch(
        "homeassistant.components.upb.config_flow.upb_lib.UpbPim",
        return_value=mocked_upb,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"protocol": "TCP", "address": "1.2.3.4", "file_path": "upb.upe"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_upb_file"}
