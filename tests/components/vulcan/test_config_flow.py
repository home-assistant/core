"""Test the Uonet+ Vulcan config flow."""
from unittest import mock
from unittest.mock import patch

from vulcan import Account
from vulcan.model import Student

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
from homeassistant.components.vulcan.config_flow import (
    ClientConnectionError,
    Keystore,
    VulcanAPIException,
)
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_SCAN_INTERVAL, CONF_TOKEN

from tests.common import MockConfigEntry

fake_keystore = Keystore("", "", "MA==", "", "")
fake_account = Account(
    login_id=1,
    user_login="jan@fakelog.cf",
    user_name="jan@fakelog.cf",
    rest_url="http://api.fakelog.tk/powiatwulkanowy/",
)
fake_student_1 = {
    "TopLevelPartition": "",
    "Partition": "",
    "ClassDisplay": "",
    "Unit": {
        "Id": 1,
        "Symbol": "",
        "Short": "",
        "RestURL": "",
        "Name": "",
        "DisplayName": "",
    },
    "ConstituentUnit": {
        "Id": 1,
        "Short": "",
        "Name": "",
        "Address": "",
    },
    "Pupil": {
        "Id": 0,
        "LoginId": 0,
        "LoginValue": "",
        "FirstName": "Jan",
        "SecondName": "Maciej",
        "Surname": "Kowalski",
        "Sex": True,
    },
    "Periods": [],
}

