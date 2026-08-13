"""Definitions for TrueNAS binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import (
    SCHEMA_SERVICE_APP_START,
    SCHEMA_SERVICE_APP_STOP,
    SCHEMA_SERVICE_CONTAINER_RESTART,
    SCHEMA_SERVICE_CONTAINER_START,
    SCHEMA_SERVICE_CONTAINER_STOP,
    SCHEMA_SERVICE_SERVICE_RELOAD,
    SCHEMA_SERVICE_SERVICE_RESTART,
    SCHEMA_SERVICE_SERVICE_START,
    SCHEMA_SERVICE_SERVICE_STOP,
    SCHEMA_SERVICE_VM_RESTART,
    SCHEMA_SERVICE_VM_START,
    SCHEMA_SERVICE_VM_STOP,
    SERVICE_APP_START,
    SERVICE_APP_STOP,
    SERVICE_CONTAINER_RESTART,
    SERVICE_CONTAINER_START,
    SERVICE_CONTAINER_STOP,
    SERVICE_SERVICE_RELOAD,
    SERVICE_SERVICE_RESTART,
    SERVICE_SERVICE_START,
    SERVICE_SERVICE_STOP,
    SERVICE_VM_RESTART,
    SERVICE_VM_START,
    SERVICE_VM_STOP,
)
from .entity import TrueNASEntityDescription

DEVICE_ATTRIBUTES_POOL = (
    "path",
    "status",
    "healthy",
    "is_decrypted",
    "autotrim",
    "scrub_state",
    "scrub_start",
    "scrub_end",
    "scrub_secs_left",
    "available",
    "total",
)

DEVICE_ATTRIBUTES_VM = (
    "type",
    "cpu",
    "memory",
    "autostart",
    "image",
)

DEVICE_ATTRIBUTES_CONTAINER = (
    "type",
    "status",
    "cpu",
    "memory",
    "autostart",
    "image",
    "ip_address",
)

DEVICE_ATTRIBUTES_SERVICE = (
    "enable",
    "state",
)

DEVICE_ATTRIBUTES_APP = (
    "name",
    "version",
    "latest_version",
    "human_version",
    "update_available",
    "image_updates_available",
    "custom_app",
    "portal",
)

DEVICE_ATTRIBUTES_NETWORK = (
    "description",
    "mtu",
    "link_state",
    "active_media_type",
    "active_media_subtype",
    "link_address",
)

DEVICE_ATTRIBUTES_DIRECTORYSERVICE = (
    "type",
    "status",
    "status_msg",
    "domain",
    "kerberos_realm",
    "account_cache",
    "dns_updates",
    "site",
)


@dataclass(frozen=True, kw_only=True)
class TrueNASBinarySensorEntityDescription(
    BinarySensorEntityDescription, TrueNASEntityDescription
):
    """Class describing entities."""

    data_is_on: str = "available"
    func: str = "TrueNASBinarySensor"


SENSOR_TYPES: tuple[TrueNASBinarySensorEntityDescription, ...] = (
    TrueNASBinarySensorEntityDescription(
        key="disk_issues",
        translation_key="disk_issues",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="alerts",
        data_is_on="disk_issues",
        data_name=None,
        data_uid=None,
        data_reference=None,
    ),
    TrueNASBinarySensorEntityDescription(
        key="pool_healthy",
        translation_key="pool_healthy",
        device_class=None,
        entity_category=None,
        ha_group="Pools",
        data_path="pool",
        data_is_on="healthy",
        data_name="name",
        data_uid=None,
        data_reference="guid",
        data_attributes_list=DEVICE_ATTRIBUTES_POOL,
    ),
    TrueNASBinarySensorEntityDescription(
        key="vm",
        name="",
        translation_key="vm",
        device_class=None,
        entity_category=None,
        ha_group="VMs",
        data_path="vm",
        data_is_on="running",
        data_name="name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_VM,
        func="TrueNASVMBinarySensor",
    ),
    TrueNASBinarySensorEntityDescription(
        key="container",
        name="",
        translation_key="container",
        device_class=None,
        entity_category=None,
        ha_group="Containers",
        data_path="container",
        data_is_on="running",
        data_name="name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_CONTAINER,
        func="TrueNASContainerBinarySensor",
    ),
    TrueNASBinarySensorEntityDescription(
        key="service",
        name="",
        translation_key="service",
        device_class=None,
        entity_category=None,
        entity_registry_enabled_default=False,
        ha_group="Services",
        data_path="service",
        data_is_on="running",
        data_name="display_name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_SERVICE,
        func="TrueNASServiceBinarySensor",
    ),
    TrueNASBinarySensorEntityDescription(
        key="app",
        name="",
        translation_key="app",
        device_class=None,
        entity_category=None,
        ha_group="Apps",
        data_path="app",
        data_is_on="running",
        data_name="name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_APP,
        func="TrueNASAppBinarySensor",
    ),
    TrueNASBinarySensorEntityDescription(
        key="interface",
        translation_key="interface",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="Network",
        data_path="interface",
        data_is_on="link_up",
        data_name="name",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_NETWORK,
    ),
    TrueNASBinarySensorEntityDescription(
        key="directoryservices",
        name="",
        translation_key="directoryservices",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="Directory Services",
        data_path="directoryservices",
        data_is_on="healthy",
        data_name="domain",
        data_uid=None,
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_DIRECTORYSERVICE,
    ),
    TrueNASBinarySensorEntityDescription(
        key="certificate_expired",
        translation_key="certificate_expired",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="Certificates",
        data_path="certificate",
        data_is_on="expired",
        data_name="name",
        data_uid=None,
        data_reference="name",
    ),
)


class BinarySensorService(NamedTuple):
    """Service definition."""

    name: str
    schema: Any
    action: str


SENSOR_SERVICES: tuple[BinarySensorService, ...] = (
    BinarySensorService(SERVICE_VM_START, SCHEMA_SERVICE_VM_START, "start"),
    BinarySensorService(SERVICE_VM_STOP, SCHEMA_SERVICE_VM_STOP, "stop"),
    BinarySensorService(SERVICE_VM_RESTART, SCHEMA_SERVICE_VM_RESTART, "restart"),
    BinarySensorService(
        SERVICE_CONTAINER_START, SCHEMA_SERVICE_CONTAINER_START, "start"
    ),
    BinarySensorService(SERVICE_CONTAINER_STOP, SCHEMA_SERVICE_CONTAINER_STOP, "stop"),
    BinarySensorService(
        SERVICE_CONTAINER_RESTART, SCHEMA_SERVICE_CONTAINER_RESTART, "restart"
    ),
    BinarySensorService(SERVICE_SERVICE_START, SCHEMA_SERVICE_SERVICE_START, "start"),
    BinarySensorService(SERVICE_SERVICE_STOP, SCHEMA_SERVICE_SERVICE_STOP, "stop"),
    BinarySensorService(
        SERVICE_SERVICE_RESTART, SCHEMA_SERVICE_SERVICE_RESTART, "restart"
    ),
    BinarySensorService(
        SERVICE_SERVICE_RELOAD, SCHEMA_SERVICE_SERVICE_RELOAD, "reload"
    ),
    BinarySensorService(SERVICE_APP_START, SCHEMA_SERVICE_APP_START, "start"),
    BinarySensorService(SERVICE_APP_STOP, SCHEMA_SERVICE_APP_STOP, "stop"),
)
