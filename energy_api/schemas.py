from pydantic import BaseModel


class SensorConfigUpdate(BaseModel):
    sensor_number: int
    custom_label: str
    appliance_category: str
