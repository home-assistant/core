"""Test the Network UPS Tools (NUT) config flow."""

from unittest.mock import patch

from pynut2.nut2 import PyNUTError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import zeroconf
from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from .util import _get_mock_pynutclient

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_HOST: "localhost",
    CONF_PORT: 123,
    CONF_NAME: "name",
    CONF_RESOURCES: ["battery.charge"],
}


async def test_form_zeroconf(hass):
    """Test we can setup from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.5",
            addresses=["192.168.1.5"],
            hostname="mock_hostname",
            name="mock_name",
            port=1234,
            properties={},
            type="mock_type",
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "192.168.1.5:1234"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.5",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 1234,
        CONF_USERNAME: "test-username",
    }
    assert result2["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_one_ups(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_multiple_ups(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "2.2.2.2", CONF_PORT: 123, CONF_RESOURCES: ["battery.charge"]},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1", "ups2": "UPS2"},
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["step_id"] == "ups"
    assert result2["type"] == data_entry_flow.FlowResultType.FORM

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups2"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["title"] == "ups2@1.1.1.1:2222"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_ALIAS: "ups2",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 2


async def test_form_user_one_ups_with_ignored_entry(hass):
    """Test we can setup a new one when there is an ignored one."""
    ignored_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_pynutclient()

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.nut.PyNUTClient.list_ups",
        side_effect=PyNUTError,
    ), patch(
        "homeassistant.components.nut.PyNUTClient.list_vars",
        side_effect=PyNUTError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.nut.PyNUTClient.list_ups",
        return_value=["ups1"],
    ), patch(
        "homeassistant.components.nut.PyNUTClient.list_vars",
        side_effect=TypeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_abort_if_already_setup(hass):
    """Test we abort if component is already setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 123,
            CONF_RESOURCES: ["battery.voltage"],
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1"},
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 123,
            },
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_abort_if_already_setup_alias(hass):
    """Test we abort if component is already setup with same alias."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 123,
            CONF_RESOURCES: ["battery.voltage"],
            CONF_ALIAS: "ups1",
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1", "ups2": "UPS 2"},
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 123,
            },
        )

    assert result2["step_id"] == "ups"
    assert result2["type"] == data_entry_flow.FlowResultType.FORM

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups1"},
        )

        assert result3["type"] == data_entry_flow.FlowResultType.ABORT
        assert result3["reason"] == "already_configured"


async def test_options_flow(hass):
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.nut.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            CONF_SCAN_INTERVAL: 60,
        }

    with patch("homeassistant.components.nut.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={CONF_SCAN_INTERVAL: 12},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {
            CONF_SCAN_INTERVAL: 12,
        }
