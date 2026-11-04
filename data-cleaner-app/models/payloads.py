from pydantic import BaseModel, Field
from typing import Dict

class ColumnMappingPayload(BaseModel):
    mapping: Dict[str, str]
    report_name: str = Field(default="", max_length=18)
