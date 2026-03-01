from pydantic import BaseModel


class Finding(BaseModel):
    datetime: str | None = None
    content: str
    category: str


class ExtractorMetadata(BaseModel):
    total_source_rows: int
    findings_extracted: int
    date_range: str


class ExtractorOutput(BaseModel):
    sheet_name: str
    extraction_datetime: str
    findings: list[Finding]
    metadata: ExtractorMetadata


class ReconciledFinding(BaseModel):
    datetime: str | None = None
    content: str
    sources: list[str]
    resolution_note: str | None = None


class ConflictResolution(BaseModel):
    description: str
    sources: list[str]
    resolution: str


class InterpreterMetadata(BaseModel):
    total_input_findings: int
    total_output_findings: int


class InterpreterOutput(BaseModel):
    reconciled_findings: list[ReconciledFinding]
    conflicts_resolved: list[ConflictResolution]
    duplicates_removed: int
    metadata: InterpreterMetadata


class ValidatorOutput(BaseModel):
    validated_findings: list[ReconciledFinding]
    missing_findings: list[dict]
    unresolved_conflicts: list[dict]
    metadata: dict


class GeneratorOutput(BaseModel):
    summary: str
    metadata: dict
