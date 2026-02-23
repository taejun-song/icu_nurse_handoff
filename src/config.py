from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
DATA_DIR = ROOT_DIR / "data"
PROMPTS_DIR = ROOT_DIR / "prompts"
OUTPUT_DIR = ROOT_DIR / "output"
EXTRACTIONS_DIR = OUTPUT_DIR / "extractions"
CACHE_DIR = ROOT_DIR / ".cache"

BASELINE_FILE = DATA_DIR / "Input_Baseline_P1.xlsx"
INPUT_DATA_FILE = DATA_DIR / "Input_Data_P1.xlsx"
OUTPUT_FRAMEWORK_FILE = DATA_DIR / "Output_Framework.xlsx"

LLM_MODEL = "claude-sonnet-4-5-20250929"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 8192

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
