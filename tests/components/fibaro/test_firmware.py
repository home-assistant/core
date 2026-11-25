"""Test the Fibaro firmware API workflow."""

import unittest
from unittest.mock import AsyncMock, patch

from homeassistant.components.fibaro import firmware as fw

OLD, NEW = "5.180.0", "5.190.0"


def snapshot(status=None, progress=None, version=NEW, channel="stable", installed=OLD, available=True, conditions=True, active=False):
    return fw.FirmwareState.from_api(
        {"softVersion": installed},
        {"updateStableAvailable": available, "newestStableVersion": NEW,
         "conditions": {"storage": conditions, "allConditionsMet": conditions},
         "localUpdate": {"status": status, "progress": progress, "version": version, "type": channel}},
        [{"name": "installUpdate", "status": "running"}] if active else [],
    )


class ParserTests(unittest.TestCase):
    def test_nested_schema(self):
        state = fw.FirmwareState.from_api({"softVersion": OLD}, {"updates": {"stable": {"available": True, "version": NEW}}, "conditions": {"allConditionsMet": True, "storage": True}}, [])
        self.assertEqual(state.latest, NEW)
        self.assertTrue(state.available)

    def test_no_update(self):
        state = snapshot(available=False)
        self.assertEqual(state.latest, OLD)
        self.assertFalse(state.available)

    def test_progress(self):
        self.assertEqual(snapshot("Downloading", 0).progress, 0)
        self.assertEqual(snapshot("Downloading", 65).progress, 65)
        self.assertIsNone(snapshot("Downloading", True).progress)
        self.assertIsNone(snapshot("Downloading", 101).progress)
        self.assertTrue(snapshot("Downloading", 100).active)

    def test_matching_download(self):
        self.assertTrue(snapshot("ReadyToInstall", 100).ready(NEW))
        self.assertFalse(snapshot("Downloading", 100).ready(NEW))
        self.assertFalse(snapshot("ReadyToInstall", 100, version=OLD).ready(NEW))
        self.assertFalse(snapshot("ReadyToInstall", 100, channel="beta").ready(NEW))

    def test_external_action(self):
        self.assertTrue(snapshot(active=True).active)


BETA = "5.191.1"


def beta_snapshot(status=None, progress=None, *, local_type="beta", installed=OLD,
                  beta_available=True, stable_available=False, nested=False, allow_beta=True):
    data = {"conditions": {"storage": True, "allConditionsMet": True},
            "localUpdate": {"status": status, "progress": progress,
                            "version": BETA, "type": local_type}}
    if nested:
        data["updates"] = {"stable": {"available": stable_available, "version": NEW},
                           "beta": {"available": beta_available, "version": BETA},
                           "alpha": {"available": True, "version": "9.9.9"}}
    else:
        data.update(updateStableAvailable=stable_available, newestStableVersion=NEW,
                    updateBetaAvailable=beta_available, newestBetaVersion=BETA)
    return fw.FirmwareState.from_api({"softVersion": installed}, data, [], allow_beta)


class BetaParserTests(unittest.TestCase):
    def test_flat_beta(self):
        state = beta_snapshot()
        self.assertEqual((state.latest, state.channel, state.available), (BETA, "beta", True))

    def test_nested_beta(self):
        self.assertEqual(beta_snapshot(nested=True).latest, BETA)

    def test_stable_priority(self):
        state = beta_snapshot(stable_available=True)
        self.assertEqual((state.latest, state.channel), (NEW, "stable"))

    def test_stable_only(self):
        self.assertFalse(beta_snapshot(allow_beta=False).available)

    def test_ignore_alpha(self):
        self.assertFalse(beta_snapshot(beta_available=False, nested=True).available)

    def test_already_installed_beta(self):
        self.assertFalse(beta_snapshot(installed=BETA).available)

    def test_beta_progress_and_matching_channel(self):
        self.assertEqual(beta_snapshot("Downloading", 65).progress, 65)
        self.assertTrue(beta_snapshot("ReadyToInstall", 100).ready(BETA, "beta"))
        self.assertTrue(beta_snapshot("ReadyToInstall", 100, local_type="stable").ready(BETA, "beta"))
        self.assertFalse(beta_snapshot("ReadyToInstall", 100, local_type="alpha").ready(BETA, "beta"))
        self.assertFalse(beta_snapshot("ReadyToInstall", 100, local_type=None).ready(BETA, "beta"))
        self.assertFalse(beta_snapshot("ReadyToInstall", 100, local_type="stable", allow_beta=False).ready(BETA, "beta"))

    def test_missing_beta_version(self):
        with self.assertRaisesRegex(fw.FirmwareError, "Missing beta firmware version"):
            fw.FirmwareState.from_api({"softVersion": OLD}, {"updateStableAvailable": False, "updateBetaAvailable": True}, [])


