"""Analytics helper class for the analytics integration."""

from __future__ import annotations

import asyncio
from asyncio import timeout
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict as dataclass_asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol
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

type AnalyticsModifier = Callable[
    [HomeAssistant, AnalyticsInput], Awaitable[AnalyticsModifications]
]


@singleton(DATA_ANALYTICS_MODIFIERS)
def _async_get_modifiers(
    hass: HomeAssistant,
) -> dict[str, AnalyticsModifier | None]:
    """Return the analytics modifiers."""
    return {}


@dataclass
class AnalyticsInput:
    """Analytics input for a single integration.

    This is sent to integrations that implement the platform.
    """

    device_ids: Iterable[str] = field(default_factory=list)
    entity_ids: Iterable[str] = field(default_factory=list)


@dataclass
class AnalyticsModifications:
    """Analytics config for a single integration.

    This is used by integrations that implement the platform.
    """

    remove: bool = False
    devices: Mapping[str, DeviceAnalyticsModifications] | None = None
    entities: Mapping[str, EntityAnalyticsModifications] | None = None


@dataclass
class DeviceAnalyticsModifications:
    """Analytics config for a single device.

    This is used by integrations that implement the platform.
    """

    remove: bool = False


@dataclass
class EntityAnalyticsModifications:
    """Analytics config for a single entity.

    This is used by integrations that implement the platform.
    """

    remove: bool = False


class AnalyticsPlatformProtocol(Protocol):
    """Define the format of analytics platforms."""

    async def async_modify_analytics(
        self,
        hass: HomeAssistant,
        analytics_input: AnalyticsInput,
    ) -> AnalyticsModifications:
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


DEFAULT_ANALYTICS_CONFIG = AnalyticsModifications()
DEFAULT_DEVICE_ANALYTICS_CONFIG = DeviceAnalyticsModifications()
REMOVE_DEVICE_ANALYTICS_CONFIG = DeviceAnalyticsModifications(remove=True)
DEFAULT_ENTITY_ANALYTICS_CONFIG = EntityAnalyticsModifications()


