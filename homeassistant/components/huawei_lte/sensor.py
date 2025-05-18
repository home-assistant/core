"""Support for Huawei LTE sensors."""

from __future__ import annotations

from bisect import bisect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import Router
from .const import (
    DOMAIN,
    KEY_DEVICE_INFORMATION,
    KEY_DEVICE_SIGNAL,
    KEY_MONITORING_CHECK_NOTIFICATIONS,
    KEY_MONITORING_MONTH_STATISTICS,
    KEY_MONITORING_STATUS,
    KEY_MONITORING_TRAFFIC_STATISTICS,
    KEY_NET_CURRENT_PLMN,
    KEY_NET_NET_MODE,
    KEY_SMS_SMS_COUNT,
    SENSOR_KEYS,
)
from .entity import HuaweiLteBaseEntityWithDevice

_LOGGER = logging.getLogger(__name__)


def format_default(value: StateType) -> tuple[StateType, str | None]:
    """Format value."""
    unit = None
    if value is not None:
        # Clean up value and infer unit, e.g. -71dBm, 15 dB
        if match := re.match(
            r"((&[gl]t;|[><])=?)?(?P<value>.+?)\s*(?P<unit>[a-zA-Z]+)\s*$", str(value)
        ):
            try:
                value = float(match.group("value"))
                unit = match.group("unit")
            except ValueError:
                pass
    return value, unit


def format_freq_mhz(value: StateType) -> tuple[StateType, UnitOfFrequency]:
    """Format a frequency value for which source is in tenths of MHz."""
    return (
        float(value) / 10 if value is not None else None,
        UnitOfFrequency.MEGAHERTZ,
    )


def format_last_reset_elapsed_seconds(value: str | None) -> datetime | None:
    """Convert elapsed seconds to last reset datetime."""
    if value is None:
        return None
    try:
        last_reset = datetime.now() - timedelta(seconds=int(value))
        last_reset.replace(microsecond=0)
    except ValueError:
        return None
    return last_reset


def signal_icon(limits: Sequence[int], value: StateType) -> str:
    """Get signal icon."""
    return (
        "mdi:signal-cellular-outline",
        "mdi:signal-cellular-1",
        "mdi:signal-cellular-2",
        "mdi:signal-cellular-3",
    )[bisect(limits, value if value is not None else -1000)]


def bandwidth_icon(limits: Sequence[int], value: StateType) -> str:
    """Get bandwidth icon."""
    return (
        "mdi:speedometer-slow",
        "mdi:speedometer-medium",
        "mdi:speedometer",
    )[bisect(limits, value if value is not None else -1000)]


@dataclass
class HuaweiSensorGroup:
    """Class describing Huawei LTE sensor groups."""

    descriptions: dict[str, HuaweiSensorEntityDescription]
    include: re.Pattern[str] | None = None
    exclude: re.Pattern[str] | None = None


@dataclass(frozen=True)
class HuaweiSensorEntityDescription(SensorEntityDescription):
    """Class describing Huawei LTE sensor entities."""

    # HuaweiLteSensor does not support UNDEFINED or None,
    # restrict the type to str.
    name: str = ""

    format_fn: Callable[[str], tuple[StateType, str | None]] = format_default
    icon_fn: Callable[[StateType], str] | None = None
    device_class_fn: Callable[[StateType], SensorDeviceClass | None] | None = None
    last_reset_item: str | None = None
    last_reset_format_fn: Callable[[str | None], datetime | None] | None = None


