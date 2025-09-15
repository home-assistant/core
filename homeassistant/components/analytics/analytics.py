"""Analytics helper class for the analytics integration."""

from __future__ import annotations

import asyncio
from asyncio import timeout
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict as dataclass_asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
import uuid

import aiohttp

from homeassistant import config as conf_util
from homeassistant.components import hassio
from homeassistant.components.api import ATTR_INSTALLATION_TYPE
from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.energy import (
    DOMAIN as ENERGY_DOMAIN,
    is_configured as energy_is_configured,
)
from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    get_instance as get_recorder_instance,
)
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DOMAIN,
    BASE_PLATFORMS,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integrations,
)
from homeassistant.setup import async_get_loaded_integrations

from .const import (
    ANALYTICS_ENDPOINT_URL,
    ANALYTICS_ENDPOINT_URL_DEV,
    ATTR_ADDON_COUNT,
    ATTR_ADDONS,
    ATTR_ARCH,
    ATTR_AUTO_UPDATE,
    ATTR_AUTOMATION_COUNT,
    ATTR_BASE,
    ATTR_BOARD,
    ATTR_CERTIFICATE,
    ATTR_CONFIGURED,
    ATTR_CUSTOM_INTEGRATIONS,
    ATTR_DIAGNOSTICS,
    ATTR_ENERGY,
    ATTR_ENGINE,
    ATTR_HEALTHY,
    ATTR_INTEGRATION_COUNT,
    ATTR_INTEGRATIONS,
    ATTR_OPERATING_SYSTEM,
    ATTR_PROTECTED,
    ATTR_RECORDER,
    ATTR_SLUG,
    ATTR_STATE_COUNT,
    ATTR_STATISTICS,
    ATTR_SUPERVISOR,
    ATTR_SUPPORTED,
    ATTR_USAGE,
    ATTR_USER_COUNT,
    ATTR_UUID,
    ATTR_VERSION,
    DOMAIN,
    LOGGER,
    PREFERENCE_SCHEMA,
    STORAGE_KEY,
    STORAGE_VERSION,
)

DATA_ANALYTICS_MODIFIERS = "analytics_modifiers"

type AnalyticsModifier = Callable[[HomeAssistant, AnalyticsConfig], Awaitable[None]]


@singleton(DATA_ANALYTICS_MODIFIERS)
def _async_get_modifiers(
    hass: HomeAssistant,
) -> dict[str, AnalyticsModifier | None]:
    """Return the analytics modifiers."""
    return {}


@dataclass
class AnalyticsConfig:
    """Analytics config for a single integration.

    This is modified by integrations that implement the platform.
    """

    devices: Mapping[str, DeviceAnalyticsConfig]
    entities: Mapping[str, EntityAnalyticsConfig]
    devices_to_remove: Iterable[str] | None = None
    entities_to_remove: Iterable[str] | None = None


@dataclass
class DeviceAnalyticsConfig:
    """Analytics config for a single device.

    This is modified by integrations that implement the platform.
    """

    extra: dict[str, Any] | None = None


@dataclass
class EntityAnalyticsConfig:
    """Analytics config for a single entity.

    This is modified by integrations that implement the platform.
    """

    capabilities: dict[str, Any] | None
    extra: dict[str, Any] | None = None


class AnalyticsPlatformProtocol(Protocol):
    """Define the format of analytics platforms."""

    async def async_modify_analytics(
        self,
        hass: HomeAssistant,
        config: AnalyticsConfig,
    ) -> None:
        """Modify the analytics."""


async def _async_get_analytics_platform(
    hass: HomeAssistant, domain: str
) -> AnalyticsPlatformProtocol | None:
    """Get analytics platform."""
    try:
        integration = await async_get_integration(hass, domain)
    except IntegrationNotFound:
        return None
    try:
        return await integration.async_get_platform(DOMAIN)
    except ImportError:
        return None


async def _async_get_modifier(
    hass: HomeAssistant, domain: str
) -> AnalyticsModifier | None:
    """Get analytics modifier."""
    modifiers = _async_get_modifiers(hass)
    modifier = modifiers.get(domain, UNDEFINED)

    if modifier is not UNDEFINED:
        return modifier

    platform = await _async_get_analytics_platform(hass, domain)
    if platform is None:
        modifiers[domain] = None
        return None

    modifier = getattr(platform, "async_modify_analytics", None)
    modifiers[domain] = modifier
    return modifier


