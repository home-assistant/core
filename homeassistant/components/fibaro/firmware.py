"""HC3 firmware workflow based on the v5.071 REST API."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from html import escape, unescape
import re
from time import monotonic
from typing import Any
from urllib.parse import quote, urlencode

ACTIVE_ACTIONS = {"pending", "running"}
UPDATE_ACTIONS = {"autoUpdate", "downloadUpdate", "installUpdate"}
DOWNLOAD_ERRORS = {"Canceled", "ChecksumError", "DownloadingError"}
POLL_SECONDS = 5
TIMEOUT = 1800


class FirmwareError(Exception):
    """A firmware update could not safely proceed."""


class FirmwarePermissionError(FirmwareError):
    """The hub refused access to an API endpoint."""


class FirmwareConnectionError(FirmwareError):
    """Temporary loss of connection to the hub."""


def changelog_url(version: str | None, platform: str = "HC3") -> str | None:
    """Link to the vendor's changelog for the specific firmware version."""
    if not version:
        return None
    return "https://changelog.yubii.cloud/?" + urlencode({
        "lang": "EN", "version": version, "platform": platform,
    })



def changelog_markdown(payload: Any) -> str | None:
    """Convert the HC3's mixed plain text and bold markup to safe Markdown."""
    if not isinstance(payload, dict) or not isinstance(payload.get("changelog"), str):
        raise FirmwareError("GET changelog: missing changelog text")
    text = payload["changelog"]
    # HC3 uses <b> across multiple paragraphs, tabs and plain text. Escape
    # all other markup instead of passing arbitrary hub HTML to the frontend.
    bold = False
    paragraphs = []
    for line in text.splitlines():
        parts = []
        for part in re.split(r"(</?b\s*>)", line, flags=re.IGNORECASE):
            if re.fullmatch(r"<b\s*>", part, re.IGNORECASE):
                bold = True
            elif re.fullmatch(r"</b\s*>", part, re.IGNORECASE):
                bold = False
            elif part.strip():
                value = escape(unescape(part.strip()), quote=False)
                value = re.sub(r"([\\`*_\[\]~#|])", r"\\\1", value)
                value = re.sub(r"^(\d+)\.(?=\s)", r"\1\\.", value)
                if value.startswith(("- ", "+ ")):
                    value = "\\" + value
                if parts and part[:1].isspace():
                    parts.append(" ")
                parts.append(f"**{value}**" if bold else value)
                if part[-1:].isspace():
                    parts.append(" ")
        if paragraph := "".join(parts).strip():
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs) or None


class FirmwareReleaseNotes:
    """Fetch release notes on demand and cache successful results by version."""

    def __init__(self, request: Callable[..., Awaitable[Any]]) -> None:
        self._request = request
        self._cached: tuple[str, str] | None = None
        self._lock = asyncio.Lock()

    async def get(self, version: str) -> str | None:
        async with self._lock:
            if self._cached and self._cached[0] == version:
                return self._cached[1]
            payload = await self._request(
                "GET", "changelog", params={"version": version, "lang": "en"}
            )
            notes = changelog_markdown(payload)
            if notes:
                self._cached = (version, notes)
            return notes


class FirmwareUpdateGuard:
    """One firmware operation at a time per Home Center, across entities."""

    def __init__(self) -> None:
        self.channel: str | None = None

    def claim(self, channel: str) -> None:
        """Reject, rather than queue, another installation."""
        if self.channel is not None:
            raise FirmwareError("A firmware update is already running on this Home Center")
        self.channel = channel

    def release(self) -> None:
        self.channel = None