def observed_ready_beta():
    return fw.FirmwareState.from_api(
        {"currentVersion": {"version": "5.220.19", "type": "stable"}},
        {"updates": {"stable": {"available": False, "version": "5.220.19"},
                     "beta": {"available": True, "version": "5.221.22"},
                     "alpha": {"available": False, "version": "5.000.000"}},
         "conditions": {"storage": True, "allConditionsMet": True},
         "localUpdate": {"status": "ReadyToInstall", "type": "stable",
                         "version": "5.221.22", "masterOnly": False},
         "updateStableAvailable": False, "updateBetaAvailable": True,
         "newestStableVersion": "5.220.19", "newestBetaVersion": "5.221.22",
         "allConditionsMet": True},
        [{"name": "downloadUpdate", "status": "done",
          "request": {"action": "download", "params": {"version": "5.221.22"}}}],
    )


class ObservedResponseTests(unittest.TestCase):
    def test_observed_ready_beta_without_progress(self):
        state = observed_ready_beta()
        self.assertEqual(state.local_type, "stable")
        self.assertIsNone(state.progress)
        self.assertTrue(state.ready("5.221.22", "beta"))
        self.assertFalse(state.active)

    def test_observed_wrong_version(self):
        state = fw.replace(observed_ready_beta(), local_version="5.220.19")
        self.assertFalse(state.ready("5.221.22", "beta"))

    def test_documented_active_statuses(self):
        for status in ("pending", "running"):
            state = fw.FirmwareState.from_api(
                {"softVersion": OLD}, {"updateStableAvailable": False},
                [{"name": "installUpdate", "status": status}],
            )
            self.assertTrue(state.active)


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workflow = fw.FirmwareWorkflow(AsyncMock())
        self.workflow.read = AsyncMock()
        self.workflow.start = AsyncMock(side_effect=["download-id", "install-id"])
        self.workflow.action_status = AsyncMock(return_value="done")
        self.events = []
        self.sleep = patch.object(fw.asyncio, "sleep", new=AsyncMock())
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def publish(self, state, phase):
        self.events.append((state, phase))

    async def test_observed_cached_beta_installs_without_redownload(self):
        ready = observed_ready_beta()
        self.workflow.read.side_effect = [ready, ready, fw.replace(ready, installed="5.221.22", available=False)]
        await self.workflow.install("5.221.22", self.publish, "beta")
        self.workflow.start.assert_awaited_once_with("install", {"backupType": "local", "masterOnly": True})

    async def test_observed_beta_download_transitions_to_install(self):
        ready = observed_ready_beta()
        self.workflow.read.side_effect = [fw.replace(ready, local_status=None),
            fw.replace(ready, local_status="Downloading", active=True, progress=42),
            ready, ready, fw.replace(ready, installed="5.221.22", available=False)]
        await self.workflow.install("5.221.22", self.publish, "beta")
        self.assertEqual(self.workflow.start.await_args_list, [
            unittest.mock.call("download", {"version": "5.221.22"}),
            unittest.mock.call("install", {"backupType": "local", "masterOnly": True})])
        self.assertTrue(any(s and s.progress == 42 for s, _ in self.events))

    async def test_finished_download_wrong_version_fails_immediately(self):
        ready = observed_ready_beta()
        self.workflow.read.side_effect = [fw.replace(ready, local_status=None),
                                         fw.replace(ready, local_version="5.220.19")]
        with self.assertRaisesRegex(fw.FirmwareError, "does not match"):
            await self.workflow.install("5.221.22", self.publish, "beta")
        self.workflow.start.assert_awaited_once_with("download", {"version": "5.221.22"})

    async def test_download_install_reboot(self):
        ready = snapshot("ReadyToInstall", 100)
        self.workflow.read.side_effect = [snapshot(), snapshot("Downloading", 65), ready, ready, fw.FirmwareConnectionError(), snapshot(installed=NEW, available=False)]
        await self.workflow.install(NEW, self.publish)
        self.assertEqual(self.workflow.start.await_args_list, [unittest.mock.call("download", {"version": NEW}), unittest.mock.call("install", {"backupType": "local", "masterOnly": True})])
        self.assertIn((None, "install"), self.events)
        self.assertTrue(any(s and s.progress == 65 for s, _ in self.events))

    async def test_cached_matching_download(self):
        ready = snapshot("ReadyToInstall", 100)
        self.workflow.read.side_effect = [ready, ready, snapshot(installed=NEW, available=False)]
        await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_awaited_once_with("install", {"backupType": "local", "masterOnly": True})

    async def test_checksum_failure(self):
        self.workflow.read.side_effect = [snapshot(), snapshot("ChecksumError")]
        with self.assertRaisesRegex(fw.FirmwareError, "ChecksumError"):
            await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_awaited_once_with("download", {"version": NEW})

    async def test_conditions_not_met(self):
        self.workflow.read.return_value = snapshot(conditions=False)
        with self.assertRaisesRegex(fw.FirmwareError, "conditions"):
            await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_not_awaited()

    async def test_external_action_blocks_install(self):
        self.workflow.read.return_value = snapshot(active=True)
        with self.assertRaisesRegex(fw.FirmwareError, "already active"):
            await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_not_awaited()

    async def test_version_changed_before_install(self):
        self.workflow.read.side_effect = [snapshot("ReadyToInstall", 100), snapshot("ReadyToInstall", 100, version=OLD)]
        with self.assertRaisesRegex(fw.FirmwareError, "not ready"):
            await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_not_awaited()

    async def test_install_post_disconnect_not_retried(self):
        ready = snapshot("ReadyToInstall", 100)
        self.workflow.read.side_effect = [ready, ready, snapshot(installed=NEW, available=False)]
        self.workflow.start.side_effect = fw.FirmwareConnectionError()
        await self.workflow.install(NEW, self.publish)
        self.workflow.start.assert_awaited_once()

    async def test_install_action_failed(self):
        ready = snapshot("ReadyToInstall", 100)
        self.workflow.read.side_effect = [ready, ready, snapshot()]
        self.workflow.action_status.return_value = "failed"
        with self.assertRaisesRegex(fw.FirmwareError, "installation action failed"):
            await self.workflow.install(NEW, self.publish)


    async def test_beta_download_install_reboot(self):
        ready = beta_snapshot("ReadyToInstall", 100)
        self.workflow.read.side_effect = [beta_snapshot(), beta_snapshot("Downloading", 65), ready, ready, fw.FirmwareConnectionError(), beta_snapshot(installed=BETA, beta_available=False)]
        await self.workflow.install(BETA, self.publish, "beta")
        self.assertEqual(self.workflow.start.await_args_list, [unittest.mock.call("download", {"version": BETA}), unittest.mock.call("install", {"backupType": "local", "masterOnly": True})])
        self.assertTrue(any(s and s.progress == 65 for s, _ in self.events))

    async def test_beta_alpha_label_before_install(self):
        self.workflow.read.side_effect = [beta_snapshot("ReadyToInstall", 100), beta_snapshot("ReadyToInstall", 100, local_type="alpha")]
        with self.assertRaisesRegex(fw.FirmwareError, "not ready"):
            await self.workflow.install(BETA, self.publish, "beta")
        self.workflow.start.assert_not_awaited()

    async def test_stable_becomes_available_before_beta_install(self):
        self.workflow.read.side_effect = [beta_snapshot("ReadyToInstall", 100), beta_snapshot("ReadyToInstall", 100, stable_available=True)]
        with self.assertRaisesRegex(fw.FirmwareError, "no longer available"):
            await self.workflow.install(BETA, self.publish, "beta")
        self.workflow.start.assert_not_awaited()

    async def test_beta_disabled_blocks_install(self):
        self.workflow.allow_beta = False
        with self.assertRaisesRegex(fw.FirmwareError, "disabled"):
            await self.workflow.install(BETA, self.publish, "beta")
        self.workflow.start.assert_not_awaited()


