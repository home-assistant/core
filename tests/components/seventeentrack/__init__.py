"""Tests for the seventeentrack component."""

from py17track.package import Package

SUMMARY = {
    "Not Found": 0,
    "In Transit": 1,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 1,
    "Delivered": 0,
    "Returned": 0,
}

PACKAGES = [
    Package(
        "456",
        206,
        "friendly name 1",
        "info text 1",
        "location 1",
        "2020-08-10 10:32",
        status=10,
    )
]
ARCHIVED_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 1,
    "Ready to be Picked Up": 0,
    "Undelivered": 1,
    "Delivered": 0,
    "Returned": 0,
}

ARCHIVED_PACKAGES = [
    Package(
        "410",
        206,
        "friendly name 2",
        "info text 2",
        "location 2",
        "2020-07-10 10:32",
        status=20,
    )
]

TOTAL_SUMMARY = {
    "Not Found": 0,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 0,
    "Undelivered": 2,
    "Delivered": 0,
    "Returned": 0,
}