@dataclass(frozen=True)
class FirmwareState:
    """Current firmware and update state."""

    installed: str
    latest: str | None
    available: bool
    conditions_met: bool
    local_status: str | None
    local_version: str | None
    local_type: str | None
    progress: int | None
    active: bool
    channel: str | None
    action_error: str | None = None
    status_source: str = "update"

    @classmethod
    def from_api(cls, info: dict, data: dict, actions: list, allow_beta: bool = True, *, selected_channel: str | None = None) -> "FirmwareState":
        """Read one explicit channel, or use the legacy stable-first mode."""
        updates = data.get("updates") or {}
        current = info.get("currentVersion") or {}
        installed = current.get("version") or info.get("softVersion")
        if not installed:
            installed = (data.get("currentVersion") or {}).get("version")
        if not isinstance(installed, str) or not installed:
            raise FirmwareError("Missing installed firmware version")
        channel = None
        latest = installed
        candidates = ("stable", "beta") if allow_beta else ("stable",)
        if selected_channel is not None:
            if selected_channel not in candidates:
                raise FirmwareError("Unsupported firmware channel")
            candidates = (selected_channel,)
        for candidate in candidates:
            nested = updates.get(candidate) or {}
            flag = data.get(f"update{candidate.title()}Available", nested.get("available"))
            version = data.get(f"newest{candidate.title()}Version") or nested.get("version")
            if flag is None and candidate == "beta" and selected_channel is None:
                continue  # Older stable-only API.
            if type(flag) is not bool:
                raise FirmwareError(f"Invalid {candidate} update flag")
            if flag:
                if not isinstance(version, str) or not version:
                    raise FirmwareError(f"Missing {candidate} firmware version")
                if version != installed:
                    channel, latest = candidate, version
                    break
        local = data.get("localUpdate") or {}
        conditions = data.get("conditions") or {}
        progress = local.get("progress")
        status = local.get("status")
        return cls(
            installed=installed,
            latest=latest,
            available=channel is not None,
            conditions_met=(
                conditions.get("allConditionsMet", data.get("allConditionsMet")) is True
                and conditions.get("storage", True) is True
            ),
            local_status=status,
            local_version=local.get("version"),
            local_type=local.get("type"),
            progress=progress if type(progress) is int and 0 <= progress <= 100 else None,
            active=status == "Downloading" or any(
                action.get("name") in UPDATE_ACTIONS
                and action.get("status") in ACTIVE_ACTIONS for action in actions
            ),
            channel=channel,
        )

    def ready(self, target: str, channel: str = "stable") -> bool:
        """Verify the exact advertised version and completed local download."""
        # HC3 5.220.19 reports type=stable for a beta downloaded by version.
        # Only accept this observed mismatch for the explicitly selected beta.
        matching_type = self.local_type == channel or (
            channel == "beta" and self.local_type == "stable"
        )
        return (
            channel in {"stable", "beta"}
            and self.available
            and self.channel == channel
            and self.latest == target
            and self.local_status == "ReadyToInstall"
            and self.local_version == target
            and matching_type
        )


