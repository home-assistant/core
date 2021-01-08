"""Test the iRobot Roomba config flow."""
from roombapy import RoombaConnectionError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.roomba.const import (
    CONF_BLID,
    CONF_CONTINUOUS,
    CONF_DELAY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_HOST: "1.2.3.4", CONF_BLID: "blid", CONF_PASSWORD: "password"}

VALID_YAML_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_BLID: "blid",
    CONF_PASSWORD: "password",
    CONF_CONTINUOUS: True,
    CONF_DELAY: 1,
}


def _create_mocked_roomba(
    roomba_connected=None, master_state=None, connect=None, disconnect=None
):
    mocked_roomba = MagicMock()
    type(mocked_roomba).roomba_connected = PropertyMock(return_value=roomba_connected)
    type(mocked_roomba).master_state = PropertyMock(return_value=master_state)
    type(mocked_roomba).connect = MagicMock(side_effect=connect)
    type(mocked_roomba).disconnect = MagicMock(side_effect=disconnect)
    return mocked_roomba


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.Roomba",
        return_value=mocked_roomba,
    ), patch(
        "homeassistant.components.roomba.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roomba.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "myroomba"

    assert result2["result"].unique_id == "blid"
    assert result2["data"] == {
        CONF_BLID: "blid",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: "1.2.3.4",
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_roomba = _create_mocked_roomba(
        connect=RoombaConnectionError,
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "myroomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.Roomba",
        return_value=mocked_roomba,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_import(hass):
    """Test we can import yaml config."""

    mocked_roomba = _create_mocked_roomba(
        roomba_connected=True,
        master_state={"state": {"reported": {"name": "imported_roomba"}}},
    )

    with patch(
        "homeassistant.components.roomba.config_flow.Roomba",
        return_value=mocked_roomba,
    ), patch(
        "homeassistant.components.roomba.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roomba.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=VALID_YAML_CONFIG.copy(),
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == "blid"
    assert result["title"] == "imported_roomba"
    assert result["data"] == {
        CONF_BLID: "blid",
        CONF_CONTINUOUS: True,
        CONF_DELAY: 1,
        CONF_HOST: "1.2.3.4",
        CONF_PASSWORD: "password",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_dupe(hass):
    """Test we get abort on duplicate import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, unique_id="blid")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=VALID_YAML_CONFIG.copy(),
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
