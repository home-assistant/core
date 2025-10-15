"""DayBetter Certificate Manager

Used for handling DayBetter light certificate file reading and parsing
"""

import base64
import logging
import os
import struct
import tempfile
import traceback

_LOGGER = logging.getLogger(__name__)


class CertManager:
    """Handles parsing and management of device certificates."""

    def __init__(self, file_path: str | None = None):
        """Initialize CertManager.

        Args:
            file_path: Path to binary certificate file
        """
        self.file_path = file_path
        self.extracted_data = None

    def clean_data(self, data: bytes) -> bytes:
        """Clean data, remove whitespace and invalid bytes."""
        if not data:
            return b""

        # For certificate and key data, only remove leading/trailing null bytes and whitespace
        # Don't filter binary data
        cleaned = data.strip(b"\x00 \t\n\r")

        # If no data after cleaning, return original data
        if not cleaned:
            return data

        return cleaned

    def find_next_zero_byte(self, content: bytes, start_pos: int) -> int | None:
        """Find the next zero byte position in content starting from start_pos."""
        try:
            return content.index(b"\x00", start_pos)
        except ValueError:
            return None

    def _parse_binary_data(self, content: bytes) -> list[bytes | str] | None:
        if not content:
            _LOGGER.error("Certificate content is empty")
            return None

        _LOGGER.debug(
            "Starting to parse certificate data, total length: %d bytes", len(content)
        )
        extracted_parts = []
        current_pos = 0

        try:
            # Part 1: Client ID (1 byte length + data + 1 byte terminator)
            if current_pos >= len(content):
                _LOGGER.error("Position out of content length when parsing Client ID")
                return None

            # Read 1 byte length
            length_byte = content[current_pos]
            _LOGGER.debug("Client ID length: %d", length_byte)

            # Check if data length is reasonable
            if current_pos + 1 + length_byte > len(content):
                _LOGGER.error("Client ID data length out of content range")
                return None

            # Extract data (excluding terminator)
            client_id_data = content[
                current_pos + 1 : current_pos + 1 + length_byte - 1
            ]
            client_id = self.clean_data(client_id_data)
            _LOGGER.debug(
                "Client ID: %s",
                client_id.decode("utf-8", errors="replace")
                if isinstance(client_id, bytes)
                else client_id,
            )
            extracted_parts.append(client_id)

            # Move to next part (skip terminator)
            current_pos += 1 + length_byte

            # Part 2: Client certificate (2 bytes length + data + 1 byte terminator)
            if current_pos + 2 > len(content):
                _LOGGER.error(
                    "Position out of content length when parsing client certificate"
                )
                return None

            # Read 2 bytes length (little-endian)
            cert_length = struct.unpack("<H", content[current_pos : current_pos + 2])[0]
            _LOGGER.debug("Client certificate length: %d", cert_length)

            # Check if data length is reasonable
            if current_pos + 2 + cert_length > len(content):
                _LOGGER.error("Client certificate data length out of content range")
                return None

            # Extract data (excluding terminator)
            cert_data = content[current_pos + 2 : current_pos + 2 + cert_length - 1]
            client_cert = self.clean_data(cert_data)
            extracted_parts.append(client_cert)

            # Move to next part (skip terminator)
            current_pos += 2 + cert_length

            # Part 3: Client key (2 bytes length + data + 1 byte terminator)
            if current_pos + 2 > len(content):
                _LOGGER.error("Position out of content length when parsing client key")
                return None

            # Read 2 bytes length (little-endian)
            key_length = struct.unpack("<H", content[current_pos : current_pos + 2])[0]
            _LOGGER.debug("Client key length: %d", key_length)

            # Check if data length is reasonable
            if current_pos + 2 + key_length > len(content):
                _LOGGER.error("Client key data length out of content range")
                return None

            # Extract data (excluding terminator)
            key_data = content[current_pos + 2 : current_pos + 2 + key_length - 1]
            client_key = self.clean_data(key_data)
            extracted_parts.append(client_key)

            # Move to next part (skip terminator)
            current_pos += 2 + key_length

            # Part 4: CA certificate (2 bytes length + data + 1 byte terminator)
            if current_pos + 2 > len(content):
                _LOGGER.error(
                    "Position out of content length when parsing CA certificate"
                )
                return None

            # Read 2 bytes length (little-endian)
            ca_length = struct.unpack("<H", content[current_pos : current_pos + 2])[0]
            _LOGGER.debug("CA certificate length: %d", ca_length)

            # Check if data length is reasonable
            if current_pos + 2 + ca_length > len(content):
                _LOGGER.error("CA certificate data length out of content range")
                return None

            # Extract data (excluding terminator)
            ca_data = content[current_pos + 2 : current_pos + 2 + ca_length - 1]
            ca_cert = self.clean_data(ca_data)
            extracted_parts.append(ca_cert)

            # Move to next part (skip terminator)
            current_pos += 2 + ca_length

            # Part 5: Broker address (1 byte length + data + 1 byte terminator)
            if current_pos >= len(content):
                _LOGGER.error(
                    "Position out of content length when parsing Broker address"
                )
                return None

            # Read 1 byte length
            broker_length = content[current_pos]
            _LOGGER.debug("Broker address length: %d", broker_length)

            # Check if data length is reasonable
            if current_pos + 1 + broker_length > len(content):
                _LOGGER.error("Broker address data length out of content range")
                return None

            # Extract data (excluding terminator)
            broker_data = content[current_pos + 1 : current_pos + 1 + broker_length - 1]
            broker_address = self.clean_data(broker_data)

            # Remove leading slash from broker address (if present)
            if isinstance(broker_address, bytes):
                broker_str = broker_address.decode("utf-8", errors="replace")
                broker_str = broker_str.removeprefix("/")
                broker_address = broker_str.encode("utf-8")
            elif isinstance(broker_address, str) and broker_address.startswith("/"):
                broker_address = broker_address[1:]

            _LOGGER.debug(
                "Broker address: %s",
                broker_address.decode("utf-8", errors="replace")
                if isinstance(broker_address, bytes)
                else broker_address,
            )
            extracted_parts.append(broker_address)

            # Move to next part (skip terminator)
            current_pos += 1 + broker_length

            # Part 6: Padding data (not processed, skipped)
            if current_pos < len(content):
                remaining_length = len(content) - current_pos
                _LOGGER.debug(
                    "Skipping padding data, length: %d bytes", remaining_length
                )

            self.extracted_data = extracted_parts
            return self.extracted_data

        except Exception as e:
            _LOGGER.error("Error parsing certificate data: %s", str(e))
            print(traceback.format_exc(), flush=True)
            return None

    def read_bin_file(self) -> list[bytes | str] | None:
        """Read and parse binary certificate file using length+data+end format.

        File format:
        - Part 1: Client ID (1 byte length + data + null terminator)
        - Part 2: Client Certificate (2 bytes length LE + data + null terminator)
        - Part 3: Client Key (2 bytes length LE + data + null terminator)
        - Part 4: CA Certificate (2 bytes length LE + data + null terminator)
        - Part 5: Broker Address (null-terminated string)
        - Part 6: Reserved/Additional data (remaining content)
        """
        if not self.file_path or not os.path.exists(self.file_path):
            return None

        try:
            with open(self.file_path, "rb") as f:
                content = f.read()

            return self._parse_binary_data(content)

        except Exception:
            print(traceback.format_exc(), flush=True)
            return None

    def save_extracted_data(
        self,
        extracted_data: list[str | bytes] | None = None,
        base_path: str | None = None,
    ) -> str | None:
        """Save extracted data to files.

        Args:
            extracted_data: List of extracted data [client_id, client_cert, client_key, ca_cert, broker_address, additional_data]
                           If not provided, uses self.extracted_data
            base_path: Path to directory where files should be saved
                      If not provided, creates a temporary directory

        Returns:
            str: Path to directory where files were saved, or None if failed
        """
        # Determine which data to use
        data_to_save = (
            extracted_data if extracted_data is not None else self.extracted_data
        )

        if not data_to_save:
            _LOGGER.error("No extracted data to save")
            return None

        try:
            # Use provided base path or create temporary directory
            if base_path:
                save_dir = base_path
                os.makedirs(save_dir, exist_ok=True)
            else:
                save_dir = tempfile.mkdtemp()

            # Define filenames for each part (excluding additional_data.bin)
            filenames = [
                "client_id.txt",
                "client_cert.crt",
                "client_key.key",
                "ca_cert.crt",
                "broker_address.txt",
            ]

            # Save each part to a file
            for i, (data, filename) in enumerate(
                zip(data_to_save, filenames, strict=False)
            ):
                file_path = os.path.join(save_dir, filename)

                # Handle data conversion if needed
                if isinstance(data, str):
                    # If data is a string, encode as UTF-8
                    binary_data = data.encode("utf-8")
                else:
                    # Data is already bytes - use it directly
                    binary_data = data

                # Special handling for broker address, remove leading slash
                if filename == "broker_address.txt":
                    try:
                        broker_str = binary_data.decode("utf-8", errors="replace")
                        broker_str = broker_str.removeprefix("/")
                        binary_data = broker_str.encode("utf-8")
                    except Exception:
                        # If decoding fails, keep original data
                        pass

                # Check if certificate data needs Base64 decode
                if filename.endswith(".crt"):
                    try:
                        # Attempt Base64 decode
                        decoded_data = base64.b64decode(binary_data)
                        binary_data = decoded_data
                    except Exception:
                        # If not Base64 encoded, use raw data directly
                        pass

                # Ensure certificate file has correct PEM format
                if filename.endswith(".crt"):
                    # Check if PEM header/footer tags already exist
                    try:
                        cert_text = binary_data.decode("utf-8", errors="strict")
                        if "-----BEGIN CERTIFICATE-----" not in cert_text:
                            # Add PEM header/footer tags
                            cert_with_headers = f"-----BEGIN CERTIFICATE-----\n{cert_text}\n-----END CERTIFICATE-----\n"
                            binary_data = cert_with_headers.encode("utf-8")
                        else:
                            # Use raw binary data to avoid encoding issues
                            binary_data = binary_data
                    except UnicodeDecodeError:
                        # If unable to decode as UTF-8, it may be binary certificate data
                        pass

                # Ensure key file has correct PEM format
                if filename.endswith(".key"):
                    # Check if PEM header/footer tags already exist
                    try:
                        key_text = binary_data.decode("utf-8", errors="strict")
                        if "-----BEGIN" not in key_text:
                            # Add PEM header/footer tags (based on key type)
                            if "RSA" in key_text or "PRIVATE" in key_text:
                                key_with_headers = f"-----BEGIN RSA PRIVATE KEY-----\n{key_text}\n-----END RSA PRIVATE KEY-----\n"
                            else:
                                key_with_headers = f"-----BEGIN PRIVATE KEY-----\n{key_text}\n-----END PRIVATE KEY-----\n"
                            binary_data = key_with_headers.encode("utf-8")
                        else:
                            # Already in PEM format, use directly
                            binary_data = binary_data
                    except UnicodeDecodeError:
                        # If unable to decode as UTF-8, it may be binary key data
                        pass

                # Write binary data to file (this will be called from thread pool)
                with open(file_path, "wb") as f:
                    f.write(binary_data)

            return save_dir

        except Exception:
            print(traceback.format_exc(), flush=True)
            return None

    def get_client_id(self) -> bytes | None:
        """Get Client ID."""
        if not self.extracted_data or len(self.extracted_data) < 1:
            return None

        return self.extracted_data[0]

    def get_client_cert(self) -> bytes | None:
        """Get Client Certificate."""
        if not self.extracted_data or len(self.extracted_data) < 2:
            return None

        return self.extracted_data[1]

    def get_client_key(self) -> bytes | None:
        """Get Client Key."""
        if not self.extracted_data or len(self.extracted_data) < 3:
            return None

        return self.extracted_data[2]

    def get_ca_cert(self) -> bytes | None:
        """Get CA Certificate."""
        if not self.extracted_data or len(self.extracted_data) < 4:
            return None

        return self.extracted_data[3]

    def get_broker_address(self) -> bytes | None:
        """Get Broker Address."""
        if not self.extracted_data or len(self.extracted_data) < 5:
            return None

        return self.extracted_data[4]

    def get_cert_files(self, base_path=None):
        """Get all certificate file paths from extracted data

        Args:
            base_path: Base path for certificate file saving

        Returns:
            dict: Dictionary containing all certificate file paths
        """
        try:
            # First extract data
            self.read_bin_file()

            # Save extracted data to file
            save_dir = self.save_extracted_data(base_path)

            if not save_dir:
                return None

            # Build dictionary of returned file paths
            cert_files = {
                "client_id": os.path.join(save_dir, "client_id.txt"),
                "client_cert": os.path.join(save_dir, "client_cert.crt"),
                "client_key": os.path.join(save_dir, "client_key.key"),
                "ca_cert": os.path.join(save_dir, "ca_cert.crt"),
                "broker_address": os.path.join(save_dir, "broker_address.txt"),
            }

            # Verify all files have been created
            missing_files = []
            for key, file_path in cert_files.items():
                if not os.path.exists(file_path):
                    missing_files.append(key)

            if missing_files:
                return None

            return cert_files

        except Exception:
            print(traceback.format_exc(), flush=True)
            return None
