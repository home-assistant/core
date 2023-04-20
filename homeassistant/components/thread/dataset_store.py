"""Persistently store thread datasets."""
from __future__ import annotations

from contextlib import suppress
import dataclasses
from datetime import datetime
from functools import cached_property
from typing import Any, cast

from python_otbr_api import tlv_parser

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, ulid as ulid_util

DATA_STORE = "thread.datasets"
STORAGE_KEY = "thread.datasets"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 1
SAVE_DELAY = 10


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
        if (channel := self.dataset.get(tlv_parser.MeshcopTLVType.CHANNEL)) is None:
            return None
        with suppress(ValueError):
            return int(channel, 16)
        return None

    @cached_property
    def dataset(self) -> dict[tlv_parser.MeshcopTLVType, str]:
        """Return the dataset in dict format."""
        return tlv_parser.parse_tlv(self.tlv)

    @property
    def extended_pan_id(self) -> str | None:
        """Return extended PAN ID as a hex string."""
        return self.dataset.get(tlv_parser.MeshcopTLVType.EXTPANID)

    @property
    def network_name(self) -> str | None:
        """Return network name as a string."""
        return self.dataset.get(tlv_parser.MeshcopTLVType.NETWORKNAME)

    @property
    def pan_id(self) -> str | None:
        """Return PAN ID as a hex string."""
        return self.dataset.get(tlv_parser.MeshcopTLVType.PANID)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "created": self.created.isoformat(),
            "id": self.id,
            "source": self.source,
            "tlv": self.tlv,
        }


class DatasetStore:
    """Class to hold a collection of thread datasets."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dataset store."""
        self.hass = hass
        self.datasets: dict[str, DatasetEntry] = {}
        self._preferred_dataset: str | None = None
        self._store: Store[dict[str, Any]] = Store(
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
        # Bail out if the dataset already exists
        if any(entry for entry in self.datasets.values() if entry.dataset == dataset):
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
