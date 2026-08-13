"""Definitions for TrueNAS button entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

from homeassistant.components.button import ButtonEntityDescription

from .const import (
    API_CLOUDSYNC_SYNC,
    API_CRONJOB_RUN,
    API_REPLICATION_RUN,
    API_RSYNCTASK_RUN,
    API_SNAPSHOTTASK_RUN,
)
from .entity import TrueNASEntityDescription

# Run buttons mirror the on-demand "*_run" actions, but as one-tap controls on the
# task's device page. Each carries the JSON-RPC method to call with the object id.


@dataclass(frozen=True, kw_only=True)
class TrueNASButtonEntityDescription(ButtonEntityDescription, TrueNASEntityDescription):
    """Class describing TrueNAS button entities."""

    api_method: str | None = None
    func: str = "TrueNASButton"


SENSOR_TYPES: tuple[TrueNASButtonEntityDescription, ...] = (
    TrueNASButtonEntityDescription(
        key="snapshottask_run",
        translation_key="snapshottask_run",
        api_method=API_SNAPSHOTTASK_RUN,
        ha_group="Snapshot tasks",
        data_path="snapshottask",
        data_name="dataset",
        data_uid=None,
        data_reference="id",
    ),
    TrueNASButtonEntityDescription(
        key="rsync_run",
        translation_key="rsync_run",
        api_method=API_RSYNCTASK_RUN,
        ha_group="Rsync tasks",
        data_path="rsynctask",
        data_name="desc",
        data_uid=None,
        data_reference="id",
    ),
    TrueNASButtonEntityDescription(
        key="replication_run",
        translation_key="replication_run",
        api_method=API_REPLICATION_RUN,
        ha_group="Replication",
        data_path="replication",
        data_name="name",
        data_uid=None,
        data_reference="id",
    ),
    TrueNASButtonEntityDescription(
        key="cloudsync_run",
        translation_key="cloudsync_run",
        api_method=API_CLOUDSYNC_SYNC,
        ha_group="Cloudsync",
        data_path="cloudsync",
        data_name="description",
        data_uid=None,
        data_reference="id",
    ),
    TrueNASButtonEntityDescription(
        key="cronjob_run",
        translation_key="cronjob_run",
        api_method=API_CRONJOB_RUN,
        ha_group="Cron Jobs",
        data_path="cronjob",
        data_name="display_name",
        data_uid=None,
        data_reference="id",
    ),
    TrueNASButtonEntityDescription(
        key="scrub_run",
        translation_key="scrub_run",
        ha_group="Pools",
        data_path="scrub",
        data_name="pool_name",
        data_uid=None,
        data_reference="id",
        func="TrueNASPoolScrubButton",
    ),
)


class ButtonService(NamedTuple):
    """Service definition."""

    name: str
    schema: Any
    action: str


SENSOR_SERVICES: tuple[ButtonService, ...] = ()
