"""Tests for Glances."""

from typing import Any

MOCK_USER_INPUT: dict[str, Any] = {
    "host": "0.0.0.0",
    "username": "username",
    "password": "password",
    "port": 61208,
    "ssl": False,
    "verify_ssl": True,
}

MOCK_DATA = {
    "cpu": {
        "total": 10.6,
        "user": 7.6,
        "system": 2.1,
        "idle": 88.8,
        "nice": 0.0,
        "iowait": 0.6,
    },
    "diskio": [
        {
            "time_since_update": 1,
            "disk_name": "nvme0n1",
            "read_count": 12,
            "write_count": 466,
            "read_bytes": 184320,
            "write_bytes": 23863296,
            "key": "disk_name",
        },
    ],
    "docker": {
        "containers": [
            {
                "key": "name",
                "name": "container1",
                "Status": "running",
                "cpu": {"total": 50.94973493230174},
                "cpu_percent": 50.94973493230174,
                "memory": {
                    "usage": 1120321536,
                    "limit": 3976318976,
                    "rss": 480641024,
                    "cache": 580915200,
                    "max_usage": 1309597696,
                },
                "memory_usage": 539406336,
            },
            {
                "key": "name",
                "name": "container2",
                "Status": "running",
                "cpu": {"total": 26.23567931034483},
                "cpu_percent": 26.23567931034483,
                "memory": {
                    "usage": 85139456,
                    "limit": 3976318976,
                    "rss": 33677312,
                    "cache": 35012608,
                    "max_usage": 87650304,
                },
                "memory_usage": 50126848,
            },
        ]
    },
    "fs": [
        {
            "device_name": "/dev/sda8",
            "fs_type": "ext4",
            "mnt_point": "/ssl",
            "size": 511320748032,
            "used": 32910458880,
            "free": 457917374464,
            "percent": 6.7,
            "key": "mnt_point",
        },
        {
            "device_name": "/dev/sda8",
            "fs_type": "ext4",
            "mnt_point": "/media",
            "size": 511320748032,
            "used": 32910458880,
            "free": 457917374464,
            "percent": 6.7,
            "key": "mnt_point",
        },
    ],
    "mem": {
        "total": 3976318976,
        "available": 2878337024,
        "percent": 27.6,
        "used": 1097981952,
        "free": 2878337024,
        "active": 567971840,
        "inactive": 1679704064,
        "buffers": 149807104,
        "cached": 1334816768,
        "shared": 1499136,
    },
    "sensors": [
        {
            "label": "cpu_thermal 1",
            "value": 59,
            "warning": None,
            "critical": None,
            "unit": "C",
            "type": "temperature_core",
            "key": "label",
        },
        {
            "label": "err_temp",
            "value": "ERR",
            "warning": None,
            "critical": None,
            "unit": "C",
            "type": "temperature_hdd",
            "key": "label",
        },
        {
            "label": "na_temp",
            "value": "NA",
            "warning": None,
            "critical": None,
            "unit": "C",
            "type": "temperature_hdd",
            "key": "label",
        },
    ],
    "system": {
        "os_name": "Linux",
        "hostname": "fedora-35",
        "platform": "64bit",
        "linux_distro": "Fedora Linux 35",
        "os_version": "5.15.6-200.fc35.x86_64",
        "hr_name": "Fedora Linux 35 64bit",
    },
    "raid": {
        "md3": {
            "status": "active",
            "type": "raid1",
            "components": {"sdh1": "2", "sdi1": "0"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
        "md1": {
            "status": "active",
            "type": "raid1",
            "components": {"sdg": "0", "sde": "1"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
        "md4": {
            "status": "active",
            "type": "raid1",
            "components": {"sdf1": "1", "sdb1": "0"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
        "md0": {
            "status": "active",
            "type": "raid1",
            "components": {"sdc": "2", "sdd": "3"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
    },
    "uptime": "3 days, 10:25:20",
}

HA_SENSOR_DATA: dict[str, Any] = {
    "fs": {
        "/ssl": {"disk_use": 30.7, "disk_use_percent": 6.7, "disk_free": 426.5},
        "/media": {"disk_use": 30.7, "disk_use_percent": 6.7, "disk_free": 426.5},
    },
    "sensors": {
        "cpu_thermal 1": {"temperature_core": 59},
        "err_temp": {"temperature_hdd": "unavailable"},
        "na_temp": {"temperature_hdd": "unavailable"},
    },
    "mem": {
        "memory_use_percent": 27.6,
        "memory_use": 1047.1,
        "memory_free": 2745.0,
    },
    "docker": {"docker_active": 2, "docker_cpu_use": 77.2, "docker_memory_use": 1149.6},
    "raid": {
        "md3": {
            "status": "active",
            "type": "raid1",
            "components": {"sdh1": "2", "sdi1": "0"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
        "md1": {
            "status": "active",
            "type": "raid1",
            "components": {"sdg": "0", "sde": "1"},
            "available": "2",
            "used": "2",
            "config": "UU",
        },
    },
}