class FirmwareWorkflow:
    """Control firmware actions without retrying mutating requests."""

    def __init__(self, request: Callable[..., Awaitable[Any]], allow_beta: bool = True, *, channel: str | None = None, guard: FirmwareUpdateGuard | None = None) -> None:
        self.request = request
        self.allow_beta = allow_beta
        self.channel = channel
        self.guard = guard if guard is not None else FirmwareUpdateGuard()

    async def read(self, *, require_actions: bool = True) -> FirmwareState:
        """Read update information; action access is mandatory only for installation."""
        info = await self.request("GET", "settings/info")
        if not isinstance(info, dict):
            raise FirmwareError("GET settings/info: expected an object")
        try:
            data = await self.request("GET", "update")
        except FirmwarePermissionError as err:
            if require_actions:
                raise
            # Node-RED reads availability from settings/info without credentials.
            # Never use this reduced view to authorize an installation.
            try:
                state = FirmwareState.from_api(info, info, [], self.allow_beta, selected_channel=self.channel)
                if self.allow_beta and self.channel != "stable" and not isinstance(info.get("updateBetaAvailable"), bool):
                    raise FirmwareError("Missing beta flag in settings/info")
            except (FirmwareError, TypeError, AttributeError):
                public_info = await self.request("GET", "settings/info", anonymous=True)
                if not isinstance(public_info, dict):
                    raise FirmwareError("GET settings/info: expected an object") from err
                state = FirmwareState.from_api(public_info, public_info, [], self.allow_beta, selected_channel=self.channel)
                if self.allow_beta and self.channel != "stable" and not isinstance(public_info.get("updateBetaAvailable"), bool):
                    raise FirmwareError("Missing beta flag in settings/info") from err
            return replace(state, conditions_met=False, progress=None, active=False,
                           local_status=None, local_version=None, local_type=None,
                           action_error=str(err), status_source="settings/info")
        if not isinstance(data, dict):
            raise FirmwareError("GET update: expected an object")
        try:
            state = FirmwareState.from_api(info, data, [], self.allow_beta, selected_channel=self.channel)
        except (FirmwareError, TypeError, AttributeError) as err:
            raise FirmwareError(f"GET update/settings/info: {err}") from err
        try:
            actions = await self.request("GET", "service/actions")
            if not isinstance(actions, list) or any(not isinstance(a, dict) for a in actions):
                raise FirmwareError("GET service/actions: expected a list of action objects")
        except FirmwareError as err:
            if require_actions:
                raise
            return replace(state, action_error=str(err))
        return FirmwareState.from_api(info, data, actions, self.allow_beta, selected_channel=self.channel)

    async def start(self, action: str, params: dict) -> str:
        """Start an action and retain the returned action ID."""
        result = await self.request("POST", "service/update", json={"action": action, "params": params})
        action_id = result.get("actionId") if isinstance(result, dict) else None
        if not isinstance(action_id, str) or not action_id:
            raise FirmwareError("No action ID returned; check the hub before retrying")
        return action_id

    async def action_status(self, action_id: str) -> str | None:
        """Get the status of an action; it may disappear after reboot."""
        response = await self.request("GET", f"service/actions/{quote(action_id, safe='')}")
        if response is None:
            return None
        action = response.get("action") or {}
        return action.get("status")

    async def install(self, target: str, publish: Callable[[FirmwareState | None, str], None], channel: str = "stable") -> None:
        """Serialize installations across the two firmware entities."""
        if self.channel is not None and self.channel != channel:
            raise FirmwareError("Requested firmware channel does not match this entity")
        self.guard.claim(channel)
        try:
            await self._install(target, publish, channel)
        finally:
            self.guard.release()

    async def _install(self, target: str, publish: Callable[[FirmwareState | None, str], None], channel: str) -> None:
        """Download matching firmware and install with a local backup."""
        if channel == "beta" and not self.allow_beta:
            raise FirmwareError("Beta firmware is disabled")
        state = await self.read()
        self._validate(state, target, channel)
        if state.active:
            raise FirmwareError("A firmware action is already active on the hub")
        if not state.ready(target, channel):
            publish(state, "download")
            # The version is pinned to prevent downloading a newer release mid-run.
            action_id = await self.start("download", {"version": target})
            deadline = monotonic() + TIMEOUT
            while monotonic() < deadline:
                await asyncio.sleep(POLL_SECONDS)
                state = await self.read()
                publish(state, "download")
                status = await self.action_status(action_id)
                if status == "failed":
                    raise FirmwareError("Firmware download action failed")
                if state.local_version == target and state.local_status in DOWNLOAD_ERRORS:
                    raise FirmwareError(f"Firmware download failed: {state.local_status}")
                if status == "done" and state.local_status == "ReadyToInstall" and not state.active:
                    self._validate(state, target, channel)
                    if not state.ready(target, channel):
                        raise FirmwareError("Downloaded firmware does not match the requested version or channel")
                    break
            else:
                raise FirmwareError("Firmware download did not reach ReadyToInstall")
        # Refresh just before the destructive action, and never install another version.
        state = await self.read()
        self._validate(state, target, channel)
        if state.active or not state.ready(target, channel):
            raise FirmwareError("Matching firmware is not ready to install")
        publish(state, "install")
        # No documented value for skipping a backup. Always request a local backup.
        # A failed POST may have been accepted: do not send it again.
        try:
            action_id = await self.start("install", {"backupType": "local", "masterOnly": True})
        except FirmwareConnectionError:
            action_id = None
        deadline = monotonic() + TIMEOUT
        while monotonic() < deadline:
            await asyncio.sleep(POLL_SECONDS)
            try:
                state = await self.read()
                publish(state, "install")
                if state.installed == target:
                    return
                if action_id and await self.action_status(action_id) == "failed":
                    raise FirmwareError("Firmware installation action failed")
            except FirmwareConnectionError:
                publish(None, "install")
        raise FirmwareError("Could not verify installed firmware; check the Home Center")

    @staticmethod
    def _validate(state: FirmwareState, target: str, channel: str) -> None:
        if channel not in {"stable", "beta"} or not state.available or state.latest != target or state.channel != channel:
            raise FirmwareError("The requested firmware is no longer available")
        if not state.conditions_met:
            raise FirmwareError("The Home Center update conditions are not met")
