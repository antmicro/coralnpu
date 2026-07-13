load("@rules_foreign_cc//foreign_cc:configure.bzl", "configure_make")
load("@coralnpu_hw//rules:verilator_defs.bzl", "VERILATOR_INCLUDE_FILES")

filegroup(
    name = "all_srcs",
    srcs = glob(["**"]),
    visibility = ["//visibility:public"],
)

configure_make(
    name = "verilator",
    args = ["-j8"],
    autoconf = True,
    configure_in_place = True,
    configure_options = [
        "CXX=clang++",
    ],
    lib_source = ":all_srcs",
    out_bin_dir = "bin",
    out_binaries = ["verilator_bin"],
    out_include_dir = "",
    out_data_files = ["share/verilator/include/{}".format(p) for p in VERILATOR_INCLUDE_FILES],
    visibility = ["//visibility:public"],
    env = {
        # Disable ccache in the sandbox
        "CCACHE_DISABLE": 1,
    },
)
