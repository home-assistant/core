"""Test the Hikvision config flow."""

from unittest.mock import MagicMock
import uuid

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import CONF_RANDOM_ID, DOMAIN
from homeassistant.components.hikvision.identity import looks_made_up
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_with_ssl(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test user flow with ssl enabled passes ssl parameter to HikCamera."""
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
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is True
    assert result["result"].unique_id == TEST_DEVICE_ID

    # Verify HikCamera was called over HTTPS, verifying the certificate
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_with_ssl_without_verification(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test user flow can use HTTPS without verifying the certificate."""
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
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is False
    assert result["result"].unique_id == TEST_DEVICE_ID

    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, False
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
