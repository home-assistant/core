"""Tests for the Withings component."""

from datetime import timedelta
from typing import Final

from homeassistant.components.evohome import CONFIG_SCHEMA
from homeassistant.components.evohome.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONFIG: Final = {CONF_USERNAME: "username@email.com", CONF_PASSWORD: "P@ssw0rd!!"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import flow (from configuration.yaml)."""

    HASS_CONFIG: Final = CONFIG_SCHEMA({DOMAIN: TEST_CONFIG})

    # async_step_import() converts scan_interval from a timedelta to an int
    assert isinstance(HASS_CONFIG[DOMAIN][CONF_SCAN_INTERVAL], timedelta)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=HASS_CONFIG[DOMAIN]
    )

    assert isinstance(HASS_CONFIG[DOMAIN][CONF_SCAN_INTERVAL], timedelta)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Evohome"
    assert result["options"] == {}

    scan_interval = result["data"].pop(CONF_SCAN_INTERVAL)
    assert scan_interval == HASS_CONFIG[DOMAIN][CONF_SCAN_INTERVAL].total_seconds()

    assert result["data"] == {
        k: v for k, v in HASS_CONFIG[DOMAIN].items() if k != CONF_SCAN_INTERVAL
    }


async def test_single_config_entry(hass: HomeAssistant) -> None:
    """Test config flow is aborted when creating a second entry."""

    HASS_CONFIG: Final = CONFIG_SCHEMA({DOMAIN: TEST_CONFIG})

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, title="Evohome", data=HASS_CONFIG[DOMAIN]
    )
    mock_config_entry.add_to_hass(hass)

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=HASS_CONFIG[DOMAIN]
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
