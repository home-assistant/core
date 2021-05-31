"""Test NFAndroidTV config flow."""
import logging
from unittest.mock import patch

from httpcore import ConnectError
import pytest

from homeassistant.components.nfandroidtv.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    CONF_CONFIG_FLOW,
    CONF_DATA,
    NAME,
    _create_mocked_tv,
    _patch_config_flow_tv,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture():
    """Mock the connect timeout."""
    with patch(
        "homeassistant.components.nfandroidtv.DEFAULT_TIMEOUT", new=1
    ) as timeout:
        yield timeout


def _patch_setup():
    return patch(
        "homeassistant.components.nfandroidtv.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass):
    """Test user initialized flow."""
    mocked_tv = await _create_mocked_tv()
    with _patch_config_flow_tv(mocked_tv), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass):
    """Test user initialized flow with duplicate device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_NAME: "Android TV / Fire TV"},
    )

    entry.add_to_hass(hass)

    service_info = {
        "host": "1.2.3.4",
        "name": "Android TV / Fire TV",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass):
    """Test user initialized flow with unreachable server."""
    mocked_tv = await _create_mocked_tv(True)
    with _patch_config_flow_tv(mocked_tv) as tvmock:
        tvmock.side_effect = ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_error(hass):
    """Test user initialized flow with unreachable server."""
    mocked_tv = await _create_mocked_tv(True)
    with _patch_config_flow_tv(mocked_tv) as tvmock:
        tvmock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}
