# Copyright 2026 Antmicro

load("@coralnpu_host_cpus//:defs.bzl", "MAKE_JOBS")
load("@coralnpu_hw//third_party/python:requirements.bzl", "requirement")
load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cc_toolchain")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")
load("@rules_hdl//verilator:defs.bzl", "verilator_cc_library")
load("@rules_hdl//verilog:providers.bzl", "VerilogInfo", "verilog_library")
load("//rules:verilator.bzl", "verilator_model")

package(default_visibility = ["//visibility:public"])


verilator_model(
    name = "uvm_sim_verilator",
    cflags = [
        "+define+UVM_NO_DEPRECATED",
        "+define+TB_SUPPORT",
        "+define+VLEN_128",
        "+define+ZVE32F_ON",
        "+define+DUMP_WAVES_VCD",
        "-Wno-PINMISSING",
        "-Wno-lint",
        "-Wno-style",
        "-Wno-fatal",
        "--timescale 1ns/1ps",
        "--trace-vcd",
        "-CFLAGS \"-std=c++17\"",
    ],
    hdl_toplevel = "coralnpu_tb_top",
    verilog_source = "//hdl/chisel/src/coralnpu:rvv_core_mini_verification_axi_cc_library_emit_verilog",
    file_list = "coralnpu_dv.f",
)
