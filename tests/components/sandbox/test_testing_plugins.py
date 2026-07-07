"""Phase 10 tests: the ``hass_client.testing`` pytest plugins.

Two plugins are exercised here:

* ``hass_client.testing.pytest_plugin`` (in-process) — spins up a
  :class:`hass_client.sandbox.SandboxRuntime` as an asyncio task and
  joins it to the integration's manager-side bridge with an in-memory
  channel pair.
* ``hass_client.testing.conftest_sandbox`` (subprocess) — registers the
  ``no_sandbox_freezer`` marker and skips tests that combine ``freezer``
  with the real-subprocess sandbox.

The real-subprocess fixture itself is covered by
:mod:`test_phase4_subprocess` which already drives ``SandboxManager``
through a real subprocess; the tests here unit-check the hook shape
without spawning a nested pytest run.
"""

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

from hass_client.testing import conftest_sandbox as cs_plugin
from hass_client.testing.pytest_plugin import (
    DEFAULT_GROUP,
    InProcessSandbox,
    async_setup_inprocess_sandbox,
)
import pytest

from homeassistant.components.sandbox.const import DATA_SANDBOX_V2
from homeassistant.core import HomeAssistant


@pytest.fixture(name="in_process_sandbox")
async def _in_process_sandbox_fixture(
    hass: HomeAssistant, tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[InProcessSandbox]:
    """Local copy of the ``sandbox_inprocess`` fixture for these tests.

    The plugin fixture is defined under ``hass_client.testing`` and the
    HA Core tests don't load that plugin by default — replicating the
    setup here keeps the assertion close to what the plugin guarantees.
    """
    config_dir = tmp_path_factory.mktemp("sandbox_inproc")
    sandbox = await async_setup_inprocess_sandbox(
        hass, group=DEFAULT_GROUP, config_dir=str(config_dir)
    )
    try:
        yield sandbox
    finally:
        await sandbox.stop()


async def test_inprocess_plugin_wires_manager_and_bridge(
    hass: HomeAssistant, in_process_sandbox: InProcessSandbox
) -> None:
    """The plugin installs a bridge for the group and parks a fake process."""
    data = hass.data[DATA_SANDBOX_V2]
    assert in_process_sandbox.group == DEFAULT_GROUP
    assert DEFAULT_GROUP in data.channels
    assert DEFAULT_GROUP in data.bridges
    manager = data.manager
    assert manager is not None
    sandbox = manager.get(DEFAULT_GROUP)
    assert sandbox is not None
    assert sandbox.state == "running"
    # The runtime task is still alive — set ready and serving.
    assert not in_process_sandbox.runtime_task.done()


async def test_inprocess_plugin_round_trips_ping(
    hass: HomeAssistant, in_process_sandbox: InProcessSandbox
) -> None:
    """The in-memory channel speaks the real sandbox protocol.

    Calling ``sandbox/ping`` on the manager-side channel reaches the
    runtime's handler and returns the same payload a subprocess would.
    """
    data = hass.data[DATA_SANDBOX_V2]
    channel = data.channels[DEFAULT_GROUP]
    result = await asyncio.wait_for(channel.call("sandbox/ping", None), timeout=2.0)
    assert result.pong == "sandbox"


async def test_inprocess_plugin_returns_existing_sandbox_on_ensure_started(
    hass: HomeAssistant, in_process_sandbox: InProcessSandbox
) -> None:
    """``ensure_started`` returns the pre-installed sandbox without spawning."""
    data = hass.data[DATA_SANDBOX_V2]
    manager = data.manager
    assert manager is not None
    existing = manager.get(DEFAULT_GROUP)
    fresh = await manager.ensure_started(DEFAULT_GROUP)
    assert fresh is existing


def _make_item(
    *, fixturenames: tuple[str, ...] = (), markers: tuple[str, ...] = ()
) -> MagicMock:
    """Construct a fake pytest item with the given fixtures/markers."""
    item = MagicMock(spec=pytest.Item)
    item.fixturenames = fixturenames
    item.get_closest_marker.side_effect = lambda name: (
        MagicMock() if name in markers else None
    )
    item.add_marker = MagicMock()
    return item


def test_conftest_sandbox_skips_freezer_tests() -> None:
    """A test that takes a ``freezer`` fixture gets a skip marker added."""
    item = _make_item(fixturenames=("freezer",))
    cs_plugin.pytest_collection_modifyitems(MagicMock(), [item])
    assert item.add_marker.called
    # The marker passed in is the skip marker constructed inline; sanity-
    # check the call shape rather than the exact MarkDecorator identity.
    args, _ = item.add_marker.call_args
    assert args[0].name == "skip"


def test_conftest_sandbox_skips_marker_tagged_tests() -> None:
    """A test marked ``@pytest.mark.no_sandbox_freezer`` is skipped."""
    item = _make_item(markers=("no_sandbox_freezer",))
    cs_plugin.pytest_collection_modifyitems(MagicMock(), [item])
    assert item.add_marker.called
    args, _ = item.add_marker.call_args
    assert args[0].name == "skip"


def test_conftest_sandbox_leaves_unrelated_tests_alone() -> None:
    """Tests without the freezer fixture or marker are left untouched."""
    item = _make_item(fixturenames=("hass",))
    cs_plugin.pytest_collection_modifyitems(MagicMock(), [item])
    assert not item.add_marker.called


def test_autotag_sets_mock_config_entry_sandbox() -> None:
    """``install_mock_config_entry_autotag`` sets ``entry.sandbox`` on ``add_to_hass``.

    Drives the patch end-to-end against a real ``MockConfigEntry``: a
    built-in domain (``light``) classifies to ``built-in``, the patch
    sets the first-class ``ConfigEntry.sandbox`` field (without
    touching ``entry.data``), and ``restore()`` puts the original
    method back.
    """
    from hass_client.testing._autotag import (  # noqa: PLC0415
        install_mock_config_entry_autotag,
    )

    from tests.common import MockConfigEntry  # noqa: PLC0415

    fake_hass = MagicMock()
    fake_hass.config_entries._entries = {}

    restore = install_mock_config_entry_autotag()
    try:
        entry = MockConfigEntry(domain="light", data={"foo": "bar"})
        assert entry.sandbox is None
        entry.add_to_hass(fake_hass)
        assert entry.sandbox == "built-in"
        # entry.data is untouched — this is the whole point of Phase 17.
        assert dict(entry.data) == {"foo": "bar"}
        assert fake_hass.config_entries._entries == {entry.entry_id: entry}

        # ALWAYS_MAIN domains are skipped — entry stays untagged.
        main_entry = MockConfigEntry(domain="automation", data={})
        main_entry.add_to_hass(fake_hass)
        assert main_entry.sandbox is None

        # An entry that already carries the tag is left alone.
        tagged = MockConfigEntry(domain="light", sandbox="custom")
        tagged.add_to_hass(fake_hass)
        assert tagged.sandbox == "custom"
    finally:
        restore()

    # After restoring, ``add_to_hass`` is no longer patched: a fresh entry
    # for a sandboxable domain does not get the tag injected.
    untagged = MockConfigEntry(domain="light", data={})
    untagged.add_to_hass(fake_hass)
    assert untagged.sandbox is None


def test_conftest_sandbox_registers_marker_in_configure() -> None:
    """``pytest_configure`` adds the marker line so pytest --strict-markers passes."""
    config = MagicMock()
    try:
        cs_plugin.pytest_configure(config)
        config.addinivalue_line.assert_called_once()
        args, _ = config.addinivalue_line.call_args
        assert args[0] == "markers"
        assert args[1].startswith("no_sandbox_freezer:")
    finally:
        # ``pytest_configure`` also installs the autotag monkey-patch;
        # tear it down so the rest of the suite sees the original
        # ``MockConfigEntry.add_to_hass``.
        cs_plugin.pytest_unconfigure(config)
