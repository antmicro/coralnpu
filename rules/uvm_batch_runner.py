#!/usr/bin/env python3
#
# Drives the UVM batch regression: builds the REGRESSION_LIST batch file,
# launches the Verilator/UVM model, and determines pass/fail from its
# REGRESSION_SUMMARY line (the model process always exits 0 regardless of
# UVM pass/fail, so the exit code alone can't be trusted).
#
# Env vars (set by the verilator_batch_uvm_test rule via RunEnvironmentInfo):
#   UVM_MODEL_RLOCATION: rlocation path of the model binary.
#   UVM_EXTRA_PATHS: newline-separated rlocation paths of riscv-tests
#     directories and coralnpu_v2_binary ELFs.

import os
import re
import subprocess
import sys
import tempfile

from bazel_tools.tools.python.runfiles import runfiles

from run_uvm_regression import (
    DENYLIST,
    format_batch_entry,
    get_entry_point,
    get_tohost_addr,
    is_riscv_test_file,
)

SUMMARY_RE = re.compile(r"\[REGRESSION_SUMMARY\] (\d+)/(\d+) tests failed\.")


def label_for_coralnpu_elf(path):
    marker = "/coralnpu_hw/"
    idx = path.rfind(marker)
    if idx == -1 or not path.endswith(".elf"):
        return None
    rel = path[idx + len(marker):-len(".elf")]
    pkg, _, name = rel.rpartition("/")
    return "//%s:%s" % (pkg, name)


def write_entry(f, path, seen, label=None):
    if path in seen:
        return
    if label is not None and label in DENYLIST:
        return
    seen.add(path)
    entry = get_entry_point(path)
    tohost = get_tohost_addr(path)
    if tohost is None:
        tohost = 0xFFFFFFFF
    f.write(format_batch_entry(path, tohost, entry, 100000, "NONE", path))


def build_batch_file(out_path, paths):
    seen = set()
    with open(out_path, "w") as f:
        for p in paths:
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for fname in sorted(files):
                        if not is_riscv_test_file(fname):
                            continue
                        label = "//third_party/riscv-tests:%s" % fname
                        write_entry(f, os.path.join(root, fname), seen, label)
            elif os.path.isfile(p):
                write_entry(f, p, seen, label_for_coralnpu_elf(p))


def main():
    r = runfiles.Create()

    model_rloc = os.environ["UVM_MODEL_RLOCATION"]
    model = r.Rlocation(model_rloc)
    if not model or not os.path.isfile(model):
        sys.exit("ERROR: model not found: %s" % model_rloc)

    extra_paths = [
        r.Rlocation(p)
        for p in os.environ.get("UVM_EXTRA_PATHS", "").splitlines()
        if p
    ]

    fd, batch_path = tempfile.mkstemp(prefix="uvm_batch_", suffix=".txt")
    os.close(fd)
    try:
        build_batch_file(batch_path, extra_paths)

        print("Batch list:")
        with open(batch_path) as f:
            print(f.read())

        print("Starting UVM regression...")
        proc = subprocess.Popen(
            [
                model,
                "+UVM_TESTNAME=coralnpu_regression_test",
                "+UVM_VERBOSITY=UVM_MEDIUM",
                "+REGRESSION_LIST=" + batch_path,
                "+TEST_ELF=dummy",
                "+TEST_TIMEOUT=100000",
                "+MISA_VALUE='h40201120",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        lines = []
        for line in proc.stdout:
            sys.stdout.write(line)
            lines.append(line)
        proc.wait()
        output = "".join(lines)
    finally:
        os.remove(batch_path)

    match = SUMMARY_RE.search(output)
    if not match:
        sys.exit("ERROR: no REGRESSION_SUMMARY line found in simulator output")

    failed, total = match.groups()
    print("[REGRESSION_SUMMARY] %s/%s tests failed." % (failed, total))
    sys.exit(1 if int(failed) else 0)


if __name__ == "__main__":
    main()
