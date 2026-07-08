"""The tests for the nx584 alarm_control_panel platform."""

from unittest import mock

import pytest
import requests

from homeassistant.components.nx584 import alarm_control_panel as nx584
from homeassistant.components.nx584.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("reason", "issue_domain", "issue_id"),
    [
        pytest.param(
            "already_configured",
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            id="already_configured",
        ),
        pytest.param(
            "cannot_connect",
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            id="import_failed",
        ),
    ],
)
async def test_async_setup_platform_imports_config(
    hass: HomeAssistant, reason: str, issue_domain: str, issue_id: str
) -> None:
    """Test the YAML platform triggers the config entry import flow and raises an issue."""
    config = {CONF_HOST: "1.1.1.1", CONF_PORT: 5007}

    with mock.patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init",
        return_value=FlowResult(type=FlowResultType.ABORT, reason=reason),
    ) as mock_init:
        await nx584.async_setup_platform(hass, config, mock.MagicMock())

    mock_init.assert_called_once_with(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    assert ir.async_get(hass).async_get_issue(issue_domain, issue_id) is not None


async def test_async_setup_entry_creates_alarm_panel(hass: HomeAssistant) -> None:
    """Test setting up the alarm_control_panel platform from a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 5007},
        title="NX584",
    )
    entry.add_to_hass(hass)

    with mock.patch("homeassistant.components.nx584.client.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = []
        mock_client.list_partitions.return_value = [
            {"armed": False, "condition_flags": []}
        ]

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.nx584") is not None


def test_update_marks_entity_unavailable_on_connection_error() -> None:
    """Test that a connection error is handled and marks the entity unavailable."""
    client = mock.MagicMock()
    client.list_partitions.side_effect = requests.exceptions.ConnectionError
    alarm = nx584.NX584Alarm("NX584", client)

    alarm.update()

    assert alarm.available is False


def test_update_marks_entity_unavailable_when_no_partitions_reported() -> None:
    """Test that a missing partition list is handled and marks the entity unavailable."""
    client = mock.MagicMock()
    client.list_partitions.return_value = []
    alarm = nx584.NX584Alarm("NX584", client)

    alarm.update()

    assert alarm.available is False


def test_update_restores_availability_after_reconnect() -> None:
    """Test the entity becomes available again once the panel is reachable again."""
    client = mock.MagicMock()
    client.list_partitions.side_effect = requests.exceptions.ConnectionError
    alarm = nx584.NX584Alarm("NX584", client)
    alarm.update()
    assert alarm.available is False

    client.list_partitions.side_effect = None
    client.list_partitions.return_value = [{"armed": False, "condition_flags": []}]
    client.list_zones.return_value = []

    alarm.update()

    assert alarm.available is True
