from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _handle_empty_pairs(
    golds: list[str], preds: list[str],
) -> tuple[list[float], list[int]]:
    scores = [0.0] * len(golds)
    compute_indices = []
    for i, (g, p) in enumerate(zip(golds, preds)):
        g_empty = len(g.strip()) == 0
        p_empty = len(p.strip()) == 0
        if g_empty and p_empty:
            scores[i] = 1.0
        elif g_empty or p_empty:
            scores[i] = 0.0
        else:
            compute_indices.append(i)
    return scores, compute_indices


def compute_bertscore(
    golds: list[str],
    preds: list[str],
    model_type: str = "xlm-roberta-large",
    lang: str = "ko",
) -> dict[str, list[float]]:
    from bert_score import score as bert_score_fn
    base_scores, compute_indices = _handle_empty_pairs(golds, preds)
    p_scores = list(base_scores)
    r_scores = list(base_scores)
    f1_scores = list(base_scores)
    if not compute_indices:
        return {"precision": p_scores, "recall": r_scores, "f1": f1_scores}
    sub_golds = [golds[i] for i in compute_indices]
    sub_preds = [preds[i] for i in compute_indices]
    p, r, f1 = bert_score_fn(
        sub_preds, sub_golds, model_type=model_type, lang=lang, verbose=False,
    )
    for j, idx in enumerate(compute_indices):
        p_scores[idx] = float(p[j])
        r_scores[idx] = float(r[j])
        f1_scores[idx] = float(f1[j])
    return {"precision": p_scores, "recall": r_scores, "f1": f1_scores}


def compute_sbert_cosine(
    golds: list[str],
    preds: list[str],
    model_name: str = "jhgan/ko-sroberta-multitask",
) -> list[float]:
    from sentence_transformers import SentenceTransformer
    scores, compute_indices = _handle_empty_pairs(golds, preds)
    if not compute_indices:
        return scores
    model = SentenceTransformer(model_name)
    sub_golds = [golds[i] for i in compute_indices]
    sub_preds = [preds[i] for i in compute_indices]
    gold_embs = model.encode(sub_golds, normalize_embeddings=True)
    pred_embs = model.encode(sub_preds, normalize_embeddings=True)
    cosines = np.sum(gold_embs * pred_embs, axis=1)
    for j, idx in enumerate(compute_indices):
        scores[idx] = float(cosines[j])
    return scores


def aggregate_by_sheet(
    df: pd.DataFrame, metric_cols: list[str],
) -> pd.DataFrame:
    agg_dict = {col: ["count", "mean", "median", "std"] for col in metric_cols}
    grouped = df.groupby("sheet_name").agg(agg_dict)
    grouped.columns = ["_".join(c) for c in grouped.columns]
    return grouped.reset_index().sort_values(
        "sheet_name", key=lambda s: s.str.extract(r"(\d+)", expand=False).astype(int),
    )


def aggregate_by_framework(
    df: pd.DataFrame, metric_cols: list[str],
) -> pd.DataFrame:
    agg_dict = {col: "mean" for col in metric_cols}
    agg_dict[metric_cols[0]] = ["count", "mean"]
    grouped = df.groupby("level_1").agg(agg_dict)
    grouped.columns = [
        "count" if stat == "count" else f"{col}_mean"
        for col, stat in grouped.columns
    ]
    framework_order = [
        "Situation", "Assessments by Systems", "Investigation",
        "Treatments", "Next steps",
    ]
    grouped = grouped.reindex(
        [f for f in framework_order if f in grouped.index],
    )
    return grouped.reset_index().rename(columns={"level_1": "framework"})


def aggregate_by_level2(
    df: pd.DataFrame, metric_cols: list[str],
) -> pd.DataFrame:
    from src.alignment import LEVEL_2_HEADERS, LEVEL_2_TO_LEVEL_1
    agg_dict = {col: "mean" for col in metric_cols}
    agg_dict[metric_cols[0]] = ["count", "mean"]
    grouped = df.groupby("level_2").agg(agg_dict)
    grouped.columns = [
        "count" if stat == "count" else f"{col}_mean"
        for col, stat in grouped.columns
    ]
    grouped = grouped.reindex(
        [h for h in LEVEL_2_HEADERS if h in grouped.index],
    )
    grouped.insert(0, "level_1", grouped.index.map(LEVEL_2_TO_LEVEL_1))
    return grouped.reset_index()


def aggregate_overall(
    df: pd.DataFrame, metric_cols: list[str],
) -> dict:
    stats: dict = {"n_pairs": len(df)}
    for col in metric_cols:
        vals = df[col].dropna()
        stats[col] = {
            "count": int(len(vals)),
            "mean": round(float(vals.mean()), 4),
            "median": round(float(vals.median()), 4),
            "std": round(float(vals.std()), 4),
            "min": round(float(vals.min()), 4),
            "max": round(float(vals.max()), 4),
        }
    return stats


def save_results(
    pairs_df: pd.DataFrame,
    sheet_agg: pd.DataFrame,
    overall: dict,
    output_dir: str | Path,
    config: dict | None = None,
    framework_agg: pd.DataFrame | None = None,
    level2_agg: pd.DataFrame | None = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs_df.to_csv(output_dir / "results_per_sample.csv", index=False, encoding="utf-8-sig")
    sheet_agg.to_csv(output_dir / "results_by_sheet.csv", index=False, encoding="utf-8-sig")
    overall_out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config or {},
        "stats": overall,
    }
    (output_dir / "results_overall.json").write_text(
        json.dumps(overall_out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    metric_cols = [c for c in pairs_df.columns if c.startswith(("bertscore", "sbert"))]
    lines = [
        "# Summary Evaluation Report",
        f"\nGenerated: {overall_out['timestamp']}",
        f"\nTotal pairs evaluated: {overall['n_pairs']}",
        "\n## Overall Metrics\n",
    ]
    for col in metric_cols:
        s = overall[col]
        lines.append(
            f"- **{col}**: mean={s['mean']:.4f}, median={s['median']:.4f}, "
            f"std={s['std']:.4f}, min={s['min']:.4f}, max={s['max']:.4f}",
        )
    lines.append("\n## Per-Patient Aggregation\n")
    lines.append(sheet_agg.to_markdown(index=False))
    if framework_agg is not None:
        framework_agg.to_csv(
            output_dir / "results_by_framework.csv", index=False, encoding="utf-8-sig",
        )
        lines.append("\n## Per-Framework Aggregation\n")
        lines.append(framework_agg.to_markdown(index=False))
    if level2_agg is not None:
        level2_agg.to_csv(
            output_dir / "results_by_level2.csv", index=False, encoding="utf-8-sig",
        )
        lines.append("\n## Per-Level 2 Aggregation\n")
        lines.append(level2_agg.to_markdown(index=False))
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return output_dir
