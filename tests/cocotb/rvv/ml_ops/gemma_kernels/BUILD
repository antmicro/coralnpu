# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

load("//rules:coralnpu_v2.bzl", "coralnpu_v2_binary")
load("//rules:utils.bzl", "template_rule")
load("//rules:coco_tb.bzl", "cocotb_test_suite")
load(
    "//tests/cocotb:build_defs.bzl",
    "VCS_BUILD_ARGS",
    "VCS_DEFINES",
    "VCS_TEST_ARGS",
)

package(default_visibility = ["//visibility:public"])

# Compile binary for NPU simulation
template_rule(
    coralnpu_v2_binary,
    {
        "rvv_rms_norm": {
            "srcs": ["rms_norm_runner.cc", "rvv_rms_norm.cc"],
            "hdrs": ["//sw/utils:utils.h"],
            "itcm_size_kbytes": 512,
            "dtcm_size_kbytes": 512,
        },
        "rvv_flashattention_test": {
            "srcs": ["rvv_flashattention_runner.cc", "rvv_flashattention_kernel.cc"],
            "hdrs": ["//sw/utils:utils.h"],
            "itcm_size_kbytes": 512,
            "dtcm_size_kbytes": 512,
        },
    },
)

# Test cases defined in rvv_rms_norm_cocotb_test.py
RVV_RMS_NORM_TESTCASES = [
    "core_mini_rvv_rms_norm_test",
]

RVV_FLASHATTENTION_TESTCASES = [
    "core_mini_rvv_flashattention_test",
]

# Filegroup for gemma weights to be packaged into runfiles
filegroup(
    name = "weights_files",
    srcs = glob(["test_data/*.npy"]),
)

# Cocotb test suite target
cocotb_test_suite(
    name = "rvv_rms_norm_cocotb_test",
    simulators = [
        "verilator",
        "vcs",
    ],
    testcases = RVV_RMS_NORM_TESTCASES,
    testcases_vname = "RVV_RMS_NORM_TESTCASES",
    tests_kwargs = {
        "hdl_toplevel": "RvvCoreMini_ITCM512KB_DTCM512KBAxi",
        "waves": False,
        "seed": "42",
        "tags": ["manual"],
        "test_module": ["rvv_rms_norm_cocotb_test.py"],
        "deps": [
            "//coralnpu_test_utils:sim_test_fixture",
            "@bazel_tools//tools/python/runfiles",
        ],
        "data": [
            ":rvv_rms_norm.elf",
            ":weights_files",
        ],
        "size": "enormous",
    },
    vcs_build_args = VCS_BUILD_ARGS,
    vcs_data = [
        ":rvv_rms_norm.elf",
        "//tests/cocotb:xprop.cfg",
        "@coralnpu_hw//hdl/verilog:dpi_files",
    ],
    vcs_defines = VCS_DEFINES,
    vcs_test_args = VCS_TEST_ARGS,
    vcs_verilog_sources = ["//hdl/chisel/src/coralnpu:rvv_core_mini_axi_cc_library_verilog"],
    verilator_model = "//tests/cocotb:rvv_core_mini_itcm512kb_dtcm512kb_axi_model",
)

cocotb_test_suite(
    name = "rvv_flashattention_cocotb_test",
    simulators = [
        "verilator",
        "vcs",
    ],
    testcases = RVV_FLASHATTENTION_TESTCASES,
    testcases_vname = "RVV_FLASHATTENTION_TESTCASES",
    tests_kwargs = {
        "hdl_toplevel": "RvvCoreMini_ITCM512KB_DTCM512KBAxi",
        "waves": False,
        "seed": "42",
        "tags": ["manual"],
        "test_module": ["rvv_flashattention_cocotb_test.py"],
        "deps": [
            "//coralnpu_test_utils:sim_test_fixture",
            "@bazel_tools//tools/python/runfiles",
        ],
        "data": [
            ":rvv_flashattention_test.elf",
            ":weights_files",
        ],
        "size": "enormous",
    },
    vcs_build_args = VCS_BUILD_ARGS,
    vcs_data = [
        ":rvv_flashattention_test.elf",
        "//tests/cocotb:xprop.cfg",
        "@coralnpu_hw//hdl/verilog:dpi_files",
    ],
    vcs_defines = VCS_DEFINES,
    vcs_test_args = VCS_TEST_ARGS,
    vcs_verilog_sources = ["//hdl/chisel/src/coralnpu:rvv_core_mini_axi_cc_library_verilog"],
    verilator_model = "//tests/cocotb:rvv_core_mini_itcm512kb_dtcm512kb_axi_model",
)
