"""
Helper functions for the unified IronSleep BIDSme bidsification notebook.

The notebook should stay small and user-facing. This module contains the
reusable logic for:

- checking paths
- detecting whether standard and/or LORAKS data are present
- building per-stream configuration
- running BIDSme prepare / mapper / bidsify
- checking expected bookkeeping outputs

It is designed to work with the generalized plugins:

- plugin_prepare_auto_tempfolder_no_idinfo_commented_nk.py
- plugin_bidsify_auto_with_csv_tsv_nk.py

Intended boundary:

- prepare may write temporary mapping files inside the prepared/temp folder
  (for example .prepare_id_map/), but not final BIDS metadata.
- bidsify writes durable id_info CSVs and sub-*_sessions.tsv/json files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import shlex
import subprocess


@dataclass(frozen=True)
class StreamConfig:
    """Configuration for one input stream: standard data or LORAKS data."""

    name: str
    source_path: Path
    prepared_path: Path
    bids_path: Path
    data_dirs: Mapping[str, str]
    include_smaps: bool = False


def print_path_report(paths: Mapping[str, Path]) -> None:
    """Print a compact existence report for important files/folders."""

    for name, path in paths.items():
        print(f"{name:24s}: {path} -> {path.exists()}")


def _path_contains_name(root: Path, names: Iterable[str]) -> bool:
    """Return True if a file/folder below root has exactly one of `names`."""

    if not root.exists():
        return False

    wanted = {name.casefold() for name in names}
    return any(path.name.casefold() in wanted for path in root.rglob("*"))


def _path_contains_text(root: Path, text: str) -> bool:
    """Return True if any path below root contains `text`."""

    if not root.exists():
        return False

    text = text.casefold()
    return any(text in str(path).casefold() for path in root.rglob("*"))


def detect_streams(source_path: Path) -> list[str]:
    """
    Detect which input streams are present.

    This is intentionally conservative and based on folder/file names, not on
    BIDSme internals. If it guesses wrong, set STREAMS_TO_RUN manually in the
    notebook.
    """

    has_standard = (
        _path_contains_name(source_path, ["dcm2niix", "nii", "nii_dcm2niix"])
        or _path_contains_text(source_path, "dcm2niix")
    )

    has_loraks = (
        _path_contains_name(source_path, ["nii_loraks_recon"])
        or _path_contains_text(source_path, "rec-loraks")
        or _path_contains_text(source_path, "loraks")
    )

    streams: list[str] = []
    if has_standard:
        streams.append("standard")
    if has_loraks:
        streams.append("loraks")
    return streams


def select_streams(source_path: Path, streams_to_run: str | Sequence[str]) -> list[str]:
    """Return the final list of streams that should be processed."""

    detected = detect_streams(source_path)
    if streams_to_run == "auto":
        selected = detected
    else:
        selected = list(streams_to_run)

    if not selected:
        raise RuntimeError(
            "No input stream selected. Check SOURCE_PATH or set STREAMS_TO_RUN "
            "to ['standard'], ['loraks'], or ['standard', 'loraks']."
        )

    invalid = sorted(set(selected) - {"standard", "loraks"})
    if invalid:
        raise ValueError(f"Unknown stream(s): {invalid}")

    print("Detected streams:", detected)
    print("Selected streams:", selected)
    return selected


def build_stream_configs(
    *,
    source_path: Path,
    standard_prepared_path: Path,
    standard_bids_path: Path,
    loraks_prepared_path: Path,
    loraks_bids_path: Path,
    include_smaps: bool,
) -> dict[str, StreamConfig]:
    """Create standard and LORAKS stream configurations."""

    return {
        "standard": StreamConfig(
            name="standard",
            source_path=source_path,
            prepared_path=standard_prepared_path,
            bids_path=standard_bids_path,
            data_dirs={
                # Original TerraX/dcm2niix layout.
                # Change this in the notebook only if your source folder differs.
                "dcm2niix/*": "MRI",
            },
            include_smaps=include_smaps,
        ),
        "loraks": StreamConfig(
            name="loraks",
            source_path=source_path,
            prepared_path=loraks_prepared_path,
            bids_path=loraks_bids_path,
            data_dirs={
                # Original LORAKS layout.
                "nii_loraks_recon": "MRI",
            },
            include_smaps=include_smaps,
        ),
    }


def print_stream_summary(configs: Mapping[str, StreamConfig], streams: Sequence[str]) -> None:
    """Print the resolved settings for each selected stream."""

    for stream in streams:
        cfg = configs[stream]
        print(f"\n[{stream}]")
        print("source:       ", cfg.source_path)
        print("prepared_path:", cfg.prepared_path)
        print("bids_path:    ", cfg.bids_path)
        print("data_dirs:    ", dict(cfg.data_dirs))
        print("include_smaps:", cfg.include_smaps)


def _report_and_reset_bidsme_errors(bidsme_module, logger) -> None:
    """Print BIDSme errors/warnings and reset the report state."""

    bidsme_module.tools.info.reporterrors(logger)
    bidsme_module.tools.info.reseterrors(logger)


def prepare_stream(
    bidsme_module,
    logger,
    cfg: StreamConfig,
    *,
    prepare_plugin: Path,
    participants_template: Path,
    sub_list: Sequence[str] | None = None,
) -> None:
    """Run BIDSme prepare for one stream."""

    print(f"\n=== PREPARE: {cfg.name} ===")
    print("source:  ", cfg.source_path)
    print("prepared:", cfg.prepared_path)

    kwargs = dict(
        data_dirs=dict(cfg.data_dirs),
        plugin_file=str(prepare_plugin),
        part_template=str(participants_template),
        plugin_opt={"include_smaps": cfg.include_smaps},
    )
    if sub_list:
        kwargs["sub_list"] = list(sub_list)

    bidsme_module.prepare(str(cfg.source_path), str(cfg.prepared_path), **kwargs)
    _report_and_reset_bidsme_errors(bidsme_module, logger)


def map_stream(
    bidsme_module,
    logger,
    cfg: StreamConfig,
    *,
    bidsify_plugin: Path,
    sessions_template: Path,
    sub_list: Sequence[str] | None = None,
) -> None:
    """Run BIDSme mapper for one stream."""

    print(f"\n=== MAP: {cfg.name} ===")
    print("prepared:", cfg.prepared_path)
    print("bids:    ", cfg.bids_path)

    kwargs = dict(
        plugin_file=str(bidsify_plugin),
        plugin_opt={
            "bidsmap_step": True,
            "include_smaps": cfg.include_smaps,
            "sessions_tsv_template": str(sessions_template),
        },
    )
    if sub_list:
        kwargs["sub_list"] = list(sub_list)

    bidsme_module.mapper(str(cfg.prepared_path), str(cfg.bids_path), **kwargs)
    _report_and_reset_bidsme_errors(bidsme_module, logger)


def _run_shell(cmd: Sequence[str | Path]) -> None:
    """Print and run a shell command safely."""

    printable = " ".join(shlex.quote(str(part)) for part in cmd)
    print(printable)
    subprocess.run([str(part) for part in cmd], check=True)


def bidsify_stream(
    cfg: StreamConfig,
    *,
    bidsify_plugin: Path,
    sessions_template: Path,
    sub_list: Sequence[str] | None = None,
    skip_existing: bool = False,
) -> None:
    """Run BIDSme bidsify for one stream through the command line."""

    bidsmap = cfg.bids_path / "code" / "bidsme" / "bidsmap.yaml"

    print(f"\n=== BIDSIFY: {cfg.name} ===")
    print("prepared:", cfg.prepared_path)
    print("bids:    ", cfg.bids_path)
    print("bidsmap: ", bidsmap)

    cmd: list[str | Path] = [
        "bidsme",
        "bidsify",
        cfg.prepared_path,
        cfg.bids_path,
        "-b",
        bidsmap,
        "--plugin",
        bidsify_plugin,
        "-o",
        f"include_smaps={cfg.include_smaps}",
        "-o",
        f"sessions_tsv_template={sessions_template}",
    ]

    if sub_list:
        cmd += ["--participants", *list(sub_list)]
    if skip_existing:
        cmd += ["--skip-existing"]

    _run_shell(cmd)


def check_outputs(cfg: StreamConfig) -> None:
    """Print the expected durable bookkeeping outputs after bidsify."""

    bids_path = cfg.bids_path

    print(f"\n=== CHECK: {cfg.name} ===")
    print("BIDS path exists:", bids_path.exists())

    id_info = bids_path / "id_info"
    print("id_info exists:", id_info.exists())
    if id_info.exists():
        print("id_info CSV files:")
        for path in sorted(id_info.glob("*.csv")):
            print("  ", path.relative_to(bids_path))

    print("sessions.tsv files:")
    for path in sorted(bids_path.glob("sub-*/sub-*_sessions.tsv")):
        print("  ", path.relative_to(bids_path))