class ReadTests(unittest.IsolatedAsyncioTestCase):
    def make_workflow(self, actions):
        return fw.FirmwareWorkflow(AsyncMock(side_effect=[
            {"softVersion": "5.220.19"},
            {"updateStableAvailable": False, "updateBetaAvailable": True,
             "newestBetaVersion": "5.221.22", "localUpdate": {"status": "Downloading", "progress": 42},
             "conditions": {"storage": True, "allConditionsMet": True}},
            actions,
        ]))

    async def test_beta_without_action_permission(self):
        workflow = self.make_workflow(fw.FirmwareError("GET /api/service/actions: HTTP 403"))
        state = await workflow.read(require_actions=False)
        self.assertEqual((state.installed, state.latest, state.channel, state.progress),
                         ("5.220.19", "5.221.22", "beta", 42))
        self.assertTrue(state.available)
        self.assertTrue(state.active)
        self.assertIn("403", state.action_error)

    async def test_installation_requires_actions(self):
        workflow = self.make_workflow(fw.FirmwareError("GET /api/service/actions: HTTP 403"))
        with self.assertRaisesRegex(fw.FirmwareError, "403"):
            await workflow.install("5.221.22", lambda *args: None, "beta")
        self.assertEqual([call.args[0] for call in workflow.request.await_args_list], ["GET"] * 3)

    async def test_invalid_action_response_not_fatal_for_detection(self):
        state = await self.make_workflow({"actions": []}).read(require_actions=False)
        self.assertTrue(state.available)
        self.assertIn("expected a list", state.action_error)

    async def test_action_list_success(self):
        state = await self.make_workflow([]).read(require_actions=False)
        self.assertIsNone(state.action_error)
        self.assertEqual(state.latest, "5.221.22")

    async def test_required_endpoint_failure(self):
        workflow = fw.FirmwareWorkflow(AsyncMock(side_effect=[{"softVersion": OLD}, fw.FirmwareError("GET /api/update: HTTP 403")]))
        with self.assertRaisesRegex(fw.FirmwareError, "GET /api/update"):
            await workflow.read(require_actions=False)


