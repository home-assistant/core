"""Device discovery functions for Zigbee Home Automation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, cast

from slugify import slugify
from zigpy.quirks.v2 import (
    BinarySensorMetadata,
    CustomDeviceV2,
    EntityType,
    NumberMetadata,
    SwitchMetadata,
    WriteAttributeButtonMetadata,
    ZCLCommandButtonMetadata,
    ZCLEnumMetadata,
    ZCLSensorMetadata,
)
from zigpy.state import State
from zigpy.zcl import ClusterType
from zigpy.zcl.clusters.general import Ota

from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import ConfigType

from .. import (  # noqa: F401
    alarm_control_panel,
    binary_sensor,
    button,
    climate,
    cover,
    device_tracker,
    fan,
    light,
    lock,
    number,
    select,
    sensor,
    siren,
    switch,
    update,
)
from . import const as zha_const, registries as zha_regs

# importing cluster handlers updates registries
from .cluster_handlers import (  # noqa: F401
    ClusterHandler,
    closures,
    general,
    homeautomation,
    hvac,
    lighting,
    lightlink,
    manufacturerspecific,
    measurement,
    protocol,
    security,
    smartenergy,
)
from .helpers import get_zha_data, get_zha_gateway

if TYPE_CHECKING:
    from ..entity import ZhaEntity
    from .device import ZHADevice
    from .endpoint import Endpoint
    from .group import ZHAGroup

_LOGGER = logging.getLogger(__name__)


QUIRKS_ENTITY_META_TO_ENTITY_CLASS = {
    (
        Platform.BUTTON,
        WriteAttributeButtonMetadata,
        EntityType.CONFIG,
    ): button.ZHAAttributeButton,
    (
        Platform.BUTTON,
        WriteAttributeButtonMetadata,
        EntityType.STANDARD,
    ): button.ZHAAttributeButton,
    (Platform.BUTTON, ZCLCommandButtonMetadata, EntityType.CONFIG): button.ZHAButton,
    (
        Platform.BUTTON,
        ZCLCommandButtonMetadata,
        EntityType.DIAGNOSTIC,
    ): button.ZHAButton,
    (Platform.BUTTON, ZCLCommandButtonMetadata, EntityType.STANDARD): button.ZHAButton,
    (
        Platform.BINARY_SENSOR,
        BinarySensorMetadata,
        EntityType.CONFIG,
    ): binary_sensor.BinarySensor,
    (
        Platform.BINARY_SENSOR,
        BinarySensorMetadata,
        EntityType.DIAGNOSTIC,
    ): binary_sensor.BinarySensor,
    (
        Platform.BINARY_SENSOR,
        BinarySensorMetadata,
        EntityType.STANDARD,
    ): binary_sensor.BinarySensor,
    (Platform.SENSOR, ZCLEnumMetadata, EntityType.DIAGNOSTIC): sensor.EnumSensor,
    (Platform.SENSOR, ZCLEnumMetadata, EntityType.STANDARD): sensor.EnumSensor,
    (Platform.SENSOR, ZCLSensorMetadata, EntityType.DIAGNOSTIC): sensor.Sensor,
    (Platform.SENSOR, ZCLSensorMetadata, EntityType.STANDARD): sensor.Sensor,
    (Platform.SELECT, ZCLEnumMetadata, EntityType.CONFIG): select.ZCLEnumSelectEntity,
    (Platform.SELECT, ZCLEnumMetadata, EntityType.STANDARD): select.ZCLEnumSelectEntity,
    (
        Platform.SELECT,
        ZCLEnumMetadata,
        EntityType.DIAGNOSTIC,
    ): select.ZCLEnumSelectEntity,
    (
        Platform.NUMBER,
        NumberMetadata,
        EntityType.CONFIG,
    ): number.ZHANumberConfigurationEntity,
    (Platform.NUMBER, NumberMetadata, EntityType.DIAGNOSTIC): number.ZhaNumber,
    (Platform.NUMBER, NumberMetadata, EntityType.STANDARD): number.ZhaNumber,
    (
        Platform.SWITCH,
        SwitchMetadata,
        EntityType.CONFIG,
    ): switch.ZHASwitchConfigurationEntity,
    (Platform.SWITCH, SwitchMetadata, EntityType.STANDARD): switch.Switch,
}


@callback
async def async_add_entities(
    _async_add_entities: AddEntitiesCallback,
    entities: list[
        tuple[
            type[ZhaEntity],
            tuple[str, ZHADevice, list[ClusterHandler]],
            dict[str, Any],
        ]
    ],
    **kwargs,
) -> None:
    """Add entities helper."""
    if not entities:
        return

    to_add = [
        ent_cls.create_entity(*args, **{**kwargs, **kw_args})
        for ent_cls, args, kw_args in entities
    ]
    entities_to_add = [entity for entity in to_add if entity is not None]
    _async_add_entities(entities_to_add, update_before_add=False)
    entities.clear()


class ProbeEndpoint:
    """All discovered cluster handlers and entities of an endpoint."""

    def __init__(self) -> None:
        """Initialize instance."""
        self._device_configs: ConfigType = {}

    @callback
    def discover_entities(self, endpoint: Endpoint) -> None:
        """Process an endpoint on a zigpy device."""
        _LOGGER.debug(
            "Discovering entities for endpoint: %s-%s",
            str(endpoint.device.ieee),
            endpoint.id,
        )
        self.discover_by_device_type(endpoint)
        self.discover_multi_entities(endpoint)
        self.discover_by_cluster_id(endpoint)
        self.discover_multi_entities(endpoint, config_diagnostic_entities=True)
        zha_regs.ZHA_ENTITIES.clean_up()

    @callback
    def discover_device_entities(self, device: ZHADevice) -> None:
        """Discover entities for a ZHA device."""
        _LOGGER.debug(
            "Discovering entities for device: %s-%s",
            str(device.ieee),
            device.name,
        )

        if device.is_coordinator:
            self.discover_coordinator_device_entities(device)
            return

        self.discover_quirks_v2_entities(device)
        zha_regs.ZHA_ENTITIES.clean_up()

    @callback
    def discover_quirks_v2_entities(self, device: ZHADevice) -> None:
        """Discover entities for a ZHA device exposed by quirks v2."""
        _LOGGER.debug(
            "Attempting to discover quirks v2 entities for device: %s-%s",
            str(device.ieee),
            device.name,
        )

        if not isinstance(device.device, CustomDeviceV2):
            _LOGGER.debug(
                "Device: %s-%s is not a quirks v2 device - skipping "
                "discover_quirks_v2_entities",
                str(device.ieee),
                device.name,
            )
            return

        zigpy_device: CustomDeviceV2 = device.device

        if not zigpy_device.exposes_metadata:
            _LOGGER.debug(
                "Device: %s-%s does not expose any quirks v2 entities",
                str(device.ieee),
                device.name,
            )
            return

        for (
            cluster_details,
            entity_metadata_list,
        ) in zigpy_device.exposes_metadata.items():
            endpoint_id, cluster_id, cluster_type = cluster_details

            if endpoint_id not in device.endpoints:
                _LOGGER.warning(
                    "Device: %s-%s does not have an endpoint with id: %s - unable to "
                    "create entity with cluster details: %s",
                    str(device.ieee),
                    device.name,
                    endpoint_id,
                    cluster_details,
                )
                continue

            endpoint: Endpoint = device.endpoints[endpoint_id]
            cluster = (
                endpoint.zigpy_endpoint.in_clusters.get(cluster_id)
                if cluster_type is ClusterType.Server
                else endpoint.zigpy_endpoint.out_clusters.get(cluster_id)
            )

            if cluster is None:
                _LOGGER.warning(
                    "Device: %s-%s does not have a cluster with id: %s - "
                    "unable to create entity with cluster details: %s",
                    str(device.ieee),
                    device.name,
                    cluster_id,
                    cluster_details,
                )
                continue

            cluster_handler_id = f"{endpoint.id}:0x{cluster.cluster_id:04x}"
            cluster_handler = (
                endpoint.all_cluster_handlers.get(cluster_handler_id)
                if cluster_type is ClusterType.Server
                else endpoint.client_cluster_handlers.get(cluster_handler_id)
            )
            assert cluster_handler

            for entity_metadata in entity_metadata_list:
                platform = Platform(entity_metadata.entity_platform.value)
                metadata_type = type(entity_metadata)
                entity_class = QUIRKS_ENTITY_META_TO_ENTITY_CLASS.get(
                    (platform, metadata_type, entity_metadata.entity_type)
                )

                if entity_class is None:
                    _LOGGER.warning(
                        "Device: %s-%s has an entity with details: %s that does not"
                        " have an entity class mapping - unable to create entity",
                        str(device.ieee),
                        device.name,
                        {
                            zha_const.CLUSTER_DETAILS: cluster_details,
                            zha_const.ENTITY_METADATA: entity_metadata,
                        },
                    )
                    continue

                # automatically add the attribute to ZCL_INIT_ATTRS for the cluster
                # handler if it is not already in the list
                if (
                    hasattr(entity_metadata, "attribute_name")
                    and entity_metadata.attribute_name
                    not in cluster_handler.ZCL_INIT_ATTRS
                ):
                    init_attrs = cluster_handler.ZCL_INIT_ATTRS.copy()
                    init_attrs[entity_metadata.attribute_name] = (
                        entity_metadata.attribute_initialized_from_cache
                    )
                    cluster_handler.__dict__[zha_const.ZCL_INIT_ATTRS] = init_attrs

                endpoint.async_new_entity(
                    platform,
                    entity_class,
                    endpoint.unique_id,
                    [cluster_handler],
                    entity_metadata=entity_metadata,
                )

                _LOGGER.debug(
                    "'%s' platform -> '%s' using %s",
                    platform,
                    entity_class.__name__,
                    [cluster_handler.name],
                )

    @callback
    def discover_coordinator_device_entities(self, device: ZHADevice) -> None:
        """Discover entities for the coordinator device."""
        _LOGGER.debug(
            "Discovering entities for coordinator device: %s-%s",
            str(device.ieee),
            device.name,
        )
        state: State = device.gateway.application_controller.state
        platforms: dict[Platform, list] = get_zha_data(device.hass).platforms

        @callback
        def process_counters(counter_groups: str) -> None:
            for counter_group, counters in getattr(state, counter_groups).items():
                for counter in counters:
                    platforms[Platform.SENSOR].append(
                        (
                            sensor.DeviceCounterSensor,
                            (
                                f"{slugify(str(device.ieee))}_{counter_groups}_{counter_group}_{counter}",
                                device,
                                counter_groups,
                                counter_group,
                                counter,
                            ),
                            {},
                        )
                    )
                    _LOGGER.debug(
                        "'%s' platform -> '%s' using %s",
                        Platform.SENSOR,
                        sensor.DeviceCounterSensor.__name__,
                        f"counter groups[{counter_groups}] counter group[{counter_group}] counter[{counter}]",
                    )

        process_counters("counters")
        process_counters("broadcast_counters")
        process_counters("device_counters")
        process_counters("group_counters")

    @callback
    def discover_by_device_type(self, endpoint: Endpoint) -> None:
        """Process an endpoint on a zigpy device."""

        unique_id = endpoint.unique_id

        platform: str | None = self._device_configs.get(unique_id, {}).get(CONF_TYPE)
        if platform is None:
            ep_profile_id = endpoint.zigpy_endpoint.profile_id
            ep_device_type = endpoint.zigpy_endpoint.device_type
            platform = zha_regs.DEVICE_CLASS[ep_profile_id].get(ep_device_type)

        if platform and platform in zha_const.PLATFORMS:
            platform = cast(Platform, platform)

            cluster_handlers = endpoint.unclaimed_cluster_handlers()
            platform_entity_class, claimed = zha_regs.ZHA_ENTITIES.get_entity(
                platform,
                endpoint.device.manufacturer,
                endpoint.device.model,
                cluster_handlers,
                endpoint.device.quirk_id,
            )
            if platform_entity_class is None:
                return
            endpoint.claim_cluster_handlers(claimed)
            endpoint.async_new_entity(
                platform, platform_entity_class, unique_id, claimed
            )

    @callback
    def discover_by_cluster_id(self, endpoint: Endpoint) -> None:
        """Process an endpoint on a zigpy device."""

        items = zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS.items()
        single_input_clusters = {
            cluster_class: match
            for cluster_class, match in items
            if not isinstance(cluster_class, int)
        }
        remaining_cluster_handlers = endpoint.unclaimed_cluster_handlers()
        for cluster_handler in remaining_cluster_handlers:
            if (
                cluster_handler.cluster.cluster_id
                in zha_regs.CLUSTER_HANDLER_ONLY_CLUSTERS
            ):
                endpoint.claim_cluster_handlers([cluster_handler])
                continue

            platform = zha_regs.SINGLE_INPUT_CLUSTER_DEVICE_CLASS.get(
                cluster_handler.cluster.cluster_id
            )
            if platform is None:
                for cluster_class, match in single_input_clusters.items():
                    if isinstance(cluster_handler.cluster, cluster_class):
                        platform = match
                        break

            self.probe_single_cluster(platform, cluster_handler, endpoint)

        # until we can get rid of registries
        self.handle_on_off_output_cluster_exception(endpoint)

    @staticmethod
    def probe_single_cluster(
        platform: Platform | None,
        cluster_handler: ClusterHandler,
        endpoint: Endpoint,
    ) -> None:
        """Probe specified cluster for specific component."""
        if platform is None or platform not in zha_const.PLATFORMS:
            return
        cluster_handler_list = [cluster_handler]
        unique_id = f"{endpoint.unique_id}-{cluster_handler.cluster.cluster_id}"

        entity_class, claimed = zha_regs.ZHA_ENTITIES.get_entity(
            platform,
            endpoint.device.manufacturer,
            endpoint.device.model,
            cluster_handler_list,
            endpoint.device.quirk_id,
        )
        if entity_class is None:
            return
        endpoint.claim_cluster_handlers(claimed)
        endpoint.async_new_entity(platform, entity_class, unique_id, claimed)

    def handle_on_off_output_cluster_exception(self, endpoint: Endpoint) -> None:
        """Process output clusters of the endpoint."""

        profile_id = endpoint.zigpy_endpoint.profile_id
        device_type = endpoint.zigpy_endpoint.device_type
        if device_type in zha_regs.REMOTE_DEVICE_TYPES.get(profile_id, []):
            return

        for cluster_id, cluster in endpoint.zigpy_endpoint.out_clusters.items():
            platform = zha_regs.SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS.get(
                cluster.cluster_id
            )
            if platform is None:
                continue

            cluster_handler_classes = zha_regs.ZIGBEE_CLUSTER_HANDLER_REGISTRY.get(
                cluster_id, {None: ClusterHandler}
            )

            quirk_id = (
                endpoint.device.quirk_id
                if endpoint.device.quirk_id in cluster_handler_classes
                else None
            )

            cluster_handler_class = cluster_handler_classes.get(
                quirk_id, ClusterHandler
            )

            cluster_handler = cluster_handler_class(cluster, endpoint)
            self.probe_single_cluster(platform, cluster_handler, endpoint)

    @staticmethod
    @callback
    def discover_multi_entities(
        endpoint: Endpoint,
        config_diagnostic_entities: bool = False,
    ) -> None:
        """Process an endpoint on and discover multiple entities."""

        ep_profile_id = endpoint.zigpy_endpoint.profile_id
        ep_device_type = endpoint.zigpy_endpoint.device_type
        cmpt_by_dev_type = zha_regs.DEVICE_CLASS[ep_profile_id].get(ep_device_type)

        if config_diagnostic_entities:
            cluster_handlers = list(endpoint.all_cluster_handlers.values())
            ota_handler_id = f"{endpoint.id}:0x{Ota.cluster_id:04x}"
            if ota_handler_id in endpoint.client_cluster_handlers:
                cluster_handlers.append(
                    endpoint.client_cluster_handlers[ota_handler_id]
                )
            matches, claimed = zha_regs.ZHA_ENTITIES.get_config_diagnostic_entity(
                endpoint.device.manufacturer,
                endpoint.device.model,
                cluster_handlers,
                endpoint.device.quirk_id,
            )
        else:
            matches, claimed = zha_regs.ZHA_ENTITIES.get_multi_entity(
                endpoint.device.manufacturer,
                endpoint.device.model,
                endpoint.unclaimed_cluster_handlers(),
                endpoint.device.quirk_id,
            )

        endpoint.claim_cluster_handlers(claimed)
        for platform, ent_n_handler_list in matches.items():
            for entity_and_handler in ent_n_handler_list:
                _LOGGER.debug(
                    "'%s' platform -> '%s' using %s",
                    platform,
                    entity_and_handler.entity_class.__name__,
                    [ch.name for ch in entity_and_handler.claimed_cluster_handlers],
                )
        for platform, ent_n_handler_list in matches.items():
            for entity_and_handler in ent_n_handler_list:
                if platform == cmpt_by_dev_type:
                    # for well known device types,
                    # like thermostats we'll take only 1st class
                    endpoint.async_new_entity(
                        platform,
                        entity_and_handler.entity_class,
                        endpoint.unique_id,
                        entity_and_handler.claimed_cluster_handlers,
                    )
                    break
                first_ch = entity_and_handler.claimed_cluster_handlers[0]
                endpoint.async_new_entity(
                    platform,
                    entity_and_handler.entity_class,
                    f"{endpoint.unique_id}-{first_ch.cluster.cluster_id}",
                    entity_and_handler.claimed_cluster_handlers,
                )

    def initialize(self, hass: HomeAssistant) -> None:
        """Update device overrides config."""
        zha_config = get_zha_data(hass).yaml_config
        if overrides := zha_config.get(zha_const.CONF_DEVICE_CONFIG):
            self._device_configs.update(overrides)


class GroupProbe:
    """Determine the appropriate component for a group."""

    _hass: HomeAssistant

    def __init__(self) -> None:
        """Initialize instance."""
        self._unsubs: list[Callable[[], None]] = []

    def initialize(self, hass: HomeAssistant) -> None:
        """Initialize the group probe."""
        self._hass = hass
        self._unsubs.append(
            async_dispatcher_connect(
                hass, zha_const.SIGNAL_GROUP_ENTITY_REMOVED, self._reprobe_group
            )
        )

    def cleanup(self) -> None:
        """Clean up on when ZHA shuts down."""
        for unsub in self._unsubs[:]:
            unsub()
            self._unsubs.remove(unsub)

    @callback
    def _reprobe_group(self, group_id: int) -> None:
        """Reprobe a group for entities after its members change."""
        zha_gateway = get_zha_gateway(self._hass)
        if (zha_group := zha_gateway.groups.get(group_id)) is None:
            return
        self.discover_group_entities(zha_group)

    @callback
    def discover_group_entities(self, group: ZHAGroup) -> None:
        """Process a group and create any entities that are needed."""
        # only create a group entity if there are 2 or more members in a group
        if len(group.members) < 2:
            _LOGGER.debug(
                "Group: %s:0x%04x has less than 2 members - skipping entity discovery",
                group.name,
                group.group_id,
            )
            return

        entity_domains = GroupProbe.determine_entity_domains(self._hass, group)

        if not entity_domains:
            return

        zha_data = get_zha_data(self._hass)
        zha_gateway = get_zha_gateway(self._hass)

        for domain in entity_domains:
            entity_class = zha_regs.ZHA_ENTITIES.get_group_entity(domain)
            if entity_class is None:
                continue
            zha_data.platforms[domain].append(
                (
                    entity_class,
                    (
                        group.get_domain_entity_ids(domain),
                        f"{domain}_zha_group_0x{group.group_id:04x}",
                        group.group_id,
                        zha_gateway.coordinator_zha_device,
                    ),
                    {},
                )
            )
        async_dispatcher_send(self._hass, zha_const.SIGNAL_ADD_ENTITIES)

    @staticmethod
    def determine_entity_domains(
        hass: HomeAssistant, group: ZHAGroup
    ) -> list[Platform]:
        """Determine the entity domains for this group."""
        entity_registry = er.async_get(hass)

        entity_domains: list[Platform] = []
        all_domain_occurrences: list[Platform] = []

        for member in group.members:
            if member.device.is_coordinator:
                continue
            entities = async_entries_for_device(
                entity_registry,
                member.device.device_id,
                include_disabled_entities=True,
            )
            all_domain_occurrences.extend(
                [
                    cast(Platform, entity.domain)
                    for entity in entities
                    if entity.domain in zha_regs.GROUP_ENTITY_DOMAINS
                ]
            )
        if not all_domain_occurrences:
            return entity_domains
        # get all domains we care about if there are more than 2 entities of this domain
        counts = Counter(all_domain_occurrences)
        entity_domains = [domain[0] for domain in counts.items() if domain[1] >= 2]
        _LOGGER.debug(
            "The entity domains are: %s for group: %s:0x%04x",
            entity_domains,
            group.name,
            group.group_id,
        )
        return entity_domains


PROBE = ProbeEndpoint()
GROUP_PROBE = GroupProbe()
