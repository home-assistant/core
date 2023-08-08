"""Persistently store thread datasets."""
from __future__ import annotations

import dataclasses
from datetime import datetime
import logging
from typing import Any, cast

from python_otbr_api import tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.backports.functools import cached_property
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, ulid as ulid_util

DATA_STORE = "thread.datasets"
STORAGE_KEY = "thread.datasets"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2
SAVE_DELAY = 10

_LOGGER = logging.getLogger(__name__)


class DatasetPreferredError(HomeAssistantError):
    """Raised when attempting to delete the preferred dataset."""


@dataclasses.dataclass(frozen=True)
class DatasetEntry:
    """Dataset store entry."""

    source: str
    tlv: str

    created: datetime = dataclasses.field(default_factory=dt_util.utcnow)
    id: str = dataclasses.field(default_factory=ulid_util.ulid)

    @property
    def channel(self) -> int | None:
        """Return channel as an integer."""
        if (channel := self.dataset.get(MeshcopTLVType.CHANNEL)) is None:
            return None
        return cast(tlv_parser.Channel, channel).channel

    @cached_property
    def dataset(self) -> dict[MeshcopTLVType, tlv_parser.MeshcopTLVItem]:
        """Return the dataset in dict format."""
        return tlv_parser.parse_tlv(self.tlv)

    @property
    def extended_pan_id(self) -> str:
        """Return extended PAN ID as a hex string."""
        return str(self.dataset[MeshcopTLVType.EXTPANID])

    @property
    def network_name(self) -> str | None:
        """Return network name as a string."""
        if (name := self.dataset.get(MeshcopTLVType.NETWORKNAME)) is None:
            return None
        return cast(tlv_parser.NetworkName, name).name

    @property
    def pan_id(self) -> str | None:
        """Return PAN ID as a hex string."""
        return str(self.dataset.get(MeshcopTLVType.PANID))

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "created": self.created.isoformat(),
            "id": self.id,
            "source": self.source,
            "tlv": self.tlv,
        }