SENSOR_META: dict[str, HuaweiSensorGroup] = {
    #
    # Device information
    #
    KEY_DEVICE_INFORMATION: HuaweiSensorGroup(
        include=re.compile(r"^(WanIP.*Address|uptime)$", re.IGNORECASE),
        descriptions={
            "uptime": HuaweiSensorEntityDescription(
                key="uptime",
                translation_key="uptime",
                native_unit_of_measurement=UnitOfTime.SECONDS,
                device_class=SensorDeviceClass.DURATION,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "WanIPAddress": HuaweiSensorEntityDescription(
                key="WanIPAddress",
                translation_key="wan_ip_address",
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "WanIPv6Address": HuaweiSensorEntityDescription(
                key="WanIPv6Address",
                translation_key="wan_ipv6_address",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    #
    # Signal
    #
    KEY_DEVICE_SIGNAL: HuaweiSensorGroup(
        descriptions={
            "arfcn": HuaweiSensorEntityDescription(
                key="arfcn",
                translation_key="arfcn",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "band": HuaweiSensorEntityDescription(
                key="band",
                translation_key="band",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "bsic": HuaweiSensorEntityDescription(
                key="bsic",
                translation_key="base_station_identity_code",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "cell_id": HuaweiSensorEntityDescription(
                key="cell_id",
                translation_key="cell_id",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "cqi0": HuaweiSensorEntityDescription(
                key="cqi0",
                translation_key="cqi0",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "cqi1": HuaweiSensorEntityDescription(
                key="cqi1",
                translation_key="cqi1",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "dl_mcs": HuaweiSensorEntityDescription(
                key="dl_mcs",
                translation_key="downlink_mcs",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "dlbandwidth": HuaweiSensorEntityDescription(
                key="dlbandwidth",
                translation_key="downlink_bandwidth",
                icon_fn=lambda x: bandwidth_icon((8, 15), x),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "dlfrequency": HuaweiSensorEntityDescription(
                key="dlfrequency",
                translation_key="downlink_frequency",
                device_class=SensorDeviceClass.FREQUENCY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "earfcn": HuaweiSensorEntityDescription(
                key="earfcn",
                translation_key="earfcn",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ecio": HuaweiSensorEntityDescription(
                key="ecio",
                translation_key="ecio",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # https://wiki.teltonika.lt/view/EC/IO
                icon_fn=lambda x: signal_icon((-20, -10, -6), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "enodeb_id": HuaweiSensorEntityDescription(
                key="enodeb_id",
                translation_key="enodeb_id",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ims": HuaweiSensorEntityDescription(
                key="ims",
                translation_key="ims",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "lac": HuaweiSensorEntityDescription(
                key="lac",
                translation_key="lac",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ltedlfreq": HuaweiSensorEntityDescription(
                key="ltedlfreq",
                translation_key="lte_downlink_frequency",
                format_fn=format_freq_mhz,
                suggested_display_precision=0,
                device_class=SensorDeviceClass.FREQUENCY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "lteulfreq": HuaweiSensorEntityDescription(
                key="lteulfreq",
                translation_key="lte_uplink_frequency",
                format_fn=format_freq_mhz,
                suggested_display_precision=0,
                device_class=SensorDeviceClass.FREQUENCY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "mode": HuaweiSensorEntityDescription(
                key="mode",
                translation_key="mode",
                format_fn=lambda x: (
                    {"0": "2G", "2": "3G", "7": "4G"}.get(x),
                    None,
                ),
                icon_fn=lambda x: (
                    {
                        "2G": "mdi:signal-2g",
                        "3G": "mdi:signal-3g",
                        "4G": "mdi:signal-4g",
                    }.get(str(x), "mdi:signal")
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nei_cellid": HuaweiSensorEntityDescription(
                key="nei_cellid",
                translation_key="nei_cellid",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrbler": HuaweiSensorEntityDescription(
                key="nrbler",
                translation_key="nrbler",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrcqi0": HuaweiSensorEntityDescription(
                key="nrcqi0",
                translation_key="nrcqi0",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrcqi1": HuaweiSensorEntityDescription(
                key="nrcqi1",
                translation_key="nrcqi1",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrdlbandwidth": HuaweiSensorEntityDescription(
                key="nrdlbandwidth",
                translation_key="nrdlbandwidth",
                # Could add icon_fn like we have for dlbandwidth,
                # if we find a good source what to use as 5G thresholds.
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrdlmcs": HuaweiSensorEntityDescription(
                key="nrdlmcs",
                translation_key="nrdlmcs",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrearfcn": HuaweiSensorEntityDescription(
                key="nrearfcn",
                translation_key="nrearfcn",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrrank": HuaweiSensorEntityDescription(
                key="nrrank",
                translation_key="nrrank",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrrsrp": HuaweiSensorEntityDescription(
                key="nrrsrp",
                translation_key="nrrsrp",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # Could add icon_fn as in rsrp, source for 5G thresholds?
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "nrrsrq": HuaweiSensorEntityDescription(
                key="nrrsrq",
                translation_key="nrrsrq",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # Could add icon_fn as in rsrq, source for 5G thresholds?
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "nrsinr": HuaweiSensorEntityDescription(
                key="nrsinr",
                translation_key="nrsinr",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # Could add icon_fn as in sinr, source for thresholds?
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "nrtxpower": HuaweiSensorEntityDescription(
                key="nrtxpower",
                translation_key="nrtxpower",
                # The value we get from the API tends to consist of several, e.g.
                #     PPusch:21dBm PPucch:2dBm PSrs:0dBm PPrach:10dBm
                # Present as SIGNAL_STRENGTH only if it was parsed to a number.
                # We could try to parse this to separate component sensors sometime.
                device_class_fn=lambda x: (
                    SensorDeviceClass.SIGNAL_STRENGTH
                    if isinstance(x, (float, int))
                    else None
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrulbandwidth": HuaweiSensorEntityDescription(
                key="nrulbandwidth",
                translation_key="nrulbandwidth",
                # Could add icon_fn as in ulbandwidth, source for 5G thresholds?
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "nrulmcs": HuaweiSensorEntityDescription(
                key="nrulmcs",
                translation_key="nrulmcs",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "pci": HuaweiSensorEntityDescription(
                key="pci",
                translation_key="pci",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "plmn": HuaweiSensorEntityDescription(
                key="plmn",
                translation_key="plmn",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "rac": HuaweiSensorEntityDescription(
                key="rac",
                translation_key="rac",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "rrc_status": HuaweiSensorEntityDescription(
                key="rrc_status",
                translation_key="rrc_status",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "rscp": HuaweiSensorEntityDescription(
                key="rscp",
                translation_key="rscp",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # https://wiki.teltonika.lt/view/RSCP
                icon_fn=lambda x: signal_icon((-95, -85, -75), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "rsrp": HuaweiSensorEntityDescription(
                key="rsrp",
                translation_key="rsrp",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # http://www.lte-anbieter.info/technik/rsrp.php  # codespell:ignore technik
                icon_fn=lambda x: signal_icon((-110, -95, -80), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "rsrq": HuaweiSensorEntityDescription(
                key="rsrq",
                translation_key="rsrq",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # http://www.lte-anbieter.info/technik/rsrq.php  # codespell:ignore technik
                icon_fn=lambda x: signal_icon((-11, -8, -5), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "rssi": HuaweiSensorEntityDescription(
                key="rssi",
                translation_key="rssi",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # https://eyesaas.com/wi-fi-signal-strength/
                icon_fn=lambda x: signal_icon((-80, -70, -60), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "rxlev": HuaweiSensorEntityDescription(
                key="rxlev",
                translation_key="rxlev",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "sc": HuaweiSensorEntityDescription(
                key="sc",
                translation_key="sc",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "sinr": HuaweiSensorEntityDescription(
                key="sinr",
                translation_key="sinr",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                # http://www.lte-anbieter.info/technik/sinr.php  # codespell:ignore technik
                icon_fn=lambda x: signal_icon((0, 5, 10), x),
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=True,
            ),
            "tac": HuaweiSensorEntityDescription(
                key="tac",
                translation_key="tac",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "tdd": HuaweiSensorEntityDescription(
                key="tdd",
                translation_key="tdd",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "transmode": HuaweiSensorEntityDescription(
                key="transmode",
                translation_key="transmission_mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "txpower": HuaweiSensorEntityDescription(
                key="txpower",
                translation_key="transmit_power",
                # The value we get from the API tends to consist of several, e.g.
                #     PPusch:15dBm PPucch:2dBm PSrs:42dBm PPrach:1dBm
                # Present as SIGNAL_STRENGTH only if it was parsed to a number.
                # We could try to parse this to separate component sensors sometime.
                device_class_fn=lambda x: (
                    SensorDeviceClass.SIGNAL_STRENGTH
                    if isinstance(x, (float, int))
                    else None
                ),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ul_mcs": HuaweiSensorEntityDescription(
                key="ul_mcs",
                translation_key="uplink_mcs",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ulbandwidth": HuaweiSensorEntityDescription(
                key="ulbandwidth",
                translation_key="uplink_bandwidth",
                icon_fn=lambda x: bandwidth_icon((8, 15), x),
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "ulfrequency": HuaweiSensorEntityDescription(
                key="ulfrequency",
                translation_key="uplink_frequency",
                device_class=SensorDeviceClass.FREQUENCY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "wdlfreq": HuaweiSensorEntityDescription(
                key="wdlfreq",
                translation_key="wdlfreq",
                device_class=SensorDeviceClass.FREQUENCY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        }
    ),
    #
    # Monitoring
    #
    KEY_MONITORING_CHECK_NOTIFICATIONS: HuaweiSensorGroup(
        exclude=re.compile(
            r"^(onlineupdatestatus|smsstoragefull)$",
            re.IGNORECASE,
        ),
        descriptions={
            "UnreadMessage": HuaweiSensorEntityDescription(
                key="UnreadMessage",
                translation_key="sms_unread",
            ),
        },
    ),
    KEY_MONITORING_MONTH_STATISTICS: HuaweiSensorGroup(
        exclude=re.compile(
            r"^(currentday|month)(duration|lastcleartime)$", re.IGNORECASE
        ),
        descriptions={
            "CurrentDayUsed": HuaweiSensorEntityDescription(
                key="CurrentDayUsed",
                translation_key="current_day_transfer",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL,
                last_reset_item="CurrentDayDuration",
                last_reset_format_fn=format_last_reset_elapsed_seconds,
            ),
            "CurrentMonthDownload": HuaweiSensorEntityDescription(
                key="CurrentMonthDownload",
                translation_key="current_month_download",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL,
                last_reset_item="MonthDuration",
                last_reset_format_fn=format_last_reset_elapsed_seconds,
            ),
            "CurrentMonthUpload": HuaweiSensorEntityDescription(
                key="CurrentMonthUpload",
                translation_key="current_month_upload",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL,
                last_reset_item="MonthDuration",
                last_reset_format_fn=format_last_reset_elapsed_seconds,
            ),
        },
    ),
    KEY_MONITORING_STATUS: HuaweiSensorGroup(
        include=re.compile(
            r"^(batterypercent|currentwifiuser|(primary|secondary).*dns)$",
            re.IGNORECASE,
        ),
        descriptions={
            "BatteryPercent": HuaweiSensorEntityDescription(
                key="BatteryPercent",
                translation_key="battery",
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "CurrentWifiUser": HuaweiSensorEntityDescription(
                key="CurrentWifiUser",
                translation_key="wifi_clients_connected",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "PrimaryDns": HuaweiSensorEntityDescription(
                key="PrimaryDns",
                translation_key="primary_dns_server",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "PrimaryIPv6Dns": HuaweiSensorEntityDescription(
                key="PrimaryIPv6Dns",
                translation_key="primary_ipv6_dns_server",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "SecondaryDns": HuaweiSensorEntityDescription(
                key="SecondaryDns",
                translation_key="secondary_dns_server",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "SecondaryIPv6Dns": HuaweiSensorEntityDescription(
                key="SecondaryIPv6Dns",
                translation_key="secondary_ipv6_dns_server",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    KEY_MONITORING_TRAFFIC_STATISTICS: HuaweiSensorGroup(
        exclude=re.compile(r"^showtraffic$", re.IGNORECASE),
        descriptions={
            "CurrentConnectTime": HuaweiSensorEntityDescription(
                key="CurrentConnectTime",
                translation_key="current_connection_duration",
                native_unit_of_measurement=UnitOfTime.SECONDS,
                device_class=SensorDeviceClass.DURATION,
            ),
            "CurrentDownload": HuaweiSensorEntityDescription(
                key="CurrentDownload",
                translation_key="current_connection_download",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "CurrentDownloadRate": HuaweiSensorEntityDescription(
                key="CurrentDownloadRate",
                translation_key="current_download_rate",
                native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                device_class=SensorDeviceClass.DATA_RATE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            "CurrentUpload": HuaweiSensorEntityDescription(
                key="CurrentUpload",
                translation_key="current_connection_upload",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "CurrentUploadRate": HuaweiSensorEntityDescription(
                key="CurrentUploadRate",
                translation_key="current_upload_rate",
                native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
                device_class=SensorDeviceClass.DATA_RATE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            "TotalConnectTime": HuaweiSensorEntityDescription(
                key="TotalConnectTime",
                translation_key="total_connected_duration",
                native_unit_of_measurement=UnitOfTime.SECONDS,
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "TotalDownload": HuaweiSensorEntityDescription(
                key="TotalDownload",
                translation_key="total_download",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "TotalUpload": HuaweiSensorEntityDescription(
                key="TotalUpload",
                translation_key="total_upload",
                native_unit_of_measurement=UnitOfInformation.BYTES,
                device_class=SensorDeviceClass.DATA_SIZE,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
        },
    ),
    #
    # Network
    #
    KEY_NET_CURRENT_PLMN: HuaweiSensorGroup(
        exclude=re.compile(r"^(Rat|ShortName|Spn)$", re.IGNORECASE),
        descriptions={
            "FullName": HuaweiSensorEntityDescription(
                key="FullName",
                translation_key="operator_name",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "Numeric": HuaweiSensorEntityDescription(
                key="Numeric",
                translation_key="operator_code",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "State": HuaweiSensorEntityDescription(
                key="State",
                translation_key="operator_search_mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    KEY_NET_NET_MODE: HuaweiSensorGroup(
        include=re.compile(r"^NetworkMode$", re.IGNORECASE),
        descriptions={
            "NetworkMode": HuaweiSensorEntityDescription(
                key="NetworkMode",
                translation_key="preferred_network_mode",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        },
    ),
    #
    # SMS
    #
    KEY_SMS_SMS_COUNT: HuaweiSensorGroup(
        descriptions={
            "LocalDeleted": HuaweiSensorEntityDescription(
                key="LocalDeleted",
                translation_key="sms_deleted_device",
            ),
            "LocalDraft": HuaweiSensorEntityDescription(
                key="LocalDraft",
                translation_key="sms_drafts_device",
            ),
            "LocalInbox": HuaweiSensorEntityDescription(
                key="LocalInbox",
                translation_key="sms_inbox_device",
            ),
            "LocalMax": HuaweiSensorEntityDescription(
                key="LocalMax",
                translation_key="sms_capacity_device",
            ),
            "LocalOutbox": HuaweiSensorEntityDescription(
                key="LocalOutbox",
                translation_key="sms_outbox_device",
            ),
            "LocalUnread": HuaweiSensorEntityDescription(
                key="LocalUnread",
                translation_key="sms_unread_device",
            ),
            "SimDraft": HuaweiSensorEntityDescription(
                key="SimDraft",
                translation_key="sms_drafts_sim",
            ),
            "SimInbox": HuaweiSensorEntityDescription(
                key="SimInbox",
                translation_key="sms_inbox_sim",
            ),
            "SimMax": HuaweiSensorEntityDescription(
                key="SimMax",
                translation_key="sms_capacity_sim",
            ),
            "SimOutbox": HuaweiSensorEntityDescription(
                key="SimOutbox",
                translation_key="sms_outbox_sim",
            ),
            "SimUnread": HuaweiSensorEntityDescription(
                key="SimUnread",
                translation_key="sms_unread_sim",
            ),
            "SimUsed": HuaweiSensorEntityDescription(
                key="SimUsed",
                translation_key="sms_messages_sim",
            ),
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    sensors: list[Entity] = []
    for key in SENSOR_KEYS:
        if not (items := router.data.get(key)):
            continue
        if key_meta := SENSOR_META.get(key):
            if key_meta.include:
                items = filter(key_meta.include.search, items)
            if key_meta.exclude:
                items = [x for x in items if not key_meta.exclude.search(x)]
        sensors.extend(
            HuaweiLteSensor(
                router,
                key,
                item,
                SENSOR_META[key].descriptions.get(
                    item, HuaweiSensorEntityDescription(key=item)
                ),
            )
            for item in items
        )

    async_add_entities(sensors, True)


class HuaweiLteSensor(HuaweiLteBaseEntityWithDevice, SensorEntity):
    """Huawei LTE sensor entity."""

    entity_description: HuaweiSensorEntityDescription
    _state: StateType = None
    _unit: str | None = None
    _last_reset: datetime | None = None

    def __init__(
        self,
        router: Router,
        key: str,
        item: str,
        entity_description: HuaweiSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(router)
        self.key = key
        self.item = item
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].append(f"{SENSOR_DOMAIN}/{self.item}")
        if self.entity_description.last_reset_item:
            self.router.subscriptions[self.key].append(
                f"{SENSOR_DOMAIN}/{self.entity_description.last_reset_item}"
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(f"{SENSOR_DOMAIN}/{self.item}")
        if self.entity_description.last_reset_item:
            self.router.subscriptions[self.key].remove(
                f"{SENSOR_DOMAIN}/{self.entity_description.last_reset_item}"
            )

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return sensor's unit of measurement."""
        return self.entity_description.native_unit_of_measurement or self._unit

    @property
    def icon(self) -> str | None:
        """Return icon for sensor."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.state)
        return super().icon

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return device class for sensor."""
        if self.entity_description.device_class_fn:
            # Note: using self.state could infloop here.
            return self.entity_description.device_class_fn(self.native_value)
        return super().device_class

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        return self._last_reset

    async def async_update(self) -> None:
        """Update state."""
        try:
            value = self.router.data[self.key][self.item]
        except KeyError:
            _LOGGER.debug("%s[%s] not in data", self.key, self.item)
            value = None

        last_reset = None
        if (
            self.entity_description.last_reset_item
            and self.entity_description.last_reset_format_fn
        ):
            try:
                last_reset_value = self.router.data[self.key][
                    self.entity_description.last_reset_item
                ]
            except KeyError:
                _LOGGER.debug(
                    "%s[%s] not in data",
                    self.key,
                    self.entity_description.last_reset_item,
                )
            else:
                last_reset = self.entity_description.last_reset_format_fn(
                    last_reset_value
                )

        self._state, self._unit = self.entity_description.format_fn(value)
        self._last_reset = last_reset
        self._available = value is not None
