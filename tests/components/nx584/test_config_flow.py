"""Test the nx584 config flow."""

from unittest.mock import patch

import pytest
import requests

from homeassistant import config_entries
from homeassistant.components.nx584 import config_flow
from homeassistant.components.nx584.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry

TEST_DATA = {CONF_HOST: "1.1.1.1", CONF_PORT: 5007}


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DATA[CONF_HOST]
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_rejects_invalid_port(hass: HomeAssistant) -> None:
    """Test the user step schema rejects an out-of-range port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**TEST_DATA, CONF_PORT: 99999}
        )


async def test_validate_connection_brackets_ipv6_host(hass: HomeAssistant) -> None:
    """Test the client URL brackets an IPv6 host, as required by the URL spec."""
    with patch(
        "homeassistant.components.nx584.config_flow.client.Client"
    ) as mock_client_cls:
        mock_client_cls.return_value.list_zones.return_value = []
        await config_flow._async_validate_connection(hass, "::1", 5007)

    mock_client_cls.assert_called_once_with("http://[::1]:5007")


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nx584.config_flow.client.Client.list_zones",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nx584.config_flow.client.Client.list_zones",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the host/port is already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nx584.config_flow.client.Client.list_zones",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_success(hass: HomeAssistant) -> None:
    """Test importing YAML config creates an entry, ignoring unsupported fields."""
    import_config = {
        **TEST_DATA,
        "name": "NX584",
        "exclude_zones": [],
        "zone_types": {},
    }

    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=import_config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DATA[CONF_HOST]
    assert result["data"] == TEST_DATA


async def test_import_binary_sensor_after_alarm_control_panel_applies_zone_options(
    hass: HomeAssistant,
) -> None:
    """Test a later YAML import with zone options updates an existing entry.

    The alarm_control_panel platform has no exclude_zones/zone_types, so if it
    imports first it creates the entry with empty options. The binary_sensor
    platform's later import must still be able to apply its zone options to
    that same entry instead of losing them.
    """
    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_DATA,
        )
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].options == {}

        binary_sensor_import_config = {
            **TEST_DATA,
            "exclude_zones": [2],
            "zone_types": {3: "motion"},
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=binary_sensor_import_config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entries[0].options == {
        "exclude_zones": [2],
        "zone_types": {3: "motion"},
    }


async def test_import_alarm_control_panel_after_binary_sensor_keeps_zone_options(
    hass: HomeAssistant,
) -> None:
    """Test a later YAML import without zone options doesn't erase existing ones."""
    binary_sensor_import_config = {
        **TEST_DATA,
        "exclude_zones": [2],
        "zone_types": {3: "motion"},
    }

    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=binary_sensor_import_config,
        )
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].options == {
            "exclude_zones": [2],
            "zone_types": {3: "motion"},
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entries[0].options == {
        "exclude_zones": [2],
        "zone_types": {3: "motion"},
    }


async def test_import_after_restart_does_not_reload_with_same_zone_options(
    hass: HomeAssistant,
) -> None:
    """Test re-importing unchanged zone options after a restart doesn't reload.

    Config entry options are persisted as JSON, so zone_types keys round-trip
    as strings across a restart. The freshly-validated YAML import has int
    keys instead, so the comparison must normalize before deciding to reload.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        options={"exclude_zones": [2], "zone_types": {"3": "motion"}},
    )
    entry.add_to_hass(hass)

    binary_sensor_import_config = {
        **TEST_DATA,
        "exclude_zones": [2],
        "zone_types": {3: "motion"},
    }

    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_setup_entry.call_count == 1

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=binary_sensor_import_config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.options == {"exclude_zones": [2], "zone_types": {"3": "motion"}}
    assert mock_setup_entry.call_count == 1


async def test_import_second_panel_creates_separate_entry(hass: HomeAssistant) -> None:
    """Test importing a second panel with a different host/port is not treated as a match."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)
    other_panel = {CONF_HOST: "2.2.2.2", CONF_PORT: 5008}

    with (
        patch(
            "homeassistant.components.nx584.config_flow.client.Client.list_zones",
            return_value=[],
        ),
        patch(
            "homeassistant.components.nx584.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=other_panel
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == other_panel[CONF_HOST]
    assert result["data"] == other_panel


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test importing YAML config aborts if already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test importing YAML config aborts if the panel can't be reached."""
    with patch(
        "homeassistant.components.nx584.config_flow.client.Client.list_zones",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test configuring exclude_zones and zone_types through the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA)
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client_cls.return_value.list_zones.return_value = []
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"exclude_zones": [2], "zone_types": {"3": "motion"}},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"exclude_zones": [2], "zone_types": {3: "motion"}}


async def test_options_flow_missing_exclude_zones_defaults_to_empty(
    hass: HomeAssistant,
) -> None:
    """Test omitting exclude_zones from the submission doesn't raise KeyError."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA)
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client_cls.return_value.list_zones.return_value = []
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"zone_types": {"3": "motion"}},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"exclude_zones": [], "zone_types": {3: "motion"}}


async def test_options_flow_invalid_input(hass: HomeAssistant) -> None:
    """Test the options flow rejects malformed zone options."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA)
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client_cls.return_value.list_zones.return_value = []
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "exclude_zones": [2],
                "zone_types": {"3": "not_a_device_class"},
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_zone_options"}
