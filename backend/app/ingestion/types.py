from dataclasses import dataclass, field

@dataclass
class PageResult:
    page_no: int
    text: str
    source: str                 # digital | ocr | spreadsheet | error
    ocr_confidence: float | None = None
    error: str | None = None
    meta: dict = field(default_factory=dict)