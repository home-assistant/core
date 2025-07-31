"""Models for Hinen Open API."""

from typing import Any

from pydantic import BaseModel, Field

from homeassistant.config_entries import ConfigEntry


class HinenDeviceInfo(BaseModel):
    """hinen device info."""

    id: str = Field(...)
    device_name: str = Field(..., alias="deviceName")
    serial_number: str = Field(..., alias="serialNumber")
    img_url: str = Field(..., alias="imgUrl")

    # 时间戳转换
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")

    @property
    def get_device_name(self) -> str:
        """Return device_name."""
        return self.device_name

    @property
    def get_id(self) -> str:
        """Return id."""
        return self.id

    # @property
    # def content_details(self) -> YouTubeChannelContentDetails:
    #     """Return content details."""
    #     if self.nullable_content_details is None:
    #         raise PartMissingError
    #     return self.nullable_content_details

    # @property
    # def statistics(self) -> YouTubeChannelStatistics:
    #     """Return statistics."""
    #     if self.nullable_statistics is None:
    #         raise PartMissingError
    #     return self.nullable_statistics


class HinenDeviceProperty(BaseModel):
    """hinen device property."""

    identifier: str = Field(..., description="property key")
    name: str = Field(..., description="name")
    value: Any = Field(..., description="value")


class HinenDeviceDetail(BaseModel):
    """hinen device detail."""

    id: str = Field(...)
    device_name: str = Field(..., alias="deviceName")
    serial_number: str = Field(..., alias="serialNumber")
    status: int = Field(...)
    alert_status: int = Field(..., alias="alertStatus")
    properties: list[HinenDeviceProperty] = Field(..., alias="properties")


class HinenDeviceControl(BaseModel):
    """hinen device control."""

    device_id: str = Field(..., alias="deviceId", description="设备ID")
    map: dict[str, Any] = Field(..., description="控制参数映射")

    class Config:
        """配置信息."""

        allow_population_by_field_name = True


class HinenClient(BaseModel):
    """hinen client."""

    name: str


type HinenIntegrationConfigEntry = ConfigEntry[HinenClient]
