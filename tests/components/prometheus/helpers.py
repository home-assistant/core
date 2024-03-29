"""Helper methods for prometheus tests."""


class MetricsTestHelper:
    """Helps with formatting prometheus metrics and future-proof label changes."""

    @classmethod
    def get_device_class_label_line(cls, device_class):
        """Format the device_class label line (tries to account for enum class)."""
        if device_class:
            device_class = str(device_class)
        return f'device_class="{device_class or ""}",'

    @classmethod
    def _get_metric_string(
        cls,
        metric_name,
        domain,
        friendly_name,
        object_id,
        metric_value=None,
        area=None,
        device_class=None,
    ):
        device_class_label_line = cls.get_device_class_label_line(device_class)
        final_metric_value = f" {metric_value}" if metric_value else ""
        full_metric_string = (
            f"{metric_name}{{"
            f'area="{area or ""}",'
            f"{device_class_label_line}"
            f'domain="{domain}",'
            f'entity="{domain}.{object_id}",'
            f'friendly_name="{friendly_name}",'
            f'object_id="{object_id}"'
            f"}}{final_metric_value}"
        )
        return full_metric_string

    @classmethod
    def _perform_metric_assert(
        cls,
        metric_name,
        metric_value,
        domain,
        friendly_name,
        object_id,
        body,
        area=None,
        device_class=None,
        positive_comparison=True,
    ):
        full_metric_string = cls._get_metric_string(
            metric_name,
            domain,
            friendly_name,
            object_id,
            area=area,
            device_class=device_class,
            metric_value=metric_value,
        )
        if positive_comparison:
            assert full_metric_string in body
        else:
            assert full_metric_string not in body

    @classmethod
    def _perform_sensor_metric_assert(
        cls,
        metric_name,
        metric_value,
        friendly_name,
        object_id,
        body,
        area=None,
        device_class=None,
        positive_comparison=True,
    ):
        cls._perform_metric_assert(
            metric_name,
            metric_value,
            "sensor",
            friendly_name,
            object_id,
            body,
            area=area,
            device_class=device_class,
            positive_comparison=positive_comparison,
        )

    @classmethod
    def _perform_climate_metric_assert(
        cls,
        metric_name,
        metric_value,
        friendly_name,
        object_id,
        body,
        area=None,
        device_class=None,
        action=None,
    ):
        domain = "climate"
        device_class_label_line = cls.get_device_class_label_line(device_class)
        action_label_line = f'action="{action}",' if action else ""
        assert (
            f"{metric_name}{{"
            f'{action_label_line}'
            f'area="{area or ""}",'
            f"{device_class_label_line}"
            f'domain="{domain}",'
            f'entity="{domain}.{object_id}",'
            f'friendly_name="{friendly_name}",'
            f'object_id="{object_id}"'
            f"}} {metric_value}" in body
        )

    @classmethod
    def _perform_cover_metric_assert(
        cls,
        metric_name,
        metric_value,
        entity_id,
        friendly_name,
        body,
        area=None,
        device_class=None,
        state=None,
    ):
        domain = "cover"
        device_class_label_line = cls.get_device_class_label_line(device_class)
        object_id = entity_id.replace(f"{domain}.", "")
        state_label_line = f',state="{state}"' if state else ""
        assert (
            f"{metric_name}{{"
            f'area="{area or ""}",'
            f"{device_class_label_line}"
            f'domain="{domain}",'
            f'entity="{entity_id}",'
            f'friendly_name="{friendly_name}",'
            f'object_id="{object_id}"'
            f'{state_label_line}'
            f"}} {metric_value}" in body
        )

    @classmethod
    def _perform_humidifier_metric_assert(
        cls,
        metric_name,
        metric_value,
        friendly_name,
        object_id,
        body,
        area=None,
        device_class=None,
        mode=None,
    ):
        domain = "humidifier"
        device_class_label_line = cls.get_device_class_label_line(device_class)
        mode_label_line = f'mode="{mode}",' if mode else ""
        assert (
            f"{metric_name}{{"
            f'area="{area or ""}",'
            f"{device_class_label_line}"
            f'domain="{domain}",'
            f'entity="{domain}.{object_id}",'
            f'friendly_name="{friendly_name}",'
            f'{mode_label_line}'
            f'object_id="{object_id}"'
            f"}} {metric_value}" in body
        )