fake_student_2 = {
    "TopLevelPartition": "",
    "Partition": "",
    "ClassDisplay": "",
    "Unit": {
        "Id": 1,
        "Symbol": "",
        "Short": "",
        "RestURL": "",
        "Name": "",
        "DisplayName": "",
    },
    "ConstituentUnit": {
        "Id": 1,
        "Short": "",
        "Name": "",
        "Address": "",
    },
    "Pupil": {
        "Id": 1,
        "LoginId": 1,
        "LoginValue": "",
        "FirstName": "Magda",
        "SecondName": "",
        "Surname": "Kowalska",
        "Sex": False,
    },
    "Periods": [],
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.VulcanFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_success(
    mock_keystore, mock_account, mock_student, hass
):
    """Test a successful config flow initialized by the user."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [Student.load(fake_student_1)]
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_success_with_multiple_students(
    mock_keystore, mock_account, mock_student, hass
):
    """Test a successful config flow with multiple students."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [
        Student.load(student) for student in [fake_student_1] + [fake_student_2]
    ]
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"student": "0"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_config_flow_reauth_success(
    mock_account, mock_keystore, mock_student, hass
):
    """Test a successful config flow reauth."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [Student.load(fake_student_1)]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data={"student_id": "0", "login": "jan@fakelog.cf"},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_config_flow_reauth_with_errors(mock_account, mock_keystore, hass):
    """Test reauth config flow with errors."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid token."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Expired token."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "expired_token"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid PIN."),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_pin"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Unknown error"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Internal Server Error (ArgumentException)"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "invalid_symbol"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Unknown error"),
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_multiple_config_entries(mock_account, mock_keystore, mock_student, hass):
    """Test a successful config flow for multiple config entries."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [Student.load(fake_student_1)]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "0",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": False},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials(mock_student, hass):
    """Test a successful config flow for multiple config entries using saved credentials."""
    mock_student.return_value = [Student.load(fake_student_1)]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_2(mock_student, hass):
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
    mock_student.return_value = [Student.load(fake_student_1)] + [
        Student.load(fake_student_2)
    ]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"student": "0"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_3(mock_student, hass):
    """Test a successful config flow for multiple config entries using saved credentials."""
    mock_student.return_value = [Student.load(fake_student_1)]
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"credentials": "123"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
async def test_multiple_config_entries_using_saved_credentials_4(mock_student, hass):
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
    mock_student.return_value = [Student.load(fake_student_1)] + [
        Student.load(fake_student_2)
    ]
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_saved_credentials"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"credentials": "123"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_student"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"student": "0"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


async def test_multiple_config_entries_without_valid_saved_credentials(hass):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=VulcanAPIException("The certificate is not authorized."),
    ):
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_credentials"}


async def test_multiple_config_entries_using_saved_credentials_with_connections_issues(
    hass,
):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_multiple_config_entries_using_saved_credentials_with_unknown_error(hass):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_multiple_config_entries_using_saved_credentials_with_unknown_api_error(
    hass,
):
    """Test a unsuccessful config flow for multiple config entries without valid saved credentials."""
    MockConfigEntry(
        entry_id="456",
        domain=const.DOMAIN,
        unique_id="234567",
        data={
            "student_id": "456",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "mail@fakelog.cf",
                "UserName": "mail@fakelog.cf",
            },
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        entry_id="123",
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "123",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        side_effect=VulcanAPIException("Unknown error"),
    ):
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Vulcan.get_students")
@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
@mock.patch("homeassistant.components.vulcan.config_flow.Account.register")
async def test_student_already_exists(mock_account, mock_keystore, mock_student, hass):
    """Test config entry when student's entry already exists."""
    mock_keystore.return_value = fake_keystore
    mock_account.return_value = fake_account
    mock_student.return_value = [Student.load(fake_student_1)]
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data={
            "student_id": "0",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    ).add_to_hass(hass)

    await register.register(hass, "FK10000", "powiatwulkanowy", "000000")

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "add_next_config_entry"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_saved_credentials": True},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "all_student_already_configured"


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_token(mock_keystore, hass):
    """Test a config flow initialized by the user using invalid token."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid token."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S20000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_token"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_region(mock_keystore, hass):
    """Test a config flow initialized by the user using invalid region."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Internal Server Error (ArgumentException)"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_symbol"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_invalid_pin(mock_keystore, hass):
    """Test a config flow initialized by the with invalid pin."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid PIN."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_pin"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_expired_token(mock_keystore, hass):
    """Test a config flow initialized by the with expired token."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Expired token."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_token"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_api_unknown_error(mock_keystore, hass):
    """Test a config flow with unknown API error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_api_unknown_runtime_error(mock_keystore, hass):
    """Test a config flow with runtime error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_connection_error(mock_keystore, hass):
    """Test a config flow with connection error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}


@mock.patch("homeassistant.components.vulcan.config_flow.Keystore.create")
async def test_config_flow_auth_unknown_error(mock_keystore, hass):
    """Test a config flow with unknown error."""
    mock_keystore.return_value = fake_keystore
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


@mock.patch("homeassistant.components.vulcan.Vulcan.get_students")
async def test_options_flow(mock_student, hass):
    """Test config flow options."""
    mock_student.return_value = [Student.load(fake_student_1)]
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="0",
        data={
            "student_id": "0",
            "keystore": {
                "Certificate": "MIICyzCCAbOgAwIBAgIBATANBgkqhkiG9w0BAQsFADApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwHhcNMjEwNjE2MTcwOTUwWhcNNDEwNjExMTcwOTUwWjApMScwJQYDVQQDDB5BUFBfQ0VSVElGSUNBVEUgQ0EgQ2VydGlmaWNhdGUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADQ8K9b45zTs1LT1fYFhXli4GeSquiJlMwYMoEKBh4Vt++5KLriIIilKxQ4OwXoA56CxCBDjryb9uAgINbzM4QUTGl5ewvJ1JM4LnfompOSjbac+DQ4X4ayTfYuSE0Q0Cvt2uzBBw5xPdEwQ9KH8UBtum72BkMlx/v4iUSjgzyvm9o9IR7S6l9pfEa2hOlxToRtTsXg3BZZTp+pGQQsPYPafsyvnqQWRDXLnPYWhG1D38zQ5YkwG/1/vyrhaaPv4YoKPcjoePi/z3h0RfUfpPpFIsNe9uybcJ2dnysPyVL1sCdMLytr6B/I6pWuej9onyaL+5dRl1hxfzc4pBo8dOA0=",
                "DeviceModel": "Home Assistant",
                "Fingerprint": "8ab2ef267d2b6099e3dd4b93e0c34e8dd1b53c8a",
                "FirebaseToken": "cg8Us2ilEHk:APA91bEzzADfzkEeY4uO61vwLMmzSj9QH-msfzMTloti1WYEtyBSO9gGdeUwuDqiMUUIWi-Ugs1J1O-vz9TrC-eWSeeQa1gTqzH0BaTN7Hu5PZk-ayRyCfRuMkdX-M_BLi6Vco9iK1UY",
                "PrivateKey": "MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQCvabkxJnd2jqKhwklGRsC1cSwqptdBXoQGYx6/L0zj18rtYfP00YM8SaVZwCMESjeVHGdQjXUh2xNigO/woq38B6Ho7BBZcpuH/clAnsZt5o4mL3YYJanlI2kzqnXqAZ/etz/ZxTKZeKkdzRrGnW+qHn9q13A/eyV6fCUy9s3KcB4xwu0lQLrGrpnP1LKdD4MuCcy5ZPegVJKwNtq0sc9NbzoNu+h7VWE4dLPcXSmMdr2aYTJ4cNIGEouj318jwu8MXpKLlsuXOQPNzNJ5mr5uQn3FF+e4dVNER2Z1M8RIFxwNqPlke5PgbUqwM5PeUTy4RnBeGJeUNwQKwXGgqovBAgMBAAECgf8i8ezy3bbu53t+vjXayj2Z5/HkjVhUrX+fxh9Z9xJaUaMbp2fyXcrHN+S4/I39TMvF6OKsKYIsPHigJw+l4MLIcrzOqjiXmT1i2iw9s2PUgRnQgaQFK3utKmDK6iqTc79lnxwZRi/OYztNtI6hArw8J9c6cbDq9J2CyTif7osQyPCB0ODP8yhJXN+Kai6FSinOVkUFO/UbopT8hckuvGr3NaiNaVqzehgcieBsTaG+PSzeNhmSa9fyt9mBg/L8y6WpymfsN65Yl9WbJTSnAxG3gxyVAtY56gwEXvCXPXS6hUSIjUSd7LO1/8LLQWTS0Y2mk47EiU/rY/n6xg8LPL0CgYEA5juD9z3mqb0ERUSoNa7CAaQpWbkmZYzITPNdAub9i99MUdEuxr2MhzVY3/xlcoW9RWlyPkso2oaMm5oYrvY1ULcIj0cr8BKUWaW5TbMpXkr6VKgQkCSIFijVy/ucGXSZz6qgcTyi2Dnoc0Bm/A4GstOnGZKj3UcAAz2V4QScC1sCgYEAwwuNVyRzURsh/7HillpeJrSKvIA5qXT3PZkwUcELmkLUev/3Aw7yCUEv9zRl3vNLcqJxn+5uCbjwXVhB5N6FadWl+qqzHva31lVavQGV6QdEAHvJAQ2ll84NbX21jN2leUrXVRzXId88MtQb9so0kZOoVRFCIWzTIhSy5tvTXBMCgYAHgd9Ou5T+6evuuktl3Ln0xb6Xb2MiIpIReEoLIy8XVYOuk0ycLGgdrI6mVxuTvWqrjcGs6FR/s614EXFGmz6n0CAWU/LJ1EFEHxRIxVPPAFDjW8uWd6p8Vn6KNT0k01mEnQK4Torc1B6RS4NQKsDrKd2kBtUTDRKiCGsPuE/CSwKBgHFy/rt5UDoU9imsZofd+HW6/he23dNbXZROznQ/PWh1BvKkgCEfSFlpuWSo7bhI+9Gp+z1zij3NfMJO28UsSZ3Nz8WGFLol97iL3UOi8Hei6kL9vWUHcxJhoB3XyQouwllS1v2C0P+6wWEvTzS1WO50XK1eZIDcs9JXB9iQdNhRAoGAZMYhIOe8kDQb4J8xG7HKYEDommMALwwwsYYlz15NvY6xJ4OTB3t+nb6u44CWQIA/d35Me6tgVKWBKAqFovS9wsUYpPcwAcUkvHlZnOLFxfGgKNqkn+S2S4aV47asIb4mKiYmUV23p7XikNUoQiusBHF1PxEwfzWV4qL2wC6TvG0=",
            },
            "account": {
                "LoginId": 207,
                "RestURL": "http://api.fakelog.tk/powiatwulkanowy/",
                "UserLogin": "jan@fakelog.cf",
                "UserName": "jan@fakelog.cf",
            },
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 2137}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 2137}
