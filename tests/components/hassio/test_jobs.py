"""Test supervisor jobs manager."""

from collections.abc import Generator
from datetime import datetime
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from aiohasupervisor.models import Job, JobsInfo
import pytest

from homeassistant.components.hassio.const import ADDONS_COORDINATOR
from homeassistant.components.hassio.coordinator import HassioDataUpdateCoordinator
from homeassistant.components.hassio.jobs import JobSubscription
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def fixture_supervisor_environ() -> Generator[None]:
    """Mock os environ for supervisor."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        yield


@pytest.mark.usefixtures("all_setup_requests")
async def test_job_manager_setup(hass: HomeAssistant, jobs_info: AsyncMock) -> None:
    """Test setup of job manager."""
    jobs_info.return_value = JobsInfo(
        ignore_conditions=[],
        jobs=[
            Job(
                name="test_job",
                reference=None,
                uuid=uuid4(),
                progress=0,
                stage=None,
                done=False,
                errors=[],
                created=datetime.now(),
                extra=None,
                child_jobs=[
                    Job(
                        name="test_inner_job",
                        reference=None,
                        uuid=uuid4(),
                        progress=0,
                        stage=None,
                        done=False,
                        errors=[],
                        created=datetime.now(),
                        extra=None,
                        child_jobs=[],
                    )
                ],
            )
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result
    jobs_info.assert_called_once()

    data_coordinator: HassioDataUpdateCoordinator = hass.data[ADDONS_COORDINATOR]
    assert len(data_coordinator.jobs.current_jobs) == 2
    assert data_coordinator.jobs.current_jobs[0].name == "test_job"
    assert data_coordinator.jobs.current_jobs[1].name == "test_inner_job"


@pytest.mark.usefixtures("all_setup_requests")
async def test_disconnect_on_config_entry_reload(
    hass: HomeAssistant, jobs_info: AsyncMock
) -> None:
    """Test dispatcher subscription disconnects on config entry reload."""
    result = await async_setup_component(hass, "hassio", {})
    assert result
    jobs_info.assert_called_once()

    jobs_info.reset_mock()
    data_coordinator: HassioDataUpdateCoordinator = hass.data[ADDONS_COORDINATOR]
    await hass.config_entries.async_reload(data_coordinator.entry_id)
    await hass.async_block_till_done()
    jobs_info.assert_called_once()


@pytest.mark.usefixtures("all_setup_requests")
async def test_job_manager_ws_updates(
    hass: HomeAssistant, jobs_info: AsyncMock, hass_ws_client: WebSocketGenerator
) -> None:
    """Test job updates sync from Supervisor WS messages."""
    result = await async_setup_component(hass, "hassio", {})
    assert result
    jobs_info.assert_called_once()

    jobs_info.reset_mock()
    client = await hass_ws_client(hass)
    data_coordinator: HassioDataUpdateCoordinator = hass.data[ADDONS_COORDINATOR]
    assert not data_coordinator.jobs.current_jobs

    # Make an example listener
    job_data: Job | None = None

    @callback
    def mock_subcription_callback(job: Job) -> None:
        nonlocal job_data
        job_data = job

    subscription = JobSubscription(
        mock_subcription_callback, name="test_job", reference="test"
    )
    unsubscribe = data_coordinator.jobs.subscribe(subscription)

    # Send start of job update
    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {
                    "name": "test_job",
                    "reference": "test",
                    "uuid": (uuid := uuid4().hex),
                    "progress": 0,
                    "stage": None,
                    "done": False,
                    "errors": [],
                    "created": (created := datetime.now().isoformat()),
                    "extra": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    assert job_data.progress == 0
    assert job_data.done is False
    # One job in the cache
    assert len(data_coordinator.jobs.current_jobs) == 1

    # Example progress update
    await client.send_json(
        {
            "id": 2,
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {
                    "name": "test_job",
                    "reference": "test",
                    "uuid": uuid,
                    "progress": 50,
                    "stage": None,
                    "done": False,
                    "errors": [],
                    "created": created,
                    "extra": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    assert job_data.progress == 50
    assert job_data.done is False
    # Same job, same number of jobs in cache
    assert len(data_coordinator.jobs.current_jobs) == 1

    # Unrelated job update - name change, subscriber should not receive
    await client.send_json(
        {
            "id": 3,
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {
                    "name": "bad_job",
                    "reference": "test",
                    "uuid": uuid4().hex,
                    "progress": 0,
                    "stage": None,
                    "done": False,
                    "errors": [],
                    "created": created,
                    "extra": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    # New job, cache increases
    assert len(data_coordinator.jobs.current_jobs) == 2

    # Unrelated job update - reference change, subscriber should not receive
    await client.send_json(
        {
            "id": 4,
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {
                    "name": "test_job",
                    "reference": "bad",
                    "uuid": uuid4().hex,
                    "progress": 0,
                    "stage": None,
                    "done": False,
                    "errors": [],
                    "created": created,
                    "extra": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    # New job, cache increases
    assert len(data_coordinator.jobs.current_jobs) == 3

    # Unsubscribe mock listener, should not receive final update
    unsubscribe()
    await client.send_json(
        {
            "id": 5,
            "type": "supervisor/event",
            "data": {
                "event": "job",
                "data": {
                    "name": "test_job",
                    "reference": "test",
                    "uuid": uuid,
                    "progress": 100,
                    "stage": None,
                    "done": True,
                    "errors": [],
                    "created": created,
                    "extra": None,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    assert job_data.progress == 50
    assert job_data.done is False
    # Job ended, cache decreases
    assert len(data_coordinator.jobs.current_jobs) == 2

    # REST API should not be used during this sequence
    jobs_info.assert_not_called()


@pytest.mark.usefixtures("all_setup_requests")
async def test_job_manager_reload_on_supervisor_restart(
    hass: HomeAssistant, jobs_info: AsyncMock, hass_ws_client: WebSocketGenerator
) -> None:
    """Test job manager reloads cache on supervisor restart."""
    jobs_info.return_value = JobsInfo(
        ignore_conditions=[],
        jobs=[
            Job(
                name="test_job",
                reference="test",
                uuid=uuid4(),
                progress=0,
                stage=None,
                done=False,
                errors=[],
                created=datetime.now(),
                extra=None,
                child_jobs=[],
            )
        ],
    )

    result = await async_setup_component(hass, "hassio", {})
    assert result
    jobs_info.assert_called_once()

    data_coordinator: HassioDataUpdateCoordinator = hass.data[ADDONS_COORDINATOR]
    assert len(data_coordinator.jobs.current_jobs) == 1
    assert data_coordinator.jobs.current_jobs[0].name == "test_job"

    jobs_info.reset_mock()
    jobs_info.return_value = JobsInfo(ignore_conditions=[], jobs=[])
    client = await hass_ws_client(hass)

    # Make an example listener
    job_data: Job | None = None

    @callback
    def mock_subcription_callback(job: Job) -> None:
        nonlocal job_data
        job_data = job

    subscription = JobSubscription(mock_subcription_callback, name="test_job")
    data_coordinator.jobs.subscribe(subscription)

    # Send supervisor restart signal
    await client.send_json(
        {
            "id": 1,
            "type": "supervisor/event",
            "data": {
                "event": "supervisor_update",
                "update_key": "supervisor",
                "data": {"startup": "complete"},
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    # Listener should be told job is done and cache cleared out
    jobs_info.assert_called_once()
    assert job_data.name == "test_job"
    assert job_data.reference == "test"
    assert job_data.done is True
    assert not data_coordinator.jobs.current_jobs