class DatasetStoreStore(Store):
    """Store Thread datasets."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1:
            if old_minor_version < 2:
                datasets: dict[str, DatasetEntry] = {}
                preferred_dataset = old_data["preferred_dataset"]

                for dataset in old_data["datasets"]:
                    created = cast(datetime, dt_util.parse_datetime(dataset["created"]))
                    entry = DatasetEntry(
                        created=created,
                        id=dataset["id"],
                        source=dataset["source"],
                        tlv=dataset["tlv"],
                    )
                    if (
                        MeshcopTLVType.EXTPANID not in entry.dataset
                        or MeshcopTLVType.ACTIVETIMESTAMP not in entry.dataset
                    ):
                        _LOGGER.warning(
                            "Dropped invalid Thread dataset '%s'", entry.tlv
                        )
                        if entry.id == preferred_dataset:
                            preferred_dataset = None
                        continue

                    if entry.extended_pan_id in datasets:
                        if datasets[entry.extended_pan_id].id == preferred_dataset:
                            _LOGGER.warning(
                                (
                                    "Dropped duplicated Thread dataset '%s' "
                                    "(duplicate of preferred dataset '%s')"
                                ),
                                entry.tlv,
                                datasets[entry.extended_pan_id].tlv,
                            )
                            continue
                        new_timestamp = cast(
                            tlv_parser.Timestamp,
                            entry.dataset[MeshcopTLVType.ACTIVETIMESTAMP],
                        )
                        old_timestamp = cast(
                            tlv_parser.Timestamp,
                            datasets[entry.extended_pan_id].dataset[
                                MeshcopTLVType.ACTIVETIMESTAMP
                            ],
                        )
                        if old_timestamp.seconds >= new_timestamp.seconds or (
                            old_timestamp.seconds == new_timestamp.seconds
                            and old_timestamp.ticks >= new_timestamp.ticks
                        ):
                            _LOGGER.warning(
                                (
                                    "Dropped duplicated Thread dataset '%s' "
                                    "(duplicate of '%s')"
                                ),
                                entry.tlv,
                                datasets[entry.extended_pan_id].tlv,
                            )
                            continue
                        _LOGGER.warning(
                            (
                                "Dropped duplicated Thread dataset '%s' "
                                "(duplicate of '%s')"
                            ),
                            datasets[entry.extended_pan_id].tlv,
                            entry.tlv,
                        )
                    datasets[entry.extended_pan_id] = entry
                data = {
                    "preferred_dataset": preferred_dataset,
                    "datasets": [dataset.to_json() for dataset in datasets.values()],
                }

        return data


class DatasetStore:
    """Class to hold a collection of thread datasets."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dataset store."""
        self.hass = hass
        self.datasets: dict[str, DatasetEntry] = {}
        self._preferred_dataset: str | None = None
        self._store: Store[dict[str, Any]] = DatasetStoreStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_add(self, source: str, tlv: str) -> None:
        """Add dataset, does nothing if it already exists."""
        # Make sure the tlv is valid
        dataset = tlv_parser.parse_tlv(tlv)

        # Don't allow adding a dataset which does not have an extended pan id or
        # timestamp
        if (
            MeshcopTLVType.EXTPANID not in dataset
            or MeshcopTLVType.ACTIVETIMESTAMP not in dataset
        ):
            raise HomeAssistantError("Invalid dataset")

        # Bail out if the dataset already exists
        if any(entry for entry in self.datasets.values() if entry.dataset == dataset):
            return

        # Update if dataset with same extended pan id exists and the timestamp
        # is newer
        if entry := next(
            (
                entry
                for entry in self.datasets.values()
                if entry.dataset[MeshcopTLVType.EXTPANID]
                == dataset[MeshcopTLVType.EXTPANID]
            ),
            None,
        ):
            new_timestamp = cast(
                tlv_parser.Timestamp, dataset[MeshcopTLVType.ACTIVETIMESTAMP]
            )
            old_timestamp = cast(
                tlv_parser.Timestamp,
                entry.dataset[MeshcopTLVType.ACTIVETIMESTAMP],
            )
            if old_timestamp.seconds >= new_timestamp.seconds or (
                old_timestamp.seconds == new_timestamp.seconds
                and old_timestamp.ticks >= new_timestamp.ticks
            ):
                _LOGGER.warning(
                    (
                        "Got dataset with same extended PAN ID and same or older active"
                        " timestamp, old dataset: '%s', new dataset: '%s'"
                    ),
                    entry.tlv,
                    tlv,
                )
                return
            _LOGGER.debug(
                (
                    "Updating dataset with same extended PAN ID and newer active "
                    "timestamp, old dataset: '%s', new dataset: '%s'"
                ),
                entry.tlv,
                tlv,
            )
            self.datasets[entry.id] = dataclasses.replace(
                self.datasets[entry.id], tlv=tlv
            )
            self.async_schedule_save()
            return

        entry = DatasetEntry(source=source, tlv=tlv)
        self.datasets[entry.id] = entry
        # Set to preferred if there is no preferred dataset
        if self._preferred_dataset is None:
            self._preferred_dataset = entry.id
        self.async_schedule_save()

    @callback
    def async_delete(self, dataset_id: str) -> None:
        """Delete dataset."""
        if self._preferred_dataset == dataset_id:
            raise DatasetPreferredError("attempt to remove preferred dataset")
        del self.datasets[dataset_id]
        self.async_schedule_save()

    @callback
    def async_get(self, dataset_id: str) -> DatasetEntry | None:
        """Get dataset by id."""
        return self.datasets.get(dataset_id)

    @property
    @callback
    def preferred_dataset(self) -> str | None:
        """Get the id of the preferred dataset."""
        return self._preferred_dataset

    @preferred_dataset.setter
    @callback
    def preferred_dataset(self, dataset_id: str) -> None:
        """Set the preferred dataset."""
        if dataset_id not in self.datasets:
            raise KeyError("unknown dataset")
        self._preferred_dataset = dataset_id
        self.async_schedule_save()

    async def async_load(self) -> None:
        """Load the datasets."""
        data = await self._store.async_load()

        datasets: dict[str, DatasetEntry] = {}
        preferred_dataset: str | None = None

        if data is not None:
            for dataset in data["datasets"]:
                created = cast(datetime, dt_util.parse_datetime(dataset["created"]))
                datasets[dataset["id"]] = DatasetEntry(
                    created=created,
                    id=dataset["id"],
                    source=dataset["source"],
                    tlv=dataset["tlv"],
                )
            preferred_dataset = data["preferred_dataset"]

        self.datasets = datasets
        self._preferred_dataset = preferred_dataset

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the dataset store."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of datasets to store in a file."""
        data: dict[str, Any] = {}
        data["datasets"] = [dataset.to_json() for dataset in self.datasets.values()]
        data["preferred_dataset"] = self._preferred_dataset
        return data


@singleton(DATA_STORE)
async def async_get_store(hass: HomeAssistant) -> DatasetStore:
    """Get the dataset store."""
    store = DatasetStore(hass)
    await store.async_load()
    return store


async def async_add_dataset(hass: HomeAssistant, source: str, tlv: str) -> None:
    """Add a dataset."""
    store = await async_get_store(hass)
    store.async_add(source, tlv)


async def async_get_dataset(hass: HomeAssistant, dataset_id: str) -> str | None:
    """Get a dataset."""
    store = await async_get_store(hass)
    if (entry := store.async_get(dataset_id)) is None:
        return None
    return entry.tlv


async def async_get_preferred_dataset(hass: HomeAssistant) -> str | None:
    """Get the preferred dataset."""
    store = await async_get_store(hass)
    if (preferred_dataset := store.preferred_dataset) is None or (
        entry := store.async_get(preferred_dataset)
    ) is None:
        return None
    return entry.tlv
