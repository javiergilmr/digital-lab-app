from pydantic import BaseModel
from typing import Dict

class ColumnMappingPayload(BaseModel):
    mapping: Dict[str, str]
