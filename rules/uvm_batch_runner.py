#!/usr/bin/env python3
#
# Env vars (set by the verilator_batch_uvm_test rule):
#   UVM_MODEL_RLOCATION: rlocation path of the model binary
#   UVM_RISCV_DIRS: newline-separated rlocation paths of riscv-tests directories
#   UVM_CORALNPU_ELFS: newline-separated "<rlocation path>\t<bazel label>" pairs for individual coralnpu_v2_binary ELFs
#   UVM_SPIKE_RLOCATION: rlocation path of the spike binary, if any

import os
import re
import subprocess
import sys
import tempfile

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
)

SUMMARY_FAILED_RE = re.compile(r"\[REGRESSION_SUMMARY\] (\d+)/(\d+) tests failed\.")
SUMMARY_PASSED_RE = re.compile(r"\[REGRESSION_SUMMARY\] All (\d+) tests passed\.")


def write_entry(f, path, label, seen, spike_bin=None, spike_dir=None):
    if path in seen or label in DENYLIST:
        return
    seen.add(path)
    entry = get_entry_point(path)
    tohost = get_tohost_addr(path)
    if tohost is None:
        tohost = 0xFFFFFFFF

    spike_log = "NONE"

    timeout = TIMEOUT_MAP.get(label, 100000)
    f.write(format_batch_entry(path, tohost, entry, timeout, spike_log, path))


def build_batch_file(out_path, riscv_dirs, coralnpu_elfs, spike_bin=None):
    seen = set()
    spike_dir = tempfile.mkdtemp(prefix="uvm_spike_") if spike_bin else None
    with open(out_path, "w") as f:
        for d in riscv_dirs:
            for root, _, files in os.walk(d):
                for fname in sorted(files):
                    if not is_riscv_test_file(fname):
                        continue
                    label = "//third_party/riscv-tests:%s" % fname
                    write_entry(f, os.path.join(root, fname), label, seen,
                               spike_bin, spike_dir)
        for path, label in coralnpu_elfs:
            write_entry(f, path, label, seen, spike_bin, spike_dir)


def main():
    r = runfiles.Create()

    model_rloc = os.environ["UVM_MODEL_RLOCATION"]
    model = r.Rlocation(model_rloc)
    if not model or not os.path.isfile(model):
        sys.exit("ERROR: model not found: %s" % model_rloc)

    riscv_dirs = [
        r.Rlocation(p)
        for p in os.environ.get("UVM_RISCV_DIRS", "").splitlines()
        if p
    ]
    coralnpu_elfs = []
    for line in os.environ.get("UVM_CORALNPU_ELFS", "").splitlines():
        rloc, label = line.split("\t")
        coralnpu_elfs.append((r.Rlocation(rloc), label))

    spike_bin = None
    spike_rloc = os.environ.get("UVM_SPIKE_RLOCATION")
    if spike_rloc:
        spike_bin = r.Rlocation(spike_rloc)
        if not spike_bin or not os.path.isfile(spike_bin):
            sys.exit("ERROR: spike binary not found: %s" % spike_rloc)

    fd, batch_path = tempfile.mkstemp(prefix="uvm_batch_", suffix=".txt")
    os.close(fd)
    try:
        build_batch_file(batch_path, riscv_dirs, coralnpu_elfs, spike_bin)

        print("Batch list:")
        with open(batch_path) as f:
            print(f.read())

        print("Starting UVM regression...")
        proc = subprocess.Popen(
            [
                model,
                "+UVM_TESTNAME=coralnpu_regression_test",
                "+UVM_VERBOSITY=UVM_LOW",
                "+REGRESSION_LIST=" + batch_path,
                "+TEST_ELF=dummy",
                "+TEST_TIMEOUT=100000",
                "+MISA_VALUE='h40201120'",
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

    fail_match = SUMMARY_FAILED_RE.search(output)
    pass_match = SUMMARY_PASSED_RE.search(output)
    if fail_match:
        failed, total = fail_match.groups()
        print("[REGRESSION_SUMMARY] %s/%s tests failed." % (failed, total))
        sys.exit(1)
    elif pass_match:
        total = pass_match.group(1)
        print("[REGRESSION_SUMMARY] All %s tests passed." % total)
        sys.exit(0)
    else:
        sys.exit("ERROR: no REGRESSION_SUMMARY line found in simulator output")


if __name__ == "__main__":
    main()
