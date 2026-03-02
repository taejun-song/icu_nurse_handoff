import argparse
import asyncio
import json
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ICU Nurse Handoff Pipeline — batch processing script",
    )
    parser.add_argument("data_dir", help="Directory containing Input_Baseline_P*.xlsx and Input_Data_P*.xlsx files")
    parser.add_argument("--output-dir", default=None, help="Output root directory (default: <project>/output)")
    parser.add_argument("--patient", "-p", default=None, help="Process a single patient ID (e.g. P1, P3)")
    return parser.parse_args()


def discover_pairs(data_dir: Path, patient_filter: str | None = None) -> list[tuple[str, Path, Path]]:
    baselines = sorted(data_dir.glob("Input_Baseline_P*.xlsx"))
    pairs = []
    for bp in baselines:
        m = re.search(r"P(\d+)", bp.name)
        if not m:
            continue
        pid = f"P{m.group(1)}"
        if patient_filter and pid != patient_filter:
            continue
        dp = data_dir / f"Input_Data_{pid}.xlsx"
        if not dp.exists():
            print(f"[WARN] Data file missing for {pid}: {dp.name}", file=sys.stderr)
            continue
        pairs.append((pid, bp, dp))
    if not pairs:
        print(f"[ERROR] No matching Baseline/Data pairs found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    return pairs


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
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"[ERROR] Not a directory: {data_dir}", file=sys.stderr)
        sys.exit(1)
    if args.output_dir:
        output_root = Path(args.output_dir)
    else:
        from src.config import OUTPUT_DIR
        output_root = OUTPUT_DIR
    pairs = discover_pairs(data_dir, args.patient)
    print(f"Found {len(pairs)} patient(s): {', '.join(pid for pid, _, _ in pairs)}\n")
    failed = []
    for i, (pid, bp, dp) in enumerate(pairs, 1):
        print(f"{'='*60}")
        print(f"[{i}/{len(pairs)}] Processing {pid}")
        print(f"  Baseline: {bp.name}")
        print(f"  Data:     {dp.name}")
        print(f"{'='*60}")
        patient_output = output_root / pid
        try:
            asyncio.run(run_pipeline(bp, dp, patient_output))
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            sys.exit(130)
        except Exception as e:
            print(f"\n[ERROR] {pid} failed: {e}", file=sys.stderr)
            failed.append(pid)
            continue
        print()
    print(f"{'='*60}")
    print(f"Done. {len(pairs) - len(failed)}/{len(pairs)} patients succeeded.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
