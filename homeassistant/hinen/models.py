"""Models for Hinen Open API."""

from pydantic import BaseModel, Field


class HinenDeviceInfo(BaseModel):
    """设备详细信息模型."""

    id: str = Field(..., description="设备唯一ID")
    device_name: str = Field(..., alias="deviceName", description="设备名称")
    product_id: str = Field(..., alias="productId", description="产品ID")
    product_name: str = Field(..., alias="productName", description="产品名称")
    serial_number: str = Field(..., alias="serialNumber", description="序列号")
    firmware_version: str = Field(..., alias="firmwareVersion", description="固件版本")
    status: int = Field(..., description="设备状态 (0-离线, 1-在线)")
    model_code: str = Field(..., alias="modelCode", description="型号代码")
    accessory_type: int = Field(..., alias="accessoryType", description="配件类型")
    product_type: int = Field(..., alias="productType", description="产品类型")
    alert_status: int = Field(
        ..., alias="alertStatus", description="告警状态 (0-正常, 1-告警)"
    )
    img_url: str = Field(..., alias="imgUrl", description="设备图片URL")
    ota_status: int = Field(
        ..., alias="otaStatus", description="OTA升级状态 (0-无更新, 1-有更新)"
    )
    time_zone: int = Field(..., alias="timeZone", description="设备时区")

    # 时间戳转换
    create_time: str = Field(..., alias="createTime", description="创建时间")
    update_time: str = Field(..., alias="updateTime", description="更新时间")

    # @property
    # def upload_playlist_id(self) -> str:
    #     """Return playlist id with uploads from channel."""
    #     return str(self.channel_id).replace("UC", "UU", 1)

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


class HinenDeviceDetail(BaseModel):
    """简化设备数据模型."""

    id: str = Field(..., description="设备唯一ID")
    device_name: str = Field(..., alias="deviceName", description="设备名称")
    product_id: str = Field(..., alias="productId", description="产品ID")
    product_name: str = Field(..., alias="productName", description="产品名称")
    serial_number: str = Field(..., alias="serialNumber", description="序列号")
    status: int = Field(..., description="设备状态 (0-离线, 1-在线)")
    alert_status: int = Field(
        ..., alias="alertStatus", description="告警状态 (0-正常, 1-告警)"
    )
