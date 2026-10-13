"""Barcode discovery data."""

from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class BarcodeServiceInfo(BaseServiceInfo):
    """Prepared info from a scanned or manually entered barcode."""

    data: str
    # Barcode Detection API format (e.g. "qr_code"), None when entered manually
    format: str | None = None
