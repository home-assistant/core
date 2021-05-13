"""Test the Heatzy config flow."""
from unittest.mock import patch

from heatzypy.exception import HeatzyException
import pytest

from homeassistant import config_entries
from homeassistant.components.heatzy.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_USERNAME: "myuser",
    CONF_PASSWORD: "password",
}


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.heatzy.HeatzyClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.get_devices.return_value = [
            {
                "product_key": "ABC0123456",
                "product_name": "Pilote2",
                "dev_alias": "my_name",
                "did": "0123456789",
                "mac": "01020304050F",
            }
        ]
        yield client


async def test_form(hass, client):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.heatzy.config_flow.HeatzyClient", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_CONFIG,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "heatzy"
    assert result["data"] == {CONF_USERNAME: "myuser", CONF_PASSWORD: "password"}


async def test_form_updates_unique_id(hass, client):
    """Test a duplicate id aborts and updates existing entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="myuser",
        data={CONF_USERNAME: "myuser", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_form_exception(hass, client):
    """Test client exception."""
    with patch(
        "homeassistant.components.heatzy.config_flow.HeatzyClient",
        side_effect=HeatzyException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_CONFIG,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
