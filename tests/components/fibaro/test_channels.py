"""Regression tests for independent firmware channels and the shared guard."""
import asyncio
import unittest
from unittest.mock import AsyncMock
from homeassistant.components.fibaro import firmware as fw

INFO = {"currentVersion": {"version": "5.220.15", "type": "stable"}}
DATA = {"updates": {"stable": {"available": True, "version": "5.220.19"},
                    "beta": {"available": True, "version": "5.221.22"},
                    "alpha": {"available": True, "version": "9.9.9"}},
        "conditions": {"storage": True, "allConditionsMet": True}}


class ChannelTests(unittest.TestCase):
    def test_both_channels_independent(self):
        for channel, version in (("stable", "5.220.19"), ("beta", "5.221.22")):
            state = fw.FirmwareState.from_api(INFO, DATA, [], selected_channel=channel)
            self.assertEqual((state.channel, state.latest, state.available), (channel, version, True))

    def test_stable_does_not_fall_back_to_beta(self):
        data = DATA | {"updateStableAvailable": False}
        state = fw.FirmwareState.from_api(INFO, data, [], selected_channel="stable")
        self.assertFalse(state.available)
        self.assertEqual(state.latest, "5.220.15")

    def test_beta_does_not_fall_back_to_stable(self):
        state = fw.FirmwareState.from_api(INFO, DATA | {"updateBetaAvailable": False}, [], selected_channel="beta")
        self.assertFalse(state.available)

    def test_beta_ready_while_stable_available(self):
        data = DATA | {"localUpdate": {"version": "5.221.22", "type": "stable", "status": "ReadyToInstall"}}
        beta = fw.FirmwareState.from_api(INFO, data, [], selected_channel="beta")
        stable = fw.FirmwareState.from_api(INFO, data, [], selected_channel="stable")
        self.assertTrue(beta.ready("5.221.22", "beta"))
        self.assertFalse(stable.ready("5.220.19", "stable"))

    def test_alpha_is_not_selectable(self):
        with self.assertRaises(fw.FirmwareError):
            fw.FirmwareState.from_api(INFO, DATA, [], selected_channel="alpha")

    def test_changelog_version(self):
        self.assertEqual(fw.changelog_url("5.220.15"), "https://changelog.yubii.cloud/?lang=EN&version=5.220.15&platform=HC3")
        self.assertIn("version=5.221.22&", fw.changelog_url("5.221.22"))
        self.assertIsNone(fw.changelog_url(None))

    def test_changelog_encodes_query(self):
        self.assertIn("version=5.1%26lang%3DXX", fw.changelog_url("5.1&lang=XX"))


class WorkflowChannelTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_beta_reads_beta_while_stable_available(self):
        workflow = fw.FirmwareWorkflow(AsyncMock(side_effect=[INFO, DATA, []]), channel="beta")
        state = await workflow.read()
        self.assertEqual(state.latest, "5.221.22")

    async def test_fallback_is_independent(self):
        info = INFO | {"updateStableAvailable": True, "newestStableVersion": "5.220.19",
                       "updateBetaAvailable": True, "newestBetaVersion": "5.221.22"}
        for channel, version in (("stable", "5.220.19"), ("beta", "5.221.22")):
            workflow = fw.FirmwareWorkflow(AsyncMock(side_effect=[info, fw.FirmwarePermissionError("403")]), channel=channel)
            state = await workflow.read(require_actions=False)
            self.assertEqual(state.latest, version)
            self.assertFalse(state.conditions_met)
            self.assertEqual(state.status_source, "settings/info")

    async def test_shared_guard_rejects_parallel_install_and_releases(self):
        guard = fw.FirmwareUpdateGuard()
        stable = fw.FirmwareWorkflow(AsyncMock(), channel="stable", guard=guard)
        beta = fw.FirmwareWorkflow(AsyncMock(), channel="beta", guard=guard)
        entered, finish = asyncio.Event(), asyncio.Event()
        async def install(*args):
            entered.set()
            await finish.wait()
        stable._install = install
        task = asyncio.create_task(stable.install("5.220.19", lambda *_: None, "stable"))
        await entered.wait()
        try:
            with self.assertRaisesRegex(fw.FirmwareError, "already running"):
                await beta.install("5.221.22", lambda *_: None, "beta")
            beta.request.assert_not_awaited()
            self.assertEqual(guard.channel, "stable")
        finally:
            finish.set()
            await task
        self.assertIsNone(guard.channel)
        beta._install = AsyncMock()
        await beta.install("5.221.22", lambda *_: None, "beta")
        beta._install.assert_awaited_once()

    async def test_guard_releases_on_failure(self):
        guard = fw.FirmwareUpdateGuard()
        workflow = fw.FirmwareWorkflow(AsyncMock(), channel="stable", guard=guard)
        workflow._install = AsyncMock(side_effect=fw.FirmwareError("test failure"))
        with self.assertRaises(fw.FirmwareError):
            await workflow.install("5.220.19", lambda *_: None, "stable")
        self.assertIsNone(guard.channel)

    async def test_wrong_channel_rejected(self):
        workflow = fw.FirmwareWorkflow(AsyncMock(), channel="stable")
        with self.assertRaisesRegex(fw.FirmwareError, "does not match"):
            await workflow.install("5.221.22", lambda *_: None, "beta")
        workflow.request.assert_not_awaited()
