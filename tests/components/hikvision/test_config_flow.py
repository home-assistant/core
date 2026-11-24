"""Test the Hikvision config flow."""

from unittest.mock import MagicMock, patch
import uuid

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import CONF_RANDOM_ID, DOMAIN
from homeassistant.components.hikvision.identity import looks_made_up
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import TextSelector, TextSelectorType
from homeassistant.helpers.translation import async_get_translations

from . import setup_integration
from .conftest import (
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USERNAME,
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test we get the form and can create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == TEST_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_RANDOM_ID: False,
    }

    # Certificate verification defaults to on; it is unused over plain HTTP
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle cannot connect error and can recover."""
    mock_hikcamera.return_value.get_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_exception(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test we handle exception during connection and can recover."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_unknown_exception(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle unknown exception during connection and can recover."""
    mock_hikcamera.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_hikcamera: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured devices."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("form", "verify_ssl"),
    [
        pytest.param({}, True, id="verified_by_default"),
        pytest.param({CONF_VERIFY_SSL: True}, True, id="verified"),
        pytest.param({CONF_VERIFY_SSL: False}, False, id="unverified"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_with_ssl(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    form: dict[str, bool],
    verify_ssl: bool,
) -> None:
    """Test the user flow passes HTTPS and the certificate choice to HikCamera."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: True,
            **form,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    assert result["result"].unique_id == TEST_DEVICE_ID
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, verify_ssl
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_invalid_auth(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test a rejected password is reported as such, and the user can recover."""
    mock_hikcamera.return_value.get_id = None
    mock_hikcamera.return_value.auth_failed = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    user_input = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.auth_failed = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the stored credentials can be replaced."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"name": mock_config_entry.title}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new-user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    # The rest of the entry is unchanged.
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST
    assert mock_config_entry.data[CONF_PORT] == TEST_PORT
    # The new credentials are what the device was asked to accept.
    assert mock_hikcamera.call_args.args[2:4] == ("new-user", "new-password")


async def test_reauth_form_does_not_show_the_stored_password(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the form offers the stored username, but never the stored password."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    fields = {str(key): key for key in result["data_schema"].schema}
    assert fields[CONF_USERNAME].default() == TEST_USERNAME
    password = fields[CONF_PASSWORD]
    assert password.default is probatio.UNDEFINED
    assert not (password.description or {}).get("suggested_value")


async def test_reauth_success_message_comes_from_home_assistant(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reason the reauthentication ends with has a text to show.

    Home Assistant translates it, so the integration does not repeat it in its
    strings.json (core's translation check refuses the duplicate).
    """
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["reason"] == "reauth_successful"
    assert result["translation_domain"] == "homeassistant"
    translations = await async_get_translations(hass, "en", "config", ["homeassistant"])
    assert translations["component.homeassistant.config.abort.reauth_successful"]


async def test_reauth_flow_keeps_the_certificate_setting(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication connects the way the entry was set up."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SSL: True, CONF_VERIFY_SSL: False},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_hikcamera.assert_called_with(
        f"https://{TEST_HOST}", TEST_PORT, "new-user", "new-password", False
    )


@pytest.mark.parametrize(
    ("get_id", "auth_failed", "side_effect", "error"),
    [
        (None, True, None, "invalid_auth"),
        (None, False, None, "cannot_connect"),
        (TEST_DEVICE_ID, False, requests.exceptions.ConnectionError, "cannot_connect"),
        (TEST_DEVICE_ID, False, RuntimeError, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    get_id: str | None,
    auth_failed: bool,
    side_effect: type[Exception] | None,
    error: str,
) -> None:
    """Test reauthentication reports why the credentials were not accepted."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)
    user_input = {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "wrong"}

    mock_hikcamera.return_value.get_id = get_id
    mock_hikcamera.return_value.auth_failed = auth_failed
    mock_hikcamera.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    # Recover from the error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.auth_failed = False
    mock_hikcamera.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "right"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "right"


_DERIVED_ID = uuid.uuid5(uuid.NAMESPACE_URL, "serialNumber:sn1")


@pytest.mark.parametrize(
    ("stored_unique_id", "returned_id", "reason"),
    [
        # An entry made with a random ID cannot be checked.
        (str(uuid.uuid4()), uuid.uuid4(), "reauth_successful"),
        # A derived ID is stable: the same one is the same device...
        (str(_DERIVED_ID), _DERIVED_ID, "reauth_successful"),
        # ...another derived one, or a random one, is not.
        (
            str(_DERIVED_ID),
            uuid.uuid5(uuid.NAMESPACE_URL, "serialNumber:sn2"),
            "wrong_device",
        ),
        (str(_DERIVED_ID), uuid.uuid4(), "wrong_device"),
        # A real device ID, and a real one that is a UUID: still checked.
        (TEST_DEVICE_ID, uuid.uuid4(), "wrong_device"),
        ("88cbe8b2-6b7b-11b2-8094-c056e3e9a4c2", uuid.uuid4(), "wrong_device"),
    ],
    ids=[
        "random",
        "same_derived",
        "other_derived",
        "derived_then_random",
        "real_id",
        "real_uuid_id",
    ],
)
async def test_reauth_flow_device_with_a_made_up_id(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    stored_unique_id: str,
    returned_id: uuid.UUID,
    reason: str,
) -> None:
    """Test only an entry with a random ID made up by pyHik skips the device check.

    pyHik before 0.5.1 makes up a random UUID for a device whose own ID is too
    short, a new one at every connection: an entry made with one cannot be checked.
    The stable ID later versions derive is checked like a real one.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=stored_unique_id
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_hikcamera.return_value.get_id = returned_id
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    saved = reason == "reauth_successful"
    assert (mock_config_entry.data[CONF_PASSWORD] == "new-password") is saved
    assert mock_config_entry.unique_id == stored_unique_id


async def test_device_with_a_made_up_id_set_up_and_reauthenticated(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test a device whose ID pyHik makes up, from the user flow to reauthentication.

    pyHik gives that ID as a UUID object. The entry stores it as a string, and its
    credentials can be replaced while the device answers with another made-up ID.
    """
    made_up = uuid.uuid4()
    mock_hikcamera.return_value.get_id = made_up
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == str(made_up)
    assert entry.data[CONF_RANDOM_ID] is True

    entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.get_id = uuid.uuid4()
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("stored_unique_id", "made_up"),
    [(uuid.uuid4(), True), (uuid.uuid5(uuid.NAMESPACE_URL, "macAddress:aa"), False)],
)
def test_a_made_up_id_kept_as_a_uuid_object_is_recognised(
    stored_unique_id: uuid.UUID, made_up: bool
) -> None:
    """Test an entry that kept pyHik's UUID object is still recognised as made up.

    Only a random one is: a derived one is checked like any other.
    """
    assert looks_made_up(stored_unique_id) is made_up


async def test_reauth_flow_wrong_device(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the credentials cannot be used to switch to another device."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_hikcamera.return_value.get_id = "another-device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD


async def test_reauth_of_a_made_up_id_still_checks_a_device_with_its_own(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device that answers with an ID of its own is checked, made-up entry or not.

    Only a made-up ID cannot be checked against the entry.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=str(uuid.uuid4()),
        data={**mock_config_entry.data, CONF_RANDOM_ID: True},
    )
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_hikcamera.return_value.get_id = "another-device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD


async def test_a_devices_own_random_uuid_is_checked(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test a device whose own ID is a random UUID is not taken for a made-up one.

    pyHik gives a device's own ID as a string, and only an ID it makes up as a UUID
    object: the entry records which it was. Another device, answering with a
    made-up ID at the same address, is not the same device.
    """
    own = str(uuid.uuid4())
    mock_hikcamera.return_value.get_id = own
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == own
    assert entry.data[CONF_RANDOM_ID] is False

    entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()
    mock_hikcamera.return_value.get_id = uuid.uuid4()
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_PASSWORD] == TEST_PASSWORD


async def test_a_derived_id_is_not_recorded_as_random(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test the stable ID pyHik derives from the serial is checked like a real one."""
    derived = uuid.uuid5(uuid.NAMESPACE_URL, "serialNumber:sn1")
    mock_hikcamera.return_value.get_id = derived
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()

    assert result["result"].unique_id == str(derived)
    assert result["result"].data[CONF_RANDOM_ID] is False


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test where and how the device is reached can be changed."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"name": mock_config_entry.title}
    # The form starts from what the entry has now
    assert {
        str(key): (key.description or {}).get("suggested_value")
        for key in result["data_schema"].schema
    } == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: TEST_USERNAME,
        # The password is never shown
        CONF_PASSWORD: None,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "192.168.1.200",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
        CONF_USERNAME: TEST_USERNAME,
        # Left empty, the password is kept
        CONF_PASSWORD: TEST_PASSWORD,
        # Recorded by the setup: the camera's own ID.
        CONF_RANDOM_ID: False,
    }
    # The device was reached the new way, with the stored credentials, and the
    # entry was loaded again with the new settings.
    mock_hikcamera.assert_called_with(
        "https://192.168.1.200", 443, TEST_USERNAME, TEST_PASSWORD, False
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({CONF_PORT: 8080}, id="port"),
        pytest.param({CONF_SSL: True}, id="ssl"),
        pytest.param({CONF_VERIFY_SSL: False}, id="verify_ssl"),
    ],
)
@pytest.mark.usefixtures("mock_hikcamera")
async def test_reconfigure_whose_reload_fails_to_unload_asks_for_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    changes: dict[str, object],
) -> None:
    """Test settings saved by the flow, then held back by its reload, ask a restart.

    The flow already said it worked: the repair issue says what is left to do.
    """
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        side_effect=HomeAssistantError("stuck"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_PORT: TEST_PORT,
                CONF_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_USERNAME: TEST_USERNAME,
                **changes,
            },
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert issue_registry.async_get_issue(
        DOMAIN, f"restart_required_{mock_config_entry.entry_id}"
    )


async def test_reconfigure_flow_changes_the_credentials(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the username and the password can be changed, and are checked."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: "viewer",
            CONF_PASSWORD: "new-secret",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "viewer"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    mock_hikcamera.assert_called_with(
        f"http://{TEST_HOST}", TEST_PORT, "viewer", "new-secret", True
    )


async def test_the_password_is_masked_in_every_form(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the setup, reauthentication and reconfigure forms hide the password."""
    await setup_integration(hass, mock_config_entry)
    forms = [
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        ),
        await mock_config_entry.start_reauth_flow(hass),
        await mock_config_entry.start_reconfigure_flow(hass),
    ]

    for form in forms:
        [selector] = [
            value
            for key, value in form["data_schema"].schema.items()
            if str(key) == CONF_PASSWORD
        ]
        assert isinstance(selector, TextSelector)
        assert selector.config["type"] == TextSelectorType.PASSWORD


async def test_reconfigure_a_new_username_needs_its_password(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a new username with no password is not checked with the stored one.

    The stored password is the other user's: the form asks for the new one.
    """
    await setup_integration(hass, mock_config_entry)
    mock_hikcamera.reset_mock()
    form = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: "viewer",
    }

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "password_required"}
    mock_hikcamera.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**form, CONF_PASSWORD: "viewer-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "viewer"
    assert mock_config_entry.data[CONF_PASSWORD] == "viewer-secret"


async def test_reconfigure_an_entry_that_cannot_reach_its_device(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device that moved to another address is reached again.

    The entry retries its setup at the old address; saving the new one sets it up.
    """
    mock_hikcamera.side_effect = requests.exceptions.ConnectionError("unreachable")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_hikcamera.side_effect = None
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: TEST_PORT,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.assert_called_with(
        "http://192.168.1.200", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.parametrize("port", [0, 65536])
async def test_a_port_out_of_range_is_refused(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    port: int,
) -> None:
    """Test the setup and reconfigure forms refuse a port no device can have."""
    form = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: port,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], form)

    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], form)


async def test_reconfigure_flow_of_an_entry_from_before_verify_ssl(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry without the option is shown, and kept, as verifying."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            key: value
            for key, value in mock_config_entry.data.items()
            if key != CONF_VERIFY_SSL
        },
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert {
        str(key): (key.description or {}).get("suggested_value")
        for key in result["data_schema"].schema
    }[CONF_VERIFY_SSL] is True

    # Only the address changes, the form sends the option as it was shown.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: TEST_PORT,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert mock_config_entry.data[CONF_VERIFY_SSL] is True


@pytest.mark.parametrize(
    ("get_id", "auth_failed", "side_effect", "error"),
    [
        (None, True, None, "invalid_auth"),
        (None, False, None, "cannot_connect"),
        (TEST_DEVICE_ID, False, requests.exceptions.ConnectionError, "cannot_connect"),
        (TEST_DEVICE_ID, False, RuntimeError, "unknown"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    get_id: str | None,
    auth_failed: bool,
    side_effect: type[Exception] | None,
    error: str,
) -> None:
    """Test reconfiguring reports why the device could not be reached."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    user_input = {
        CONF_HOST: "192.168.1.200",
        CONF_PORT: TEST_PORT,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: TEST_USERNAME,
    }

    mock_hikcamera.return_value.get_id = get_id
    mock_hikcamera.return_value.auth_failed = auth_failed
    mock_hikcamera.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST
    # The form keeps what was typed.
    suggested = {
        str(key): (key.description or {}).get("suggested_value")
        for key in result["data_schema"].schema
    }
    assert suggested[CONF_HOST] == "192.168.1.200"

    # Recover from the error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.auth_failed = False
    mock_hikcamera.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"


async def test_reconfigure_flow_different_device(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry cannot be moved to another device."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_hikcamera.return_value.get_id = "another-device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: TEST_PORT,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST


async def test_reconfigure_after_a_failed_unload_needs_a_restart(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the new settings are saved, and a restart asked for.

    Home Assistant does not reload an entry whose unload failed, so the flow must
    not say it was reloaded.
    """
    await setup_integration(hass, mock_config_entry)
    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        side_effect=HomeAssistantError("boom"),
    ):
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: TEST_PORT,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_restart_required"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD


async def test_reconfigure_an_entry_with_a_made_up_id(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a device whose ID pyHik makes up can be moved to a new address.

    It gets a new made-up ID each time, so it cannot be checked against the entry.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Front Camera",
        unique_id=str(uuid.uuid4()),
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_RANDOM_ID: True,
        },
    )
    mock_hikcamera.return_value.get_id = uuid.uuid4()
    await setup_integration(hass, entry)
    mock_hikcamera.return_value.get_id = uuid.uuid4()

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: TEST_PORT,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.200"
