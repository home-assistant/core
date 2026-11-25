"""Regression tests for release notes from the HC3 web UI endpoint."""
import asyncio
import unittest
from unittest.mock import AsyncMock
from homeassistant.components.fibaro import firmware as fw


class ReleaseNotesTests(unittest.IsolatedAsyncioTestCase):
    def test_markdown_multiline_bold(self):
        self.assertEqual(fw.changelog_markdown({"changelog": "<b>Notice\n\n    Hotfix</b>\n\tFixed bug.**"}),
                         "**Notice**\n\n**Hotfix**\n\nFixed bug.\\*\\*")

    def test_confirmation_dialog_excluded(self):
        self.assertEqual(fw.changelog_markdown({"changelog": "Notes", "confirmationDialog": {"message": "Terms"}}), "Notes")

    def test_html_escaped(self):
        notes = fw.changelog_markdown({"changelog": '<script>alert(1)</script> &amp; [bad](url)'})
        self.assertNotIn('<script>', notes)
        self.assertIn('&lt;script&gt;', notes)
        self.assertIn('\\[bad\\]', notes)

    def test_invalid_and_empty(self):
        with self.assertRaises(fw.FirmwareError):
            fw.changelog_markdown({"changelog": 123})
        self.assertIsNone(fw.changelog_markdown({"changelog": "  \n<b></b>"}))

    async def test_cache_and_version_change(self):
        request = AsyncMock(side_effect=[{"changelog": "Stable"}, {"changelog": "Beta"}])
        notes = fw.FirmwareReleaseNotes(request)
        self.assertEqual(await notes.get("5.220.19"), "Stable")
        self.assertEqual(await notes.get("5.220.19"), "Stable")
        request.assert_awaited_once_with("GET", "changelog", params={"version": "5.220.19", "lang": "en"})
        self.assertEqual(await notes.get("5.221.22"), "Beta")
        self.assertEqual(request.await_count, 2)

    async def test_retry_after_failure(self):
        request = AsyncMock(side_effect=[fw.FirmwarePermissionError("403"), {"changelog": ""}, {"changelog": "OK"}])
        notes = fw.FirmwareReleaseNotes(request)
        with self.assertRaises(fw.FirmwareError):
            await notes.get("5.221.22")
        self.assertIsNone(await notes.get("5.221.22"))
        self.assertEqual(await notes.get("5.221.22"), "OK")

    async def test_concurrent_requests_coalesced(self):
        request = AsyncMock(return_value={"changelog": "Notes"})
        notes = fw.FirmwareReleaseNotes(request)
        self.assertEqual(await asyncio.gather(notes.get("5.221.22"), notes.get("5.221.22")), ["Notes", "Notes"])
        request.assert_awaited_once()