async def async_devices_payload(hass: HomeAssistant) -> dict:  # noqa: C901
    """Return detailed information about entities and devices."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    integration_inputs: dict[str, tuple[list[str], list[str]]] = {}
    integration_configs: dict[str, AnalyticsModifications] = {}

    # Get device list
    for device_entry in dev_reg.devices.values():
        if not device_entry.primary_config_entry:
            continue

        config_entry = hass.config_entries.async_get_entry(
            device_entry.primary_config_entry
        )

        if config_entry is None:
            continue

        integration_domain = config_entry.domain

        integration_input = integration_inputs.setdefault(integration_domain, ([], []))
        integration_input[0].append(device_entry.id)

    # Get entity list
    for entity_entry in ent_reg.entities.values():
        integration_domain = entity_entry.platform

        integration_input = integration_inputs.setdefault(integration_domain, ([], []))
        integration_input[1].append(entity_entry.entity_id)

    integrations = {
        domain: integration
        for domain, integration in (
            await async_get_integrations(hass, integration_inputs.keys())
        ).items()
        if isinstance(integration, Integration)
    }

    # Filter out custom integrations and integrations that are not device or hub type
    integration_inputs = {
        domain: integration_info
        for domain, integration_info in integration_inputs.items()
        if (integration := integrations.get(domain)) is not None
        and integration.is_built_in
        and integration.manifest.get("integration_type") in ("device", "hub")
    }

    # Call integrations that implement the analytics platform
    for integration_domain, integration_input in integration_inputs.items():
        if (
            modifier := await _async_get_modifier(hass, integration_domain)
        ) is not None:
            try:
                integration_config = await modifier(
                    hass, AnalyticsInput(*integration_input)
                )
            except Exception as err:  # noqa: BLE001
                LOGGER.exception(
                    "Calling async_modify_analytics for integration '%s' failed: %s",
                    integration_domain,
                    err,
                )
                integration_configs[integration_domain] = AnalyticsModifications(
                    remove=True
                )
                continue

            if not isinstance(integration_config, AnalyticsModifications):
                LOGGER.error(  # type: ignore[unreachable]
                    "Calling async_modify_analytics for integration '%s' did not return an AnalyticsConfig",
                    integration_domain,
                )
                integration_configs[integration_domain] = AnalyticsModifications(
                    remove=True
                )
                continue

            integration_configs[integration_domain] = integration_config

    integrations_info: dict[str, dict[str, Any]] = {}

    # We need to refer to other devices, for example in `via_device` field.
    # We don't however send the original device ids outside of Home Assistant,
    # instead we refer to devices by (integration_domain, index_in_integration_device_list).
    device_id_mapping: dict[str, tuple[str, int] | None] = {}

    # Fill out information about devices
    for integration_domain, integration_input in integration_inputs.items():
        integration_config = integration_configs.get(
            integration_domain, DEFAULT_ANALYTICS_CONFIG
        )

        if integration_config.remove:
            continue

        integration_info = integrations_info.setdefault(
            integration_domain, {"devices": [], "entities": []}
        )

        devices_info = integration_info["devices"]

        for device_id in integration_input[0]:
            device_entry = dev_reg.devices[device_id]

            if device_entry.entry_type is dr.DeviceEntryType.SERVICE:
                device_config = REMOVE_DEVICE_ANALYTICS_CONFIG
            else:
                device_config = DEFAULT_DEVICE_ANALYTICS_CONFIG

            if integration_config.devices is not None:
                device_config = integration_config.devices.get(device_id, device_config)

            if device_config.remove:
                device_id_mapping[device_entry.id] = None
                continue

            device_id_mapping[device_entry.id] = (integration_domain, len(devices_info))

            devices_info.append(
                {
                    "entities": [],
                    "entry_type": device_entry.entry_type,
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

    # Fill out information about entities
    for integration_domain, integration_input in integration_inputs.items():
        integration_config = integration_configs.get(
            integration_domain, DEFAULT_ANALYTICS_CONFIG
        )

        if integration_config.remove:
            continue

        integration_info = integrations_info.setdefault(
            integration_domain, {"devices": [], "entities": []}
        )

        devices_info = integration_info["devices"]
        entities_info = integration_info["entities"]

        for entity_id in integration_input[1]:
            entity_config = DEFAULT_ENTITY_ANALYTICS_CONFIG
            if integration_config.entities is not None:
                entity_config = integration_config.entities.get(
                    entity_id, entity_config
                )

            if entity_config.remove:
                continue

            entity_entry = ent_reg.entities[entity_id]

            entity_state = hass.states.get(entity_entry.entity_id)

            entity_info = {
                # LIMITATION: `assumed_state` can be overridden by users;
                # we should replace it with the original value in the future.
                # It is also not present, if entity is not in the state machine,
                # which can happen for disabled entities.
                "assumed_state": (
                    entity_state.attributes.get(ATTR_ASSUMED_STATE, False)
                    if entity_state is not None
                    else None
                ),
                "domain": entity_entry.domain,
                "entity_category": entity_entry.entity_category,
                "has_entity_name": entity_entry.has_entity_name,
                "original_device_class": entity_entry.original_device_class,
                # LIMITATION: `unit_of_measurement` can be overridden by users;
                # we should replace it with the original value in the future.
                "unit_of_measurement": entity_entry.unit_of_measurement,
            }

            if ((device_id_ := entity_entry.device_id) is not None) and (
                (new_device_id := device_id_mapping.get(device_id_, UNDEFINED))
                is not UNDEFINED
            ):
                if new_device_id is None:
                    # The device was removed, so we remove the entity too
                    continue

                if new_device_id[0] == integration_domain:
                    device_info = devices_info[new_device_id[1]]
                    device_info["entities"].append(entity_info)
                    continue

            entities_info.append(entity_info)

    return {
        "version": "home-assistant:1",
        "home_assistant": HA_VERSION,
        "integrations": integrations_info,
    }
