"""Fixtures for Aprilaire integration."""

import asyncio

import pytest


@pytest.fixture(autouse=True)
def verify_cleanup(event_loop: asyncio.AbstractEventLoop):
    """Verify that the test has cleaned up resources correctly."""
    tasks_before = asyncio.all_tasks(event_loop)
    yield
    tasks = asyncio.all_tasks(event_loop) - tasks_before
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))