def gen_uuid() -> str:
    """Generate a new UUID."""
    return uuid.uuid4().hex


@dataclass
class AnalyticsData:
    """Analytics data."""

    onboarded: bool
    preferences: dict[str, bool]
    uuid: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalyticsData:
        """Initialize analytics data from a dict."""
        return cls(
            data["onboarded"],
            data["preferences"],
            data["uuid"],
        )


class Analytics:
    """Analytics helper class for the analytics integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Analytics class."""
        self.hass: HomeAssistant = hass
        self.session = async_get_clientsession(hass)
        self._data = AnalyticsData(False, {}, None)
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)

    @property
    def preferences(self) -> dict:
        """Return the current active preferences."""
        preferences = self._data.preferences
        return {
            ATTR_BASE: preferences.get(ATTR_BASE, False),
            ATTR_DIAGNOSTICS: preferences.get(ATTR_DIAGNOSTICS, False),
            ATTR_USAGE: preferences.get(ATTR_USAGE, False),
            ATTR_STATISTICS: preferences.get(ATTR_STATISTICS, False),
        }

    @property
    def onboarded(self) -> bool:
        """Return bool if the user has made a choice."""
        return self._data.onboarded

    @property
    def uuid(self) -> str | None:
        """Return the uuid for the analytics integration."""
        return self._data.uuid

    @property
    def endpoint(self) -> str:
        """Return the endpoint that will receive the payload."""
        if HA_VERSION.endswith("0.dev0"):
            # dev installations will contact the dev analytics environment
            return ANALYTICS_ENDPOINT_URL_DEV
        return ANALYTICS_ENDPOINT_URL

    @property
    def supervisor(self) -> bool:
        """Return bool if a supervisor is present."""
        return is_hassio(self.hass)

    async def load(self) -> None:
        """Load preferences."""
        stored = await self._store.async_load()
        if stored:
            self._data = AnalyticsData.from_dict(stored)

        if (
            self.supervisor
            and (supervisor_info := hassio.get_supervisor_info(self.hass)) is not None
        ):
            if not self.onboarded:
                # User have not configured analytics, get this setting from the supervisor
                if supervisor_info[ATTR_DIAGNOSTICS] and not self.preferences.get(
                    ATTR_DIAGNOSTICS, False
                ):
                    self._data.preferences[ATTR_DIAGNOSTICS] = True
                elif not supervisor_info[ATTR_DIAGNOSTICS] and self.preferences.get(
                    ATTR_DIAGNOSTICS, False
                ):
                    self._data.preferences[ATTR_DIAGNOSTICS] = False

    async def save_preferences(self, preferences: dict) -> None:
        """Save preferences."""
        preferences = PREFERENCE_SCHEMA(preferences)
        self._data.preferences.update(preferences)
        self._data.onboarded = True

        await self._store.async_save(dataclass_asdict(self._data))

        if self.supervisor:
            await hassio.async_update_diagnostics(
                self.hass, self.preferences.get(ATTR_DIAGNOSTICS, False)
            )

    async def send_analytics(self, _: datetime | None = None) -> None:
        """Send analytics."""
        hass = self.hass
        supervisor_info = None
        operating_system_info: dict[str, Any] = {}

        if not self.onboarded or not self.preferences.get(ATTR_BASE, False):
            LOGGER.debug("Nothing to submit")
            return

        if self._data.uuid is None:
            self._data.uuid = gen_uuid()
            await self._store.async_save(dataclass_asdict(self._data))

        if self.supervisor:
            supervisor_info = hassio.get_supervisor_info(hass)
            operating_system_info = hassio.get_os_info(hass) or {}

        system_info = await async_get_system_info(hass)
        integrations = []
        custom_integrations = []
        addons: list[dict[str, Any]] = []
        payload: dict = {
            ATTR_UUID: self.uuid,
            ATTR_VERSION: HA_VERSION,
            ATTR_INSTALLATION_TYPE: system_info[ATTR_INSTALLATION_TYPE],
        }

        if supervisor_info is not None:
            payload[ATTR_SUPERVISOR] = {
                ATTR_HEALTHY: supervisor_info[ATTR_HEALTHY],
                ATTR_SUPPORTED: supervisor_info[ATTR_SUPPORTED],
                ATTR_ARCH: supervisor_info[ATTR_ARCH],
            }

        if operating_system_info.get(ATTR_BOARD) is not None:
            payload[ATTR_OPERATING_SYSTEM] = {
                ATTR_BOARD: operating_system_info[ATTR_BOARD],
                ATTR_VERSION: operating_system_info[ATTR_VERSION],
            }

        if self.preferences.get(ATTR_USAGE, False) or self.preferences.get(
            ATTR_STATISTICS, False
        ):
            ent_reg = er.async_get(hass)

            try:
                yaml_configuration = await conf_util.async_hass_config_yaml(hass)
            except HomeAssistantError as err:
                LOGGER.error(err)
                return

            configuration_set = _domains_from_yaml_config(yaml_configuration)

            er_platforms = {
                entity.platform
                for entity in ent_reg.entities.values()
                if not entity.disabled
            }

            domains = async_get_loaded_integrations(hass)
            configured_integrations = await async_get_integrations(hass, domains)
            enabled_domains = set(configured_integrations)

            for integration in configured_integrations.values():
                if isinstance(integration, IntegrationNotFound):
                    continue

                if isinstance(integration, BaseException):
                    raise integration

                if not self._async_should_report_integration(
                    integration=integration,
                    yaml_domains=configuration_set,
                    entity_registry_platforms=er_platforms,
                ):
                    continue

                if not integration.is_built_in:
                    custom_integrations.append(
                        {
                            ATTR_DOMAIN: integration.domain,
                            ATTR_VERSION: integration.version,
                        }
                    )
                    continue

                integrations.append(integration.domain)

            if supervisor_info is not None:
                supervisor_client = hassio.get_supervisor_client(hass)
                installed_addons = await asyncio.gather(
                    *(
                        supervisor_client.addons.addon_info(addon[ATTR_SLUG])
                        for addon in supervisor_info[ATTR_ADDONS]
                    )
                )
                addons.extend(
                    {
                        ATTR_SLUG: addon.slug,
                        ATTR_PROTECTED: addon.protected,
                        ATTR_VERSION: addon.version,
                        ATTR_AUTO_UPDATE: addon.auto_update,
                    }
                    for addon in installed_addons
                )

        if self.preferences.get(ATTR_USAGE, False):
            payload[ATTR_CERTIFICATE] = hass.http.ssl_certificate is not None
            payload[ATTR_INTEGRATIONS] = integrations
            payload[ATTR_CUSTOM_INTEGRATIONS] = custom_integrations
            if supervisor_info is not None:
                payload[ATTR_ADDONS] = addons

            if ENERGY_DOMAIN in enabled_domains:
                payload[ATTR_ENERGY] = {
                    ATTR_CONFIGURED: await energy_is_configured(hass)
                }

            if RECORDER_DOMAIN in enabled_domains:
                instance = get_recorder_instance(hass)
                engine = instance.database_engine
                if engine and engine.version is not None:
                    payload[ATTR_RECORDER] = {
                        ATTR_ENGINE: engine.dialect.value,
                        ATTR_VERSION: engine.version,
                    }

        if self.preferences.get(ATTR_STATISTICS, False):
            payload[ATTR_STATE_COUNT] = hass.states.async_entity_ids_count()
            payload[ATTR_AUTOMATION_COUNT] = hass.states.async_entity_ids_count(
                AUTOMATION_DOMAIN
            )
            payload[ATTR_INTEGRATION_COUNT] = len(integrations)
            if supervisor_info is not None:
                payload[ATTR_ADDON_COUNT] = len(addons)
            payload[ATTR_USER_COUNT] = len(
                [
                    user
                    for user in await hass.auth.async_get_users()
                    if not user.system_generated
                ]
            )

        try:
            async with timeout(30):
                response = await self.session.post(self.endpoint, json=payload)
                if response.status == 200:
                    LOGGER.info(
                        (
                            "Submitted analytics to Home Assistant servers. "
                            "Information submitted includes %s"
                        ),
                        payload,
                    )
                else:
                    LOGGER.warning(
                        "Sending analytics failed with statuscode %s from %s",
                        response.status,
                        self.endpoint,
                    )
        except TimeoutError:
            LOGGER.error("Timeout sending analytics to %s", ANALYTICS_ENDPOINT_URL)
        except aiohttp.ClientError as err:
            LOGGER.error(
                "Error sending analytics to %s: %r", ANALYTICS_ENDPOINT_URL, err
            )

    @callback
    def _async_should_report_integration(
        self,
        integration: Integration,
        yaml_domains: set[str],
        entity_registry_platforms: set[str],
    ) -> bool:
        """Return a bool to indicate if this integration should be reported."""
        if integration.disabled:
            return False

        # Check if the integration is defined in YAML or in the entity registry
        if (
            integration.domain in yaml_domains
            or integration.domain in entity_registry_platforms
        ):
            return True

        # Check if the integration provide a config flow
        if not integration.config_flow:
            return False

        entries = self.hass.config_entries.async_entries(integration.domain)

        # Filter out ignored and disabled entries
        return any(
            entry
            for entry in entries
            if entry.source != SOURCE_IGNORE and entry.disabled_by is None
        )


