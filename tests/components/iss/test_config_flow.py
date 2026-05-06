"""Test iss config flow."""

from unittest.mock import patch

from homeassistant.components.iss.const import (
    CONF_MAX_CONSECUTIVE_FAILURES,
    DEFAULT_MAX_CONSECUTIVE_FAILURES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("result").data == {}


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_options(hass: HomeAssistant) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        optionflow = await hass.config_entries.options.async_init(config_entry.entry_id)

        configured = await hass.config_entries.options.async_configure(
            optionflow["flow_id"],
            user_input={
                CONF_SHOW_ON_MAP: True,
                CONF_MAX_CONSECUTIVE_FAILURES: 10,
            },
        )

        assert configured.get("type") is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            CONF_SHOW_ON_MAP: True,
            CONF_MAX_CONSECUTIVE_FAILURES: 10,
        }


async def test_options_defaults(hass: HomeAssistant) -> None:
    """Test options flow stores default value when not changed."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        optionflow = await hass.config_entries.options.async_init(config_entry.entry_id)

        configured = await hass.config_entries.options.async_configure(
            optionflow["flow_id"],
            user_input={
                CONF_SHOW_ON_MAP: False,
                CONF_MAX_CONSECUTIVE_FAILURES: DEFAULT_MAX_CONSECUTIVE_FAILURES,
            },
        )

        assert configured.get("type") is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            CONF_SHOW_ON_MAP: False,
            CONF_MAX_CONSECUTIVE_FAILURES: DEFAULT_MAX_CONSECUTIVE_FAILURES,
        }


async def test_create_entry_with_defaults(hass: HomeAssistant) -> None:
    """Test config entry is created with default options."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("result").options == {
            CONF_SHOW_ON_MAP: False,
            CONF_MAX_CONSECUTIVE_FAILURES: DEFAULT_MAX_CONSECUTIVE_FAILURES,
        }
