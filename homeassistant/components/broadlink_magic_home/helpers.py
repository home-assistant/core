"""Serialization helpers for BroadLink Magic config entries."""

from typing import Any

from broadlink_magic import (
    DiscoveredRMMax,
    Family,
    ImportedDevice,
    ImportedGroup,
    ImportedScene,
    RMProfile,
    Room,
    VirtualSubToken,
    mark_rm_children,
)

from .const import (
    CONF_BLETOKEN,
    CONF_DEVICES,
    CONF_FAMILY_ID,
    CONF_FAMILY_NAME,
    CONF_FAMILY_PID,
    CONF_FAMILY_TOKEN,
    CONF_GATEWAYS,
    CONF_GROUPS,
    CONF_ROOMS,
    CONF_SCENES,
    CONF_VIRTUAL_SUBTOKENS,
)


def family_to_entry_data(
    family: Family, gateways: list[DiscoveredRMMax]
) -> dict[str, Any]:
    """Serialize only runtime-required family data."""
    return {
        CONF_FAMILY_ID: family.family_id,
        CONF_FAMILY_NAME: family.name,
        CONF_FAMILY_PID: family.pid,
        CONF_FAMILY_TOKEN: family.token,
        CONF_BLETOKEN: family.bletoken,
        CONF_ROOMS: [
            {"room_id": room.room_id, "name": room.name} for room in family.rooms
        ],
        CONF_DEVICES: [
            {
                "did": device.did,
                "pid": device.pid,
                "name": device.name,
                "mac": device.mac,
                "sdid": device.sdid,
                "spid": device.spid,
                "short_addr": device.short_addr,
                "ble_category": device.ble_category,
                "ble_device_type": device.ble_device_type,
                "devtype": device.devtype,
                "room_id": device.room_id,
                "token": device.token,
                "version": device.version,
                "channel_count": device.channel_count,
                "channel_names": device.channel_names,
                "is_rm_child": device.is_rm_child,
                "rm_profile": (
                    device.rm_profile.value if device.rm_profile is not None else None
                ),
                "functions": device.functions,
            }
            for device in family.devices
        ],
        CONF_GATEWAYS: gateways_to_entry_data(gateways),
        CONF_GROUPS: [
            {
                "group_id": group.group_id,
                "name": group.name,
                "ble_category": group.ble_category,
                "room_id": group.room_id,
                "room_name": group.room_name,
                "member_ids": group.member_ids,
            }
            for group in family.groups
        ],
        CONF_SCENES: [
            {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "room_id": scene.room_id,
                "room_name": scene.room_name,
                "module_devices": scene.module_devices,
            }
            for scene in family.scenes
        ],
        CONF_VIRTUAL_SUBTOKENS: [
            {
                "did": token.did,
                "pid": token.pid,
                "token": token.token,
                "type": token.type,
            }
            for token in family.virtual_subtokens
        ],
    }


def family_from_entry_data(data: dict[str, Any]) -> Family:
    """Reconstruct a family from a config entry."""
    devices = [
        ImportedDevice(
            did=item["did"],
            pid=item["pid"],
            name=item["name"],
            mac=item.get("mac", ""),
            sdid=item.get("sdid", ""),
            spid=item.get("spid", ""),
            short_addr=item.get("short_addr"),
            ble_category=item.get("ble_category", ""),
            ble_device_type=item.get("ble_device_type", ""),
            devtype=item.get("devtype"),
            room_id=item.get("room_id"),
            token=item.get("token", ""),
            version=item.get("version", ""),
            channel_count=item.get("channel_count", 1),
            channel_names=list(item.get("channel_names") or []),
            is_rm_child=item.get("is_rm_child", False),
            rm_profile=(
                RMProfile(profile)
                if (profile := item.get("rm_profile")) is not None
                else None
            ),
            functions=dict(item.get("functions") or {}),
        )
        for item in data[CONF_DEVICES]
    ]
    if any("is_rm_child" not in item for item in data[CONF_DEVICES]):
        mark_rm_children(devices)
    return Family(
        family_id=data[CONF_FAMILY_ID],
        name=data[CONF_FAMILY_NAME],
        bletoken=data[CONF_BLETOKEN],
        pid=data.get(CONF_FAMILY_PID, ""),
        token=data.get(CONF_FAMILY_TOKEN, ""),
        rooms=[
            Room(room_id=item["room_id"], name=item["name"])
            for item in data.get(CONF_ROOMS, [{"room_id": 0, "name": "Home"}])
        ],
        devices=devices,
        groups=[
            ImportedGroup(
                group_id=item["group_id"],
                name=item["name"],
                ble_category=item.get("ble_category", ""),
                room_id=item.get("room_id"),
                room_name=item.get("room_name", ""),
                member_ids=item.get("member_ids", []),
            )
            for item in data.get(CONF_GROUPS, [])
        ],
        scenes=[
            ImportedScene(
                scene_id=item["scene_id"],
                name=item["name"],
                room_id=item.get("room_id"),
                room_name=item.get("room_name", ""),
                module_devices=item.get("module_devices", []),
            )
            for item in data.get(CONF_SCENES, [])
        ],
        virtual_subtokens=[
            VirtualSubToken(
                did=item["did"],
                pid=item["pid"],
                token=item["token"],
                type=item.get("type", ""),
            )
            for item in data.get(CONF_VIRTUAL_SUBTOKENS, [])
        ],
    )


def gateways_from_entry_data(data: dict[str, Any]) -> list[DiscoveredRMMax]:
    """Reconstruct discovered gateways from a config entry."""
    return [
        DiscoveredRMMax(
            host=item["host"],
            mac=item["mac"],
            devtype=item["devtype"],
            name=item.get("name", ""),
            locked=item.get("locked", False),
            port=item.get("port", 80),
        )
        for item in data.get(CONF_GATEWAYS, [])
    ]


def gateways_to_entry_data(
    gateways: list[DiscoveredRMMax],
) -> list[dict[str, Any]]:
    """Serialize known gateway endpoints."""
    return [
        {
            "host": gateway.host,
            "mac": gateway.mac,
            "devtype": gateway.devtype,
            "name": gateway.name,
            "locked": gateway.locked,
            "port": gateway.port,
        }
        for gateway in gateways
    ]