def _domains_from_yaml_config(yaml_configuration: dict[str, Any]) -> set[str]:
    """Extract domains from the YAML configuration."""
    domains = set(yaml_configuration)
    for platforms in conf_util.extract_platform_integrations(
        yaml_configuration, BASE_PLATFORMS
    ).values():
        domains.update(platforms)
    return domains


async def async_devices_payload(hass: HomeAssistant) -> dict:  # noqa: C901
    """Return detailed information about entities and devices."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    modifiable_infos: dict[
        str,  # integration domain
        tuple[
            list[str],  # list of device ids
            dict[str, DeviceAnalyticsConfig],
            list[str],  # list of entity ids
            dict[str, EntityAnalyticsConfig],
        ]
        | None,
    ] = {}

    # Get modifiable device infos
    for device_entry in dev_reg.devices.values():
        if not device_entry.primary_config_entry:
            continue

        config_entry = hass.config_entries.async_get_entry(
            device_entry.primary_config_entry
        )

        if config_entry is None:
            continue

        integration_domain = config_entry.domain

        modifiable_info = modifiable_infos.setdefault(
            integration_domain, ([], {}, [], {})
        )
        if TYPE_CHECKING:
            assert modifiable_info is not None

        modifiable_info[0].append(device_entry.id)
        modifiable_info[1][device_entry.id] = DeviceAnalyticsConfig()

    # Get modifiable entity infos
    for entity_entry in ent_reg.entities.values():
        integration_domain = entity_entry.platform

        modifiable_info = modifiable_infos.setdefault(
            integration_domain, ([], {}, [], {})
        )
        if TYPE_CHECKING:
            assert modifiable_info is not None

        modifiable_info[2].append(entity_entry.entity_id)
        modifiable_info[3][entity_entry.entity_id] = EntityAnalyticsConfig(
            capabilities=dict(entity_entry.capabilities)
            if entity_entry.capabilities is not None
            else None,
        )

    # Pass modifiable infos to integrations
    for integration_domain, modifiable_info in modifiable_infos.items():
        if TYPE_CHECKING:
            assert modifiable_info is not None
        if (
            modifier := await _async_get_modifier(hass, integration_domain)
        ) is not None:
            config = AnalyticsConfig(
                devices=modifiable_info[1],
                entities=modifiable_info[3],
            )
            try:
                await modifier(hass, config)
            except Exception as err:  # noqa: BLE001
                LOGGER.exception(
                    "Calling async_modify_analytics for integration '%s' failed: %s",
                    integration_domain,
                    err,
                )
                modifiable_infos[integration_domain] = None
            else:
                if config.devices_to_remove is not None:
                    modifiable_info[0][:] = [
                        device_id
                        for device_id in modifiable_info[0]
                        if device_id not in config.devices_to_remove
                    ]
                if config.entities_to_remove is not None:
                    modifiable_info[2][:] = [
                        entity_id
                        for entity_id in modifiable_info[2]
                        if entity_id not in config.entities_to_remove
                    ]

    integrations_info: dict[str, dict[str, Any]] = {}

    # We need to refer to other devices, for example in `via_device` field.
    # We don't however send the original device ids outside of Home Assistant,
    # instead we refer to devices by (integration_domain, index_in_integration_device_list).
    device_id_mapping: dict[str, tuple[str, int]] = {}

    # Fill out remaining information about devices
    for integration_domain, modifiable_info in modifiable_infos.items():
        if modifiable_info is None:
            continue

        integration_info = integrations_info.setdefault(
            integration_domain, {"devices": [], "entities": []}
        )

        devices_info = integration_info["devices"]

        for device_id in modifiable_info[0]:
            modifiable_device_info = modifiable_info[1][device_id]

            device_entry = dev_reg.devices[device_id]

            device_id_mapping[device_entry.id] = (integration_domain, len(devices_info))

            devices_info.append(
                {
                    "entities": [],
                    "entry_type": device_entry.entry_type,
                    "extra": modifiable_device_info.extra,
                    "has_configuration_url": device_entry.configuration_url is not None,
                    "hw_version": device_entry.hw_version,
                    "manufacturer": device_entry.manufacturer,
                    "model": device_entry.model,
                    "model_id": device_entry.model_id,
                    "sw_version": device_entry.sw_version,
                    "via_device": device_entry.via_device_id,
                }
            )

    # Fill out via_device with new device ids
    for integration_info in integrations_info.values():
        for device_info in integration_info["devices"]:
            if device_info["via_device"] is None:
                continue
            device_info["via_device"] = device_id_mapping.get(device_info["via_device"])

    # Fill out remaining information about entities
    for integration_domain, modifiable_info in modifiable_infos.items():
        if modifiable_info is None:
            continue

        integration_info = integrations_info.setdefault(
            integration_domain, {"devices": [], "entities": []}
        )

        devices_info = integration_info["devices"]
        entities_info = integration_info["entities"]

        for entity_id in modifiable_info[2]:
            modifiable_entity_info = modifiable_info[3][entity_id]

            entity_entry = ent_reg.entities[entity_id]

            entity_state = hass.states.get(entity_entry.entity_id)

            entity_info = {
                # LIMITATION: `assumed_state` can be overridden by users;
                # we should replace it with the original value in the future.
                # It is also not present, if entity is not in the state machine,
                # which can happen for disabled entities.
                "assumed_state": entity_state.attributes.get(ATTR_ASSUMED_STATE, False)
                if entity_state is not None
                else None,
                "capabilities": modifiable_entity_info.capabilities,
                "domain": entity_entry.domain,
                "entity_category": entity_entry.entity_category,
                "extra": modifiable_entity_info.extra,
                "has_entity_name": entity_entry.has_entity_name,
                "original_device_class": entity_entry.original_device_class,
                # LIMITATION: `unit_of_measurement` can be overridden by users;
                # we should replace it with the original value in the future.
                "unit_of_measurement": entity_entry.unit_of_measurement,
            }

            if (
                ((device_id_ := entity_entry.device_id) is not None)
                and ((new_device_id := device_id_mapping.get(device_id_)) is not None)
                and (new_device_id[0] == integration_domain)
            ):
                device_info = devices_info[new_device_id[1]]
                device_info["entities"].append(entity_info)
            else:
                entities_info.append(entity_info)

    integrations = {
        domain: integration
        for domain, integration in (
            await async_get_integrations(hass, integrations_info.keys())
        ).items()
        if isinstance(integration, Integration)
    }

    for domain, integration_info in integrations_info.items():
        if integration := integrations.get(domain):
            integration_info["is_custom_integration"] = not integration.is_built_in
            # Include version for custom integrations
            if not integration.is_built_in and integration.version:
                integration_info["custom_integration_version"] = str(
                    integration.version
                )

    return {
        "version": "home-assistant:1",
        "home_assistant": HA_VERSION,
        "integrations": integrations_info,
    }
