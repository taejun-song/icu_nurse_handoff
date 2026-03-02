import argparse
import asyncio
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ICU Nurse Handoff Pipeline — batch processing script",
    )
    parser.add_argument("baseline_file", help="Path to Baseline Excel file (.xlsx)")
    parser.add_argument("data_file", help="Path to Data Excel file (.xlsx)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: <project>/output)")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    baseline = Path(args.baseline_file)
    data = Path(args.data_file)
    errors = []
    for label, p in [("Baseline", baseline), ("Data", data)]:
        if not p.exists():
            errors.append(f"{label} file not found: {p}")
        elif p.suffix.lower() != ".xlsx":
            errors.append(f"{label} file is not an .xlsx file: {p}")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        from src.config import OUTPUT_DIR
        output_dir = OUTPUT_DIR
    return baseline, data, output_dir


async def run_pipeline(baseline_path: Path, data_path: Path, output_dir: Path) -> None:
    from src.loader import load_emr_file
    from src.extractors import extract_all
    from src.interpreter import interpret
    from src.validator import validate
    from src.generator import generate

    print("Loading EMR files...")
    baseline_sheets = load_emr_file(baseline_path)
    data_sheets = load_emr_file(data_path)
    print(f"Baseline sheets: {list(baseline_sheets.keys())}")
    print(f"Data sheets: {list(data_sheets.keys())}")
    for name, df in data_sheets.items():
        print(f"  {name}: {len(df)} rows")

    print("\nRunning extractors...")
    extractor_outputs = await extract_all(data_sheets)
    extractions_dir = output_dir / "extractions"
    extractions_dir.mkdir(parents=True, exist_ok=True)
    for eo in extractor_outputs:
        out_path = extractions_dir / f"{eo.sheet_name.replace(' ', '_').lower()}.json"
        out_path.write_text(json.dumps(eo.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted from {len(extractor_outputs)} sheets")

    print("\nRunning interpreter...")
    interpreter_output = await interpret(extractor_outputs, baseline_sheets)
    output_dir.mkdir(parents=True, exist_ok=True)
    interp_path = output_dir / "interpretation.json"
    interp_path.write_text(json.dumps(interpreter_output.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reconciled findings: {len(interpreter_output.reconciled_findings)}")

    print("\nRunning validator...")
    validator_output = await validate(interpreter_output, baseline_sheets)
    val_path = output_dir / "validation.json"
    val_path.write_text(json.dumps(validator_output.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Validated findings: {len(validator_output.validated_findings)}")

    print("\nGenerating summary...")
    generator_output = await generate(validator_output)
    summary_path = output_dir / "summary.md"
    summary_path.write_text(generator_output.summary, encoding="utf-8")

    print(f"\nPipeline complete. Summary saved to: {summary_path}")


def main() -> None:
    args = parse_args()
    baseline, data, output_dir = validate_inputs(args)
    try:
        asyncio.run(run_pipeline(baseline, data, output_dir))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
