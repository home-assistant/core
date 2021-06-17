"""Test the Uonet+ Vulcan config flow."""
from unittest.mock import patch

from vulcan.model import Student

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vulcan import config_flow, const, register
from homeassistant.components.vulcan.config_flow import (
    ClientConnectionError,
    VulcanAPIException,
)
from homeassistant.const import CONF_PIN, CONF_REGION, CONF_SCAN_INTERVAL, CONF_TOKEN

from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.VulcanFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


async def test_config_flow_auth_success(hass):
    """Test a successful config flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


async def test_config_flow_auth_success_with_multiple_students(hass):
    """Test a successful config flow with multiple students."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}
    data = [
        {
            "TopLevelPartition": "region",
            "Partition": "region-001000",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "001000",
                "Short": "I LO",
                "RestURL": "https://lekcjaplus.vulcan.net.pl/zielonagora/001000/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I LO",
                "Name": "School",
                "Address": "Address",
            },
            "Pupil": {
                "Id": 39447,
                "LoginId": 36976,
                "LoginValue": "example@mail.com",
                "FirstName": "FirstName",
                "SecondName": "SecondName",
                "Surname": "Surname",
                "Sex": True,
            },
            "Periods": [],
        },
        {
            "TopLevelPartition": "powiatwulkanowy",
            "Partition": "powiatwulkanowy-123456",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "123456",
                "Short": "I LO",
                "RestURL": "https://api.fakelog.tk/powiatwulkanowy/123456/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I",
                "Name": "School",
                "Address": "Idk",
            },
            "Pupil": {
                "Id": 111,
                "LoginId": 111,
                "LoginValue": "jan@fakelog.tk",
                "FirstName": "Jan",
                "SecondName": None,
                "Surname": "Kowalski",
                "Sex": True,
            },
            "Periods": [],
        },
    ]
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        return_value=[Student.load(student) for student in data],
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_student"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "111"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Jan Kowalski"


async def test_config_flow_reauth_success(hass):
    """Test a successful config flow reauth."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="111",
        data={"student_id": "111", "login": "jan@fakelog.cf"},
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


async def test_config_flow_reauth_with_errors(hass):
    """Test reauth config flow with errors."""
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


async def test_multiple_config_entries(hass):
    """Test a successful config flow for multiple config entries."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        data={
            "student_id": "111",
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
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "FK10000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


async def test_multiple_config_entries_using_saved_credentials(hass):
    """Test a successful config flow for multiple config entries using saved credentials."""
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


async def test_multiple_config_entries_using_saved_credentials_2(hass):
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
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
    data = [
        {
            "TopLevelPartition": "region",
            "Partition": "region-001000",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "001000",
                "Short": "I LO",
                "RestURL": "https://lekcjaplus.vulcan.net.pl/zielonagora/001000/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I LO",
                "Name": "School",
                "Address": "Address",
            },
            "Pupil": {
                "Id": 39447,
                "LoginId": 36976,
                "LoginValue": "example@mail.com",
                "FirstName": "FirstName",
                "SecondName": "SecondName",
                "Surname": "Surname",
                "Sex": True,
            },
            "Periods": [],
        },
        {
            "TopLevelPartition": "powiatwulkanowy",
            "Partition": "powiatwulkanowy-123456",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "123456",
                "Short": "I LO",
                "RestURL": "https://api.fakelog.cf/powiatwulkanowy/123456/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I",
                "Name": "School",
                "Address": "Idk",
            },
            "Pupil": {
                "Id": 111,
                "LoginId": 111,
                "LoginValue": "jan@fakelog.cf",
                "FirstName": "Jan",
                "SecondName": None,
                "Surname": "Kowalski",
                "Sex": True,
            },
            "Periods": [],
        },
    ]
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        return_value=[Student.load(student) for student in data],
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"use_saved_credentials": True},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_student"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "111"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Jan Kowalski"


async def test_multiple_config_entries_using_saved_credentials_3(hass):
    """Test a successful config flow for multiple config entries using saved credentials."""
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
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"credentials": "123"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Jan Kowalski"


async def test_multiple_config_entries_using_saved_credentials_4(hass):
    """Test a successful config flow for multiple config entries using saved credentials (different situation)."""
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
    data = [
        {
            "TopLevelPartition": "region",
            "Partition": "region-001000",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "001000",
                "Short": "I LO",
                "RestURL": "https://lekcjaplus.vulcan.net.pl/zielonagora/001000/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I LO",
                "Name": "School",
                "Address": "Address",
            },
            "Pupil": {
                "Id": 39447,
                "LoginId": 36976,
                "LoginValue": "example@mail.com",
                "FirstName": "FirstName",
                "SecondName": "SecondName",
                "Surname": "Surname",
                "Sex": True,
            },
            "Periods": [],
        },
        {
            "TopLevelPartition": "powiatwulkanowy",
            "Partition": "powiatwulkanowy-123456",
            "ClassDisplay": "Class",
            "Unit": {
                "Id": 10,
                "Symbol": "123456",
                "Short": "I LO",
                "RestURL": "https://api.fakelog.cf/powiatwulkanowy/123456/api",
                "Name": "School",
                "DisplayName": "School",
            },
            "ConstituentUnit": {
                "Id": 25,
                "Short": "I",
                "Name": "School",
                "Address": "Idk",
            },
            "Pupil": {
                "Id": 111,
                "LoginId": 111,
                "LoginValue": "jan@fakelog.cf",
                "FirstName": "Jan",
                "SecondName": None,
                "Surname": "Kowalski",
                "Sex": True,
            },
            "Periods": [],
        },
    ]
    with patch(
        "homeassistant.components.vulcan.config_flow.Vulcan.get_students",
        return_value=[Student.load(student) for student in data],
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"use_saved_credentials": True},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_saved_credentials"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_student"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"student": "111"},
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
        assert result["errors"] == {}

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
        assert result["errors"] == {}

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
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"credentials": "123"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_student_already_exists(hass):
    """Test config entry when student's entry already exists."""
    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="111",
        data={
            "student_id": "111",
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


async def test_config_flow_auth_invalid_token(hass):
    """Test a config flow initialized by the user using invalid token."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid token."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S20000", CONF_REGION: "powiatwulkanowy", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_token"}


async def test_config_flow_auth_invalid_region(hass):
    """Test a config flow initialized by the user using invalid region."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Internal Server Error (ArgumentException)"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_symbol"}


async def test_config_flow_auth_invalid_pin(hass):
    """Test a config flow initialized by the with invalid pin."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Invalid PIN."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_pin"}


async def test_config_flow_auth_expired_token(hass):
    """Test a config flow initialized by the with expired token."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Expired token."),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "expired_token"}


async def test_config_flow_auth_api_unknown_error(hass):
    """Test a config flow with unknown API error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=VulcanAPIException("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_auth_api_unknown_runtime_error(hass):
    """Test a config flow with runtime error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=RuntimeError("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_auth_connection_error(hass):
    """Test a config flow with connection error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_auth_unknown_error(hass):
    """Test a config flow with unknown error."""
    with patch(
        "homeassistant.components.vulcan.config_flow.Account.register",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "3S10000", CONF_REGION: "invalid_region", CONF_PIN: "000000"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="111",
        data={
            "student_id": "111",
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
