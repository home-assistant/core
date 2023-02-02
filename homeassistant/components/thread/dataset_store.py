"""Persistently store thread datasets."""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, uuid as uuid_util

from . import tlv_parser
from .const import DOMAIN

DATA_STORE = "datasets"
STORAGE_KEY = "thread.datasets"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 1
SAVE_DELAY = 10


@dataclasses.dataclass(frozen=True)
class DatasetEntry:
    """Dataset store entry."""

    preferred: bool
    source: str
    tlv: str

    created: datetime = dataclasses.field(default_factory=dt_util.utcnow)
    id: str = dataclasses.field(default_factory=uuid_util.random_uuid_hex)

    @property
    def extended_pan_id(self) -> str | None:
        """Return extended PAN ID as a hex string."""
        dataset = tlv_parser.parse_tlv(self.tlv)
        return dataset.get(tlv_parser.MeshcopTLVType.EXTPANID)

    @property
    def network_name(self) -> str | None:
        """Return network name as a string."""
        dataset = tlv_parser.parse_tlv(self.tlv)
        return dataset.get(tlv_parser.MeshcopTLVType.NETWORKNAME)

    @property
    def pan_id(self) -> str | None:
        """Return PAN ID as a hex string."""
        dataset = tlv_parser.parse_tlv(self.tlv)
        return dataset.get(tlv_parser.MeshcopTLVType.PANID)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "created": self.created.isoformat(),
            "id": self.id,
            "preferred": self.preferred,
            "source": self.source,
            "tlv": self.tlv,
        }


class DatasetStore:
    """Class to hold a collection of thread datasets."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dataset store."""
        self.hass = hass
        self.datasets: dict[str, DatasetEntry] = {}
        self._store: Store[dict[str, list[dict[str, Any]]]] = Store(
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
        tlv_parser.parse_tlv(tlv)
        # Bail out if the dataset already exists
        if any(dataset for dataset in self.datasets.values() if dataset.tlv == tlv):
            return

        # Set to preferred if this is the first dataset
        preferred = not bool(self.datasets)
        dataset = DatasetEntry(preferred=preferred, source=source, tlv=tlv)
        self.datasets[dataset.id] = dataset
        self.async_schedule_save()

    @callback
    def async_delete(self, dataset_id: str) -> None:
        """Delete dataset."""
        if not (dataset := self.datasets.get(dataset_id)):
            return
        if dataset.preferred:
            raise HomeAssistantError("attempt to remove preferred dataset")
        del self.datasets[dataset_id]
        self.async_schedule_save()

    @callback
    def async_get(self, dataset_id: str) -> DatasetEntry | None:
        """Get dataset by id."""
        return self.datasets.get(dataset_id)

    async def async_load(self) -> None:
        """Load the datasets."""
        data = await self._store.async_load()

        datasets: dict[str, DatasetEntry] = {}

        if isinstance(data, dict):
            for dataset in data["datasets"]:
                created = cast(datetime, dt_util.parse_datetime(dataset["created"]))
                datasets[dataset["id"]] = DatasetEntry(
                    created=created,
                    id=dataset["id"],
                    preferred=dataset["preferred"],
                    source=dataset["source"],
                    tlv=dataset["tlv"],
                )

        self.datasets = datasets

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the dataset store."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of datasets to store in a file."""
        data = {}
        data["datasets"] = [dataset.to_json() for dataset in self.datasets.values()]
        return data


@callback
def async_get(hass: HomeAssistant) -> DatasetStore:
    """Get the dataset store."""
    return cast(DatasetStore, hass.data[DOMAIN][DATA_STORE])


async def async_load(hass: HomeAssistant) -> None:
    """Load dataset store."""
    assert DATA_STORE not in hass.data[DOMAIN]
    hass.data[DOMAIN][DATA_STORE] = DatasetStore(hass)
    await hass.data[DOMAIN][DATA_STORE].async_load()
