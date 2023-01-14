"""Tests for the Comfoconnect config flow."""
# from copy import copy
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.comfoconnect.const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_TOKEN
from homeassistant.core import HomeAssistant

# from homeassistant.setup import async_setup_component
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONF_DATA = {
    CONF_HOST: "127.0.0.1",
    CONF_NAME: DEFAULT_NAME,
    CONF_TOKEN: DEFAULT_TOKEN,
    CONF_PIN: DEFAULT_PIN,
    CONF_USER_AGENT: DEFAULT_USER_AGENT,
}

CONF_IMPORT_DATA = CONF_DATA  # | {CONF_NAME: "Bridge"} | {}


@pytest.fixture()
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    return create_entry(hass)


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create fixture for adding config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)
    return entry


def _patch_setup_entry():
    return patch(
        "homeassistant.components.comfoconnect.async_setup_entry", return_value=True
    )


def patch_config_flow(mocked_bridge: MagicMock):
    """Patch Comfoconnect config flow."""
    return patch(
        "homeassistant.components.comfoconnect.config_flow.Bridge",
        return_value=mocked_bridge,
    )


@pytest.fixture()
def mocked_bridge() -> MagicMock:
    """Create mocked comfoconnect device."""
    mocked_bridge = MagicMock()
    return mocked_bridge


# TESTS
async def test_import(hass: HomeAssistant, mocked_bridge: MagicMock) -> None:
    """Test import initialized flow."""
    with patch_config_flow(mocked_bridge), _patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_IMPORT_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "configuration.yaml"
    assert result["data"] == CONF_DATA

    # Create same config again, should be rejected due to same host
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONF_IMPORT_DATA,
    )
    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_flow_user_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test user initialized flow with duplicate server."""

    # Create the integration using the same config data as already created,
    # we should reject the creation due same host
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow setup with connection error."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_discover:
        mock_discover.return_value = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user(hass: HomeAssistant, mocked_bridge: MagicMock) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    with patch_config_flow(mocked_bridge), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA
