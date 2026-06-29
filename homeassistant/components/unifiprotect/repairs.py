"""unifiprotect.repairs."""

import logging
from typing import cast

from uiprotect import ProtectApiClient
from uiprotect.exceptions import ClientError
import voluptuous as vol

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .data import UFPConfigEntry, async_get_data_for_entry_id
from .utils import async_create_api_client

_LOGGER = logging.getLogger(__name__)


class ProtectRepair(RepairsFlow):
    """Handler for an issue fixing flow."""

    _api: ProtectApiClient
    _entry: UFPConfigEntry

    def __init__(self, *, api: ProtectApiClient, entry: UFPConfigEntry) -> None:
        """Create flow."""

        self._api = api
        self._entry = entry
        super().__init__()

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        issue_registry = ir.async_get(self.hass)
        description_placeholders = {}
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders or {}
            if issue.learn_more_url:
                description_placeholders["learn_more"] = issue.learn_more_url

        return description_placeholders


class CloudAccountRepair(ProtectRepair):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        if user_input is None:
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        self._entry.async_start_reauth(self.hass)
        return self.async_create_entry(data={})


class RTSPRepair(ProtectRepair):
    """Fix flow for a camera without an active RTSPS stream.

    Verifies and creates the stream through the public API, so it also works in
    a public-only setup. The camera name is carried by the issue placeholders.
    """

    _camera_id: str

    def __init__(
        self, *, api: ProtectApiClient, entry: UFPConfigEntry, camera_id: str
    ) -> None:
        """Create flow."""

        super().__init__(api=api, entry=entry)
        self._camera_id = camera_id

    async def _async_has_active_stream(self) -> bool:
        streams = await self._api.get_camera_rtsps_streams(self._camera_id)
        return bool(streams and streams.get_active_stream_qualities())

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        if user_input is None:
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=self._async_get_placeholders(),
            )

        # Creating a stream needs write permission; a NotAuthorized/ClientError
        # routes to the confirm step (which explains the manual fallback)
        # instead of raising out of the fix flow.
        try:
            active = await self._async_has_active_stream()
            if not active:
                await self._api.create_camera_rtsps_streams(self._camera_id, "high")
                active = await self._async_has_active_stream()
        except ClientError:
            _LOGGER.debug(
                "Auto-creating RTSPS stream failed; routing to manual fallback",
                exc_info=True,
            )
            active = False

        if active:
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        placeholders = self._async_get_placeholders()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


@callback
def _async_get_or_create_api_client(
    hass: HomeAssistant, entry: UFPConfigEntry
) -> ProtectApiClient:
    """Get or create an API client."""
    if data := async_get_data_for_entry_id(hass, entry.entry_id):
        return data.api
    return async_create_api_client(hass, entry)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        data is not None
        and "entry_id" in data
        and (entry := hass.config_entries.async_get_entry(cast(str, data["entry_id"])))
    ):
        api = _async_get_or_create_api_client(hass, entry)
        if issue_id == "cloud_user":
            return CloudAccountRepair(api=api, entry=entry)
        if issue_id.startswith("rtsp_disabled_"):
            return RTSPRepair(
                api=api, entry=entry, camera_id=cast(str, data["camera_id"])
            )
    return ConfirmRepairFlow()
