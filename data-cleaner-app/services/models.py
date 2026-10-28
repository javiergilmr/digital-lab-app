from pydantic import BaseModel
from typing import Dict

class ColumnMapping(BaseModel):
    mapping: Dict[str, str]
