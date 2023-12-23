"""Define tests for the OpenUV config flow."""
from ipaddress import ip_address
from unittest.mock import patch

import pytest
from regenmaschine.errors import RainMachineError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import zeroconf
from homeassistant.components.rainmachine import (
    CONF_DEFAULT_ZONE_RUN_TIME,
    CONF_USE_APP_RUN_TIMES,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_duplicate_error(hass: HomeAssistant, config, config_entry) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_password(hass: HomeAssistant, config) -> None:
    """Test that an invalid password throws an error."""
    with patch("regenmaschine.client.Client.load_local", side_effect=RainMachineError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config
        )
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


@pytest.mark.parametrize(
    ("platform", "entity_name", "entity_id", "old_unique_id", "new_unique_id"),
    [
        (
            "binary_sensor",
            "Home Flow Sensor",
            "binary_sensor.home_flow_sensor",
            "60e32719b6cf_flow_sensor",
            "60:e3:27:19:b6:cf_flow_sensor",
        ),
        (
            "switch",
            "Home Landscaping",
            "switch.home_landscaping",
            "60e32719b6cf_RainMachineZone_1",
            "60:e3:27:19:b6:cf_zone_1",
        ),
    ],
)
async def test_migrate_1_2(
    hass: HomeAssistant,
    client,
    config,
    config_entry,
    entity_id,
    entity_name,
    old_unique_id,
    new_unique_id,
    platform,
) -> None:
    """Test migration from version 1 to 2 (consistent unique IDs)."""
    ent_reg = er.async_get(hass)

    # Create entity RegistryEntry using old unique ID format:
    entity_entry = ent_reg.async_get_or_create(
        platform,
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=config_entry,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == entity_id
    assert entity_entry.unique_id == old_unique_id

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(entity_id)
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id(platform, DOMAIN, old_unique_id) is None


async def test_options_flow(hass: HomeAssistant, config, config_entry) -> None:
    """Test config flow options."""
    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_DEFAULT_ZONE_RUN_TIME: 600, CONF_USE_APP_RUN_TIMES: False},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            CONF_DEFAULT_ZONE_RUN_TIME: 600,
            CONF_USE_APP_RUN_TIMES: False,
        }


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass: HomeAssistant, config, setup_rainmachine) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=config,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "12345"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
        CONF_DEFAULT_ZONE_RUN_TIME: 600,
    }


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_ip_already_exists(
    hass: HomeAssistant, client, config, config_entry, source
) -> None:
    """Test homekit and zeroconf with an ip that already exists."""
    with patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.100"),
                ip_addresses=[ip_address("192.168.1.100")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_ip_change(
    hass: HomeAssistant, client, config_entry, source
) -> None:
    """Test zeroconf with an ip change."""
    with patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.2"),
                ip_addresses=[ip_address("192.168.1.2")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_IP_ADDRESS] == "192.168.1.2"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_new_controller_when_some_exist(
    hass: HomeAssistant, client, config, source
) -> None:
    """Test homekit and zeroconf for a new controller when one already exists."""
    with patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.100"),
                ip_addresses=[ip_address("192.168.1.100")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.100",
                CONF_PASSWORD: "password",
                CONF_PORT: 8080,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "12345"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
        CONF_DEFAULT_ZONE_RUN_TIME: 600,
    }


async def test_discovery_by_homekit_and_zeroconf_same_time(
    hass: HomeAssistant, client
) -> None:
    """Test the same controller gets discovered by two different methods."""
    with patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.100"),
                ip_addresses=[ip_address("192.168.1.100")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=zeroconf.ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.100"),
                ip_addresses=[ip_address("192.168.1.100")],
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"
