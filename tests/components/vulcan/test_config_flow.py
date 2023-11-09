"""Test the Uonet+ Vulcan config flow."""
import json
from unittest import mock
from unittest.mock import patch

from vulcan import (
    Account,
    ExpiredTokenException,
    InvalidPINException,
    InvalidSymbolException,
    InvalidTokenException,
    UnauthorizedCertificateException,
)
from vulcan.model import Student

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
from homeassistant.components.vulcan.config_flow import ClientConnectionError, Keystore
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

fake_keystore = Keystore("", "", "", "", "")
fake_account = Account(
    login_id=1,
    user_login="example@example.com",
    user_name="example@example.com",
    rest_url="rest_url",
)


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    flow = config_flow.VulcanFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "auth"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_success(
    mock_keystore, mock_account, mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow initialized by the user."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 1


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_success_with_multiple_students(
    mock_keystore, mock_account, mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow with multiple students."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(student)
        for student in [load_fixture("fake_student_1.json", "vulcan")]
        + [load_fixture("fake_student_2.json", "vulcan")]
    ]
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "0"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 1


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_config_flow_reauth_success(
    mock_account, mock_keystore, mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow reauth."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data={"student_id": "0"},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_config_flow_reauth_without_matching_entries(
    mock_account, mock_keystore, mock_student, hass: HomeAssistant
) -> None:
    """Test a aborted config flow reauth caused by leak of matching entries."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data={"student_id": "1"},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_matching_entries"


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_config_flow_reauth_with_errors(
    mock_account, mock_keystore, hass: HomeAssistant
) -> None:
    """Test reauth config flow with errors."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidTokenException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ExpiredTokenException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "expired_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidPINException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_pin"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidSymbolException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_symbol"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_multiple_config_entries(
    mock_account, mock_keystore, mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow for multiple config entries."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)
    await register.register(hass, "token", "region", "000000")
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": False},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "token", CONF_REGION: "region", CONF_PIN: "000000"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 2


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials(
    mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow for multiple config entries using saved credentials."""
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"use_saved_credentials": True},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 2


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_2(
    mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ] + [Student.load(load_fixture("fake_student_2.json", "vulcan"))]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "0"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 2


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_3(
    mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow for multiple config entries using saved credentials."""
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "456"},
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 3


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_4(
    mock_student, hass: HomeAssistant
) -> None:
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ] + [Student.load(load_fixture("fake_student_2.json", "vulcan"))]
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "456"},
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"credentials": "123"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vulcan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "0"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"
    assert len(mock_setup_entry.mock_calls) == 3


async def test_multiple_config_entries_without_valid_saved_credentials(
    hass: HomeAssistant,
) -> None:
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "456"},
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=UnauthorizedCertificateException,
    ):
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_credentials"}


async def test_multiple_config_entries_using_saved_credentials_with_connections_issues(
    hass: HomeAssistant,
) -> None:
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "456"},
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=ClientConnectionError,
    ):
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_multiple_config_entries_using_saved_credentials_with_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "456"},
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan")),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=Exception,
    ):
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_student_already_exists(
    mock_account, mock_keystore, mock_student, hass: HomeAssistant
) -> None:
    """Test config entry when student's entry already exists."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(load_fixture("fake_student_1.json", "vulcan"))
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data=json.loads(load_fixture("fake_config_entry_data.json", "vulcan"))
        | {"student_id": "0"},
    ).add_to_hass(hass)

    await register.register(hass, "token", "region", "000000")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "all_student_already_configured"


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_token(
    mock_keystore, hass: HomeAssistant
) -> None:
    """Test a config flow initialized by the user using invalid token."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidTokenException,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S20000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_token"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_region(
    mock_keystore, hass: HomeAssistant
) -> None:
    """Test a config flow initialized by the user using invalid region."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidSymbolException,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_symbol"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_pin(mock_keystore, hass: HomeAssistant) -> None:
    """Test a config flow initialized by the with invalid pin."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=InvalidPINException,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_pin"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_expired_token(
    mock_keystore, hass: HomeAssistant
) -> None:
    """Test a config flow initialized by the with expired token."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ExpiredTokenException,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_token"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_connection_error(
    mock_keystore, hass: HomeAssistant
) -> None:
    """Test a config flow with connection error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_unknown_error(
    mock_keystore, hass: HomeAssistant
) -> None:
    """Test a config flow with unknown error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}
