"""Sandbox client that runs HA integrations out-of-process.

Connects to a real Home Assistant instance using a sandbox token,
fetches assigned config entries, sets up the integrations locally,
and pushes entity state back to HA Core.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Any

from .api import HomeAssistantAPI
from .config import RemoteConfig
from .sandbox_entity_bridge import SandboxEntityBridge

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
_LOGGER = logging.getLogger(__name__)


class SandboxClient:
    """Sandbox process that loads HA integrations and bridges to HA Core."""

    def __init__(self, ws_url: str, token: str) -> None:
        """Initialize the sandbox client."""
        self._ws_url = ws_url
        self._token = token
        self._api: HomeAssistantAPI | None = None
        self._entries: list[dict[str, Any]] = []
        self._hass: Any = None
        self._entity_map: dict[str, str] = {}
        self._bridges: list[SandboxEntityBridge] = []
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Connect to HA Core and set up sandbox integrations."""
        self._api = HomeAssistantAPI(
            websocket_url=self._ws_url,
            token=self._token,
        )
        await self._api.start(ssl=False)
        _LOGGER.info("Connected to HA Core at %s", self._ws_url)

        self._entries = await self._api.async_sandbox_get_entries()
        _LOGGER.info(
            "Received %d config entries: %s",
            len(self._entries),
            [e["domain"] for e in self._entries],
        )

        await self._setup_hass()
        await self._setup_integrations()

        _LOGGER.info("Sandbox is running. Waiting for stop signal.")
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Shut down the sandbox."""
        _LOGGER.info("Stopping sandbox")
        self._stop_event.set()
        if self._api is not None:
            await self._api.stop()

    async def _setup_hass(self) -> None:
        """Create a minimal local HomeAssistant instance for integrations."""
        from .runtime import RemoteHomeAssistant

        config = RemoteConfig(
            websocket_url=self._ws_url,
            token=self._token,
            ssl=False,
            sync_states=False,
            sync_entity_registry=False,
            sync_remote_services=True,
        )

        self._hass = RemoteHomeAssistant(
            config_dir=os.path.join(os.getcwd(), ".sandbox_config"),
            remote_config=config,
        )
        self._hass.remote_api = self._api

        os.makedirs(self._hass.config.config_dir, exist_ok=True)

        await self._hass.async_setup_remote()

    async def _setup_integrations(self) -> None:
        """Set up each assigned integration inside the sandbox."""
        for entry_config in self._entries:
            domain = entry_config["domain"]
            _LOGGER.info("Setting up integration: %s", domain)

            try:
                await self._setup_single_integration(entry_config)
            except Exception:
                _LOGGER.exception("Failed to set up %s", domain)

    async def _setup_single_integration(
        self, entry_config: dict[str, Any]
    ) -> None:
        """Set up a single integration and bridge its entities."""
        domain = entry_config["domain"]
        entry_id = entry_config["entry_id"]
        data = entry_config.get("data", {})

        if domain in ("input_boolean", "input_number", "input_text", "input_select", "input_datetime"):
            await self._setup_input_helper(domain, entry_id, data)
        else:
            await self._setup_config_entry_integration(entry_config)

    async def _setup_input_helper(
        self,
        domain: str,
        entry_id: str,
        data: dict[str, Any],
    ) -> None:
        """Set up an input helper integration in the sandbox."""
        hass = self._hass
        api = self._api
        assert api is not None

        items = data.get("items", [])
        if not items:
            _LOGGER.warning("No items configured for %s", domain)
            return

        integration = await self._load_integration(domain)
        if integration is None:
            return

        config = {domain: {}}
        for item in items:
            item_id = item.get("id", item.get("name", "").lower().replace(" ", "_"))
            config[domain][item_id] = {
                k: v for k, v in item.items() if k != "id"
            }

        module = integration.get_component()
        if hasattr(module, "async_setup"):
            await module.async_setup(hass, config)

        await hass.async_block_till_done()

        for entity_id, state in hass.states._states.items():
            if entity_id.startswith(f"{domain}."):
                result = await api.async_sandbox_register_entity(
                    sandbox_entry_id=entry_id,
                    domain=domain,
                    platform=domain,
                    unique_id=entity_id.split(".", 1)[1],
                    original_name=state.attributes.get("friendly_name"),
                    suggested_object_id=entity_id.split(".", 1)[1],
                )
                ha_entity_id = result["entity_id"]
                self._entity_map[entity_id] = ha_entity_id
                _LOGGER.info(
                    "Registered entity: %s -> %s", entity_id, ha_entity_id
                )

                await api.async_sandbox_update_state(
                    ha_entity_id,
                    state.state,
                    dict(state.attributes),
                )
                _LOGGER.info(
                    "Pushed initial state for %s: %s", ha_entity_id, state.state
                )

        self._subscribe_state_changes(domain)

        ha_entity_ids = list(self._entity_map.values())
        if ha_entity_ids:
            await self._subscribe_service_calls(domain, ha_entity_ids)

    async def _subscribe_service_calls(
        self, domain: str, ha_entity_ids: list[str]
    ) -> None:
        """Subscribe to service calls from HA Core targeting our entities."""
        api = self._api
        assert api is not None

        reverse_map = {v: k for k, v in self._entity_map.items()}

        async def _on_service_call(message: dict[str, Any]) -> None:
            event_data = message.get("event", {})
            svc_domain = event_data.get("domain", "")
            service = event_data.get("service", "")
            service_data = event_data.get("service_data", {})
            target_entity_ids = event_data.get("entity_ids", [])

            for ha_eid in target_entity_ids:
                local_eid = reverse_map.get(ha_eid)
                if local_eid is None:
                    continue

                _LOGGER.info(
                    "Forwarding service call %s.%s to %s",
                    svc_domain,
                    service,
                    local_eid,
                )

                target = {"entity_id": [local_eid]}
                call_data = {
                    k: v
                    for k, v in service_data.items()
                    if k != "entity_id"
                }
                try:
                    await self._hass.services.async_call(
                        svc_domain,
                        service,
                        call_data,
                        blocking=True,
                        target=target,
                    )
                except Exception:
                    _LOGGER.exception(
                        "Error handling service %s.%s for %s",
                        svc_domain,
                        service,
                        local_eid,
                    )

        await api.subscribe(
            _on_service_call,
            "sandbox/subscribe_service_calls",
            entity_ids=ha_entity_ids,
        )
        _LOGGER.info(
            "Subscribed to service calls for %s", ha_entity_ids
        )

    async def _setup_config_entry_integration(
        self, entry_config: dict[str, Any]
    ) -> None:
        """Set up a config-entry-based integration in the sandbox."""
        from homeassistant.config_entries import ConfigEntry
        from homeassistant.helpers.entity_platform import EntityPlatform

        hass = self._hass
        api = self._api
        assert api is not None

        domain = entry_config["domain"]
        entry_id = entry_config["entry_id"]
        data = entry_config.get("data", {})
        options = entry_config.get("options", {})
        title = entry_config.get("title", domain)

        integration = await self._load_integration(domain)
        if integration is None:
            return

        from types import MappingProxyType
        from homeassistant.config_entries import ConfigEntryState

        entry = ConfigEntry(
            data=data,
            discovery_keys=MappingProxyType({}),
            domain=domain,
            entry_id=entry_id,
            minor_version=1,
            options=options,
            source="sandbox",
            subentries_data=None,
            title=title,
            unique_id=None,
            version=1,
        )
        entry._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
        hass.config_entries._entries[entry.entry_id] = entry

        module = integration.get_component()
        if hasattr(module, "async_setup"):
            await module.async_setup(hass, {domain: {}})

        if hasattr(module, "async_setup_entry"):
            await module.async_setup_entry(hass, entry)

        await hass.async_block_till_done()

        bridge = SandboxEntityBridge(hass, api, entry_id)
        self._bridges.append(bridge)

        from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES

        domain_platform_entities = hass.data.get(DATA_DOMAIN_PLATFORM_ENTITIES, {})
        for (plat_domain, plat_name), entities in domain_platform_entities.items():
            for eid, entity in list(entities.items()):
                if entity.platform and entity.platform.config_entry == entry:
                    await bridge._register_entity(eid, entity, entity.platform)

        bridge.start_state_forwarding()
        await bridge.subscribe_entity_commands()

        _LOGGER.info(
            "Config entry integration %s set up with %d entities",
            domain,
            len(bridge._local_entities),
        )

    async def _load_integration(self, domain: str) -> Any:
        """Load a HA integration by domain."""
        from homeassistant.loader import async_get_integration

        try:
            return await async_get_integration(self._hass, domain)
        except Exception:
            _LOGGER.exception("Failed to load integration %s", domain)
            return None

    def _subscribe_state_changes(self, domain: str) -> None:
        """Watch for local state changes and push them to HA Core."""
        from homeassistant.const import EVENT_STATE_CHANGED
        from homeassistant.core import EventOrigin

        async def _on_state_changed(event: Any) -> None:
            if event.origin == EventOrigin.remote:
                return

            entity_id = event.data.get("entity_id", "")
            if not entity_id.startswith(f"{domain}."):
                return

            ha_entity_id = self._entity_map.get(entity_id)
            if ha_entity_id is None:
                return

            new_state = event.data.get("new_state")
            if new_state is None:
                return

            api = self._api
            if api is None:
                return

            try:
                await api.async_sandbox_update_state(
                    ha_entity_id,
                    new_state.state,
                    dict(new_state.attributes),
                )
            except Exception:
                _LOGGER.exception("Failed to push state for %s", ha_entity_id)

        self._hass.bus.async_listen(EVENT_STATE_CHANGED, _on_state_changed)


async def async_main(args: argparse.Namespace) -> None:
    """Entry point for the sandbox process."""
    client = SandboxClient(args.url, args.token)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(client.stop()))

    try:
        await client.start()
    except KeyboardInterrupt:
        pass
    finally:
        await client.stop()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Home Assistant Sandbox Client")
    parser.add_argument(
        "--url",
        required=True,
        help="WebSocket URL of the HA Core instance",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Sandbox access token",
    )
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