class NodeRedFallbackTests(unittest.IsolatedAsyncioTestCase):
    def info(self):
        return {"currentVersion": {"version": "5.220.19", "type": "stable"},
                "updateStableAvailable": False, "updateBetaAvailable": True,
                "newestBetaVersion": "5.221.22"}

    async def test_settings_info_fallback(self):
        request = AsyncMock(side_effect=[self.info(), fw.FirmwarePermissionError("HTTP 403")])
        state = await fw.FirmwareWorkflow(request).read(require_actions=False)
        self.assertEqual((state.installed, state.latest, state.channel), ("5.220.19", "5.221.22", "beta"))
        self.assertTrue(state.available)
        self.assertEqual(state.status_source, "settings/info")
        self.assertFalse(state.conditions_met)
        self.assertIsNone(state.progress)
        self.assertIn("403", state.action_error)
        self.assertEqual(request.await_count, 2)

    async def test_anonymous_info_fallback(self):
        request = AsyncMock(side_effect=[{"softVersion": "5.220.19"}, fw.FirmwarePermissionError("HTTP 403"), self.info()])
        state = await fw.FirmwareWorkflow(request).read(require_actions=False)
        self.assertEqual(state.latest, "5.221.22")
        request.assert_awaited_with("GET", "settings/info", anonymous=True)

    async def test_install_denied_no_post(self):
        request = AsyncMock(side_effect=[self.info(), fw.FirmwarePermissionError("HTTP 403")])
        with self.assertRaises(fw.FirmwarePermissionError):
            await fw.FirmwareWorkflow(request).install("5.221.22", lambda *_: None, "beta")
        self.assertEqual([c.args[0] for c in request.await_args_list], ["GET", "GET"])

    async def test_no_update_fallback(self):
        info = self.info() | {"updateBetaAvailable": False}
        request = AsyncMock(side_effect=[info, fw.FirmwarePermissionError("HTTP 403")])
        state = await fw.FirmwareWorkflow(request).read(require_actions=False)
        self.assertFalse(state.available)
        self.assertEqual(state.latest, state.installed)

    async def test_missing_data_not_reported_as_up_to_date(self):
        info = {"softVersion": "5.220.19"}
        request = AsyncMock(side_effect=[info, fw.FirmwarePermissionError("HTTP 403"), info])
        with self.assertRaises(fw.FirmwareError):
            await fw.FirmwareWorkflow(request).read(require_actions=False)


if __name__ == "__main__":
    unittest.main()
