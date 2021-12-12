"""Define tests for the OpenUV config flow."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from regenmaschine.errors import RainMachineError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import zeroconf
from homeassistant.components.rainmachine import CONF_ZONE_RUN_TIME, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def _get_mock_client():
    mock_controller = Mock()
    mock_controller.name = "My Rain Machine"
    mock_controller.mac = "aa:bb:cc:dd:ee:ff"
    return Mock(
        load_local=AsyncMock(), controllers={"aa:bb:cc:dd:ee:ff": mock_controller}
    )


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    MockConfigEntry(
        domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data=conf
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=conf,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_password(hass):
    """Test that an invalid password throws an error."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "bad_password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    with patch(
        "regenmaschine.client.Client.load_local",
        side_effect=RainMachineError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=conf,
        )
        await hass.async_block_till_done()

    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


@pytest.mark.parametrize(
    "platform,entity_name,entity_id,old_unique_id,new_unique_id",
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
    hass, platform, entity_name, entity_id, old_unique_id, new_unique_id
):
    """Test migration from version 1 to 2 (consistent unique IDs)."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    entry = MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data=conf)
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)

    # Create entity RegistryEntry using old unique ID format:
    entity_entry = ent_reg.async_get_or_create(
        platform,
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )
    assert entity_entry.entity_id == entity_id
    assert entity_entry.unique_id == old_unique_id

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    entity_entry = ent_reg.async_get(entity_id)
    assert entity_entry.unique_id == new_unique_id
    assert ent_reg.async_get_entity_id(platform, DOMAIN, old_unique_id) is None


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=conf,
        options={CONF_ZONE_RUN_TIME: 900},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ZONE_RUN_TIME: 600}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_ZONE_RUN_TIME: 600}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=conf,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "My Rain Machine"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
        CONF_ZONE_RUN_TIME: 600,
    }
    assert mock_setup_entry.called


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_ip_already_exists(hass, source):
    """Test homekit and zeroconf with an ip that already exists."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    MockConfigEntry(
        domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data=conf
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.1.100",
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_ip_change(hass, source):
    """Test zeroconf with an ip change."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    entry = MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data=conf)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.1.2",
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.2"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_step_homekit_zeroconf_new_controller_when_some_exist(hass, source):
    """Test homekit and zeroconf for a new controller when one already exists."""
    existing_conf = {
        CONF_IP_ADDRESS: "192.168.1.3",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="zz:bb:cc:dd:ee:ff", data=existing_conf
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.1.100",
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
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

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "My Rain Machine"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
        CONF_ZONE_RUN_TIME: 600,
    }
    assert mock_setup_entry.called


async def test_discovery_by_homekit_and_zeroconf_same_time(hass):
    """Test the same controller gets discovered by two different methods."""

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.1.100",
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.rainmachine.config_flow.Client",
        return_value=_get_mock_client(),
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.1.100",
                hostname="mock_hostname",
                name="mock_name",
                port=None,
                properties={},
                type="mock_type",
            ),
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"
