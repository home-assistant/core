"""Test the Aussie Broadband config flow."""
from unittest.mock import patch

from aussiebb import AuthenticationException

from homeassistant import config_entries
from homeassistant.components.aussie_broadband.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == RESULT_TYPE_FORM
    assert result1["errors"] is None

    fake_services = [
        {"service_id": "12345678", "description": "Fake ABB Service"},
    ]

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fake ABB Service"
    assert result2["data"] == {
        "service_id": "12345678",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Test Already configured
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == RESULT_TYPE_ABORT


async def test_no_services(hass: HomeAssistant) -> None:
    """Test when there are no services."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == RESULT_TYPE_FORM
    assert result1["errors"] is None

    fake_services = []

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_duplicate_service(hass: HomeAssistant) -> None:
    """Test form fails if adding a service twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    fake_services = [
        {"service_id": "12345678", "description": "Fake ABB Service"},
    ]

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] is None
    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == RESULT_TYPE_ABORT
    assert result4["reason"] == "already_configured"


async def test_form_no_services(hass: HomeAssistant) -> None:
    """Test the config flow with no services."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=[]
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "no_services_found"


async def test_form_multiple_services(hass: HomeAssistant) -> None:
    """Test the config flow with multiple services."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    fake_services = [
        {"service_id": "12345678", "description": "Fake ABB Service 1"},
        {"service_id": "87654321", "description": "Fake ABB Service 2"},
    ]

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "service"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"service_id": "87654321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Fake ABB Service 2"
    assert result3["data"] == {
        "service_id": "87654321",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_services_duplicate(hass: HomeAssistant) -> None:
    """Test that the form fails if adding a service twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    fake_services = [
        {"service_id": "12345678", "description": "Fake ABB Service 1"},
        {"service_id": "87654321", "description": "Fake ABB Service 2"},
    ]

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "service"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"service_id": "87654321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Fake ABB Service 2"
    assert result3["data"] == {
        "service_id": "87654321",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["errors"] is None

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result5["type"] == RESULT_TYPE_FORM
    assert result5["step_id"] == "service"
    assert result5["errors"] is None

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        {"service_id": "87654321"},
    )
    await hass.async_block_till_done()

    assert result6["type"] == RESULT_TYPE_ABORT
    assert result6["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth is handled."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aussiebb.AussieBB.__init__", side_effect=AuthenticationException()):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth is handled."""
    # Setup a config entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    fake_services = [
        {"service_id": "12345678", "description": "Fake ABB Service"},
    ]

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ), patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY

    # Trigger the reauth
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result3["step_id"] == "user"

    with patch("aussiebb.AussieBB.__init__", return_value=None), patch(
        "aussiebb.AussieBB.get_services", return_value=fake_services
    ):

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "username": "test-username",
                "password": "test-newpassword",
            },
        )
        await hass.async_block_till_done()

        assert result4["type"] == "abort"
        assert result4["reason"] == "reauth_successful"
