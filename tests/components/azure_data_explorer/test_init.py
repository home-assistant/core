"""Test the init functions for AEH."""
from datetime import timedelta
import logging

from azure.kusto.data.exceptions import KustoAuthenticationError, KustoServiceError
from numpy import equal
import pytest

from homeassistant.components import azure_data_explorer
from homeassistant.components.azure_data_explorer.__init__ import AzureDataExplorer
from homeassistant.components.azure_event_hub.const import CONF_SEND_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import FilterTest
from .const import BASE_CONFIG_FULL, BASIC_OPTIONS, IMPORT_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_import(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    config[DOMAIN].update(IMPORT_CONFIG)
    assert await async_setup_component(hass, DOMAIN, config)


async def test_filter_only_config(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)


async def test_unload_entry(hass, entry, mock_managed_streaming):
    """Test being able to unload an entry.

    Queue should be empty, so adding events to the batch should not be called,
    this verifies that the unload, calls async_stop, which calls async_send and
    shuts down the hub.
    """
    assert await hass.config_entries.async_unload(entry.entry_id)
    mock_managed_streaming.add.assert_not_called()
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_failed_test_connection(hass):
    """Test Error when no getting proper connection."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED


async def test_async_setup_entry_no_error(hass):
    """Test Error when not getting proper connection."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_async_setup_entry_connection_Error(
    hass, mock_azure_data_explorer_test_connection
):
    """Test Error when not getting proper connection."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_azure_data_explorer_test_connection.side_effect = Exception("Message")
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_KustoService_Error(
    hass, mock_azure_data_explorer_test_connection
):
    """Test Error when not getting proper connection."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_azure_data_explorer_test_connection.side_effect = KustoServiceError("Message")
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_failed_test_connection_Auth_Error(
    hass, mock_azure_data_explorer_test_connection
):
    """Test Error when not getting proper connection."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_azure_data_explorer_test_connection.side_effect = KustoAuthenticationError(
        authentication_method="AM", exception=Exception
    )
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_AzureDataExplorer_test_connection(hass, mock_test_connection):
    """Test the Test_Connection method when init."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    AzureDataExplorer(hass, entry)
    mock_test_connection.assert_called_once()


async def test_AzureDataExplorer_parse_event(hass):
    # pylint: disable=protected-access
    """Test parsing events."""

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow() - timedelta(hours=1),
        last_updated=utcnow() - timedelta(hours=1),
    )

    adx_event, dropped = azure_data_explorer_instance._parse_event(
        utcnow() - timedelta(hours=1), state, 0
    )

    assert adx_event is None
    assert equal(dropped, 1)

    # Pass to good event
    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    adx_event, dropped = azure_data_explorer_instance._parse_event(utcnow(), state, 0)

    assert len(adx_event) > 100
    assert equal(dropped, 0)


async def test_async_send_1(hass):
    # pylint: disable=protected-access
    """Test parsing  1 event."""

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put good message on Queue for sending
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))

    # Put old message on Queue for sending
    await azure_data_explorer_instance._queue.put(
        (2, (utcnow() - timedelta(hours=1), state))
    )


async def test_async_send_2(hass, mock_azure_data_explorer_client_ingest_data):
    """Test parsing  1 event."""
    # pylint: disable=protected-access

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put two good message on Queue for sending
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))

    await azure_data_explorer_instance.async_send(0)
    mock_azure_data_explorer_client_ingest_data.assert_called_once()


async def test_async_send_only_old(hass, mock_azure_data_explorer_client_ingest_data):
    """Test parsing  1 event."""
    # pylint: disable=protected-access

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put old message on Queue for sending
    await azure_data_explorer_instance._queue.put(
        (2, (utcnow() - timedelta(hours=1), state))
    )

    await azure_data_explorer_instance.async_send(0)
    mock_azure_data_explorer_client_ingest_data.assert_not_called()


async def test_async_KustoServiceError(
    hass, mock_azure_data_explorer_client_ingest_data
):
    """Test parsing  with KustoServiceError."""
    # pylint: disable=protected-access

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put good message on Queue for sending
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))

    mock_azure_data_explorer_client_ingest_data.side_effect = KustoServiceError(
        "Message"
    )

    await azure_data_explorer_instance.async_send(0)
    mock_azure_data_explorer_client_ingest_data.assert_called_once()


async def test_async_KustoAuthenticationError(
    hass, mock_azure_data_explorer_client_ingest_data
):
    # pylint: disable=protected-access
    """Test parsing  with KustoAuthenticationError."""

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put good message on Queue for sending
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))

    mock_azure_data_explorer_client_ingest_data.side_effect = KustoAuthenticationError(
        authentication_method="AM", exception=Exception
    )

    await azure_data_explorer_instance.async_send(0)
    mock_azure_data_explorer_client_ingest_data.assert_called_once()


async def test_async_Exception(hass, mock_azure_data_explorer_client_ingest_data):
    # pylint: disable=protected-access
    """Test parsing  with Exception."""

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    state = State(
        entity_id="sensor.test_sensor",
        attributes="",
        context="",
        state="new",
        last_changed=utcnow(),
        last_updated=utcnow(),
    )

    # Put good message on Queue for sending
    await azure_data_explorer_instance._queue.put((2, (utcnow(), state)))

    mock_azure_data_explorer_client_ingest_data.side_effect = Exception("message")

    await azure_data_explorer_instance.async_send(0)
    mock_azure_data_explorer_client_ingest_data.assert_called_once()


async def test_put_event_on_queue(hass):
    # pylint: disable=protected-access
    """Test listening to events from Hass."""

    # Pass to old event
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    azure_data_explorer_instance = AzureDataExplorer(hass, entry)

    await azure_data_explorer_instance.async_start()

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=entry.options[CONF_SEND_INTERVAL])
    )

    await hass.async_block_till_done()

    # queue_empty = azure_data_explorer_instance._queue.empty()

    # assert equal(queue_empty, False)


@pytest.mark.parametrize(
    "filter_schema, tests",
    [
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["*.included_*"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("light.included", 1),
                FilterTest("light.excluded_test", 0),
                FilterTest("light.excluded", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("climate.included_test", 0),
            ],
        ),
        (
            {
                "include_entities": ["climate.included", "sensor.excluded_test"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("climate.included", 1),
                FilterTest("switch.excluded_test", 0),
                FilterTest("sensor.excluded_test", 1),
                FilterTest("light.excluded", 0),
                FilterTest("light.included", 1),
            ],
        ),
    ],
    ids=["allowlist", "denylist", "filtered_allowlist", "filtered_denylist"],
)
async def test_filter(hass, entry, tests, mock_azure_data_explorer_client_ingest_data):
    """Test different filters.

    Filter_schema is also a fixture which is replaced by the filter_schema
    in the parametrize and added to the entry fixture.
    """
    for test in tests:
        hass.states.async_set(test.entity_id, STATE_ON)
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=entry.options[CONF_SEND_INTERVAL])
        )
        await hass.async_block_till_done()
        # assert (
        #     mock_azure_data_explorer_client_ingest_data.add.call_count
        #     == test.expected_count
        # )
        mock_azure_data_explorer_client_ingest_data.add.reset_mock()
