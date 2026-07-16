#!/usr/bin/env python3
#
# This script acts as a backend for running UVM regression tests using Bazel
#
# Env vars (set by the verilator_batch_uvm_test rule):
#   UVM_MODEL_RLOCATION: rlocation path of the model binary
#   UVM_RISCV_DIRS: newline-separated rlocation paths of riscv-tests directories
#   UVM_CORALNPU_ELFS: newline-separated "<rlocation path>\t<bazel label>" pairs for individual coralnpu_v2_binary ELFs
#   UVM_SPIKE_RLOCATION: rlocation path of the spike binary, if any

from __future__ import annotations

import csv
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from itertools import chain
from pathlib import Path
from typing import IO, TypedDict

from bazel_tools.tools.python.runfiles import runfiles
from run_uvm_regression import (
    DENYLIST,
    SPIKE_DENYLIST,
    TIMEOUT_MAP,
    format_batch_entry,
    generate_spike_log,
    get_entry_point,
    get_tohost_addr,
    is_riscv_test_file,
    run_uvm_batch,
)


class TestInfo(TypedDict):
    """Metadata describing a single regression test."""

    elf: str
    tohost: int
    entry: int
    timeout: int
    spike: str
    safe_log: str


TestInfoMap = dict[str, TestInfo]


def write_entry(
    batch_file: IO[str],
    elf_path: Path,
    log_name: str,
    label: str,
    seen: set[Path],
    test_info_map: TestInfoMap,
) -> None:
    if elf_path in seen or label in DENYLIST:
        return

    seen.add(elf_path)

    entry = get_entry_point(str(elf_path))
    tohost = get_tohost_addr(str(elf_path))
    if tohost is None:
        tohost = 0xFFFFFFFF

    timeout = TIMEOUT_MAP.get(label, 100000)
    spike_log = "NONE"

    batch_file.write(
        format_batch_entry(
            str(elf_path),
            tohost,
            entry,
            timeout,
            spike_log,
            label,
        )
    )

    test_info_map[label] = TestInfo(
        elf=str(elf_path.resolve()),
        tohost=tohost,
        entry=entry,
        timeout=timeout,
        spike=spike_log,
        safe_log=log_name,
    )


def label_to_fname(label: str) -> str:
    return label.replace("//", "").replace(":", "_").replace("/", "_")


def build_batch_file(
    batch_path: Path,
    coralnpu_elfs: list[tuple[Path, str]],
) -> TestInfoMap:
    seen: set[Path] = set()
    test_info_map: TestInfoMap = {}
    with batch_path.open("w") as batch_file:
        for elf_path, label in coralnpu_elfs:
            write_entry(
                batch_file,
                elf_path,
                f"{label_to_fname(label)}.log",
                label,
                seen,
                test_info_map,
            )

    return test_info_map


def main():
    r = runfiles.Create()
    model_rloc = os.environ["UVM_MODEL_RLOCATION"]
    model = r.Rlocation(model_rloc)
    if not model or not os.path.isfile(model):
        sys.exit("ERROR: model not found: %s" % model_rloc)

    coralnpu_elfs = []
    for line in os.environ.get("UVM_CORALNPU_ELFS", "").splitlines():
        rloc, label = line.split("\t")
        coralnpu_elfs.append((Path(r.Rlocation(rloc)), label))

    results_tmp = tempfile.TemporaryDirectory()
    results_dir_path = Path(results_tmp.name)
    batch_path = results_dir_path / "uvm_batch_list.txt"
    log_path = results_dir_path / "logs"
    log_path.mkdir()
    regression_log_path = log_path / "regression.log"
    test_info_map = build_batch_file(batch_path, coralnpu_elfs)

    logging.info("Starting UVM regression...")
    cmd = [
        model,
        "+UVM_TESTNAME=coralnpu_regression_test",
        "+UVM_VERBOSITY=UVM_LOW",
        f"+REGRESSION_LIST={batch_path}",
        "+TEST_ELF=dummy",
        "+TEST_TIMEOUT=100000",
        "+MISA_VALUE='h40201120'",
    ]
    results, _ = run_uvm_batch(
        cmd,
        os.environ.copy(),
        regression_log_path.as_posix(),
        log_path.as_posix(),
        test_info_map,
    )

    with open(results_dir_path / "uvm_results.csv", "w", newline="") as csvfile:
        fieldnames = ["Target", "Status", "Reason", "Log Path"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    any_failed = any(r["Status"] != "PASS" for r in results)
    if any_failed:
        num_failed = sum(1 for r in results if r["Status"] != "PASS")
        logging.error(f"Regression FAILED: {num_failed} tests failed.")
        sys.exit(1)

    logging.info(f"Regression PASSED: {len(results)} tests total.")

    shutil.copytree(
        results_dir_path.as_posix(),
        (Path(os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")) / "uvm_regression_batch").as_posix(),
    )


if __name__ == "__main__":
    main()
