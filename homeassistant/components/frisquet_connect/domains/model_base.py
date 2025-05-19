# TODO : Use Pydantic for data validation
class ModelBase:
    def __init__(self, response_json: dict):
        if response_json is None:
            raise ValueError("The response JSON must not be None")

        for key, value in response_json.items():
            attr_name = f"_{key}"
            setattr(self, attr_name, value)
