from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PROMPTS_DIR = ROOT_DIR / "prompts"
OUTPUT_DIR = ROOT_DIR / "output"
EXTRACTIONS_DIR = OUTPUT_DIR / "extractions"
CACHE_DIR = ROOT_DIR / ".cache"

BASELINE_FILE = DATA_DIR / "Input_Baseline_P1.xlsx"
INPUT_DATA_FILE = DATA_DIR / "Input_Data_P1.xlsx"
OUTPUT_FRAMEWORK = [
    {"level_1": "Situation", "level_2": "Patient History", "level_3": "- 진단명 및 현병력 요약"},
    {"level_1": "Situation", "level_2": "Major Events", "level_3": "- 최근 3일간 주요 이벤트 요약"},
    {"level_1": "Situation", "level_2": "Status Changes", "level_3": "(임상 상태 변화 추이: 호전/악화/유지)"},
    {"level_1": "Assessments by Systems", "level_2": "Neurological", "level_3": "- 진정제 사용 및 섬망 사정 결과, 억제대 적용 여부"},
    {"level_1": "Assessments by Systems", "level_2": "Cardiovascular", "level_3": "- 승압제 사용 및 중단 여부, 비정상 심전도 리듬"},
    {"level_1": "Assessments by Systems", "level_2": "Respiratory", "level_3": "- 객담 양상 변화 등"},
    {"level_1": "Assessments by Systems", "level_2": "Gastrointestinal", "level_3": "- 영양 공급 방식 (TPN/NPO/경관영양) 등"},
    {"level_1": "Assessments by Systems", "level_2": "Other Systems", "level_3": "- 욕창/낙상 위험도 고위험군 결과 요약"},
    {"level_1": "Investigation", "level_2": "Laboratory Tests", "level_3": "- 최근 비정상 검사 결과 요약"},
    {"level_1": "Investigation", "level_2": "Imaing Results", "level_3": "- 최근 영상 판독 결과 요약"},
    {"level_1": "Treatments", "level_2": "Medications", "level_3": "- 약물 처방 요약(신규 추가 및 중단)"},
    {"level_1": "Treatments", "level_2": "Procedures", "level_3": "- 시술 및 처치 처방 요약(Drains/Lines/CRRT/ECMO/Ventilator)"},
    {"level_1": "Next steps", "level_2": "Immediate Action Plan", "level_3": "- 추가 검사 및 처방 내용"},
    {"level_1": "Next steps", "level_2": "Long-term Action Plan", "level_3": "- 전동 및 전원 계획"},
]
OUTPUT_SECTIONS = [row["level_1"] for row in OUTPUT_FRAMEWORK]

LLM_MODEL = "snuh/hari-q3-14b"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 4096

SHEET_NAMES = [
    "Physician Notes",
    "Nursing Notes",
    "Imaging Results",
    "Laboratory Test Results",
    "Medication Orders",
    "Procedure Orders",
    "Flowsheet",
    "Nursing Risk Assessment",
]

SHEET_NAME_TO_PROMPT = {
    "Physician Notes": "extractor_physician.md",
    "Nursing Notes": "extractor_nursing.md",
    "Imaging Results": "extractor_imaging.md",
    "Laboratory Test Results": "extractor_lab.md",
    "Medication Orders": "extractor_medication.md",
    "Procedure Orders": "extractor_procedure.md",
    "Flowsheet": "extractor_flowsheet.md",
    "Nursing Risk Assessment": "extractor_risk.md",
}
