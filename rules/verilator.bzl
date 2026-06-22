"""Bazel functions for Verilator."""

load("@coralnpu_host_cpus//:defs.bzl", "MAKE_JOBS")
load("@coralnpu_hw//third_party/python:requirements.bzl", "requirement")
load("@rules_cc//cc:find_cc_toolchain.bzl", "find_cc_toolchain")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")
load("@rules_hdl//verilator:defs.bzl", "verilator_cc_library")
load("@rules_hdl//verilog:providers.bzl", "VerilogInfo", "verilog_library")

def _collect_verilog_files(dep):
    transitive_srcs = depset([], transitive = [dep[VerilogInfo].dag])
    all_srcs = [verilog_info_struct.srcs
                for verilog_info_struct in transitive_srcs.to_list()]
    all_files = [src for sub_tuple in all_srcs for src in sub_tuple]
    return all_files

def _verilator_testbench_test_impl(ctx):
    all_files = _collect_verilog_files(ctx.attr.deps)

    verilator_binary_output = ctx.actions.declare_file(ctx.attr.module)
    verilator_objdir_output = ctx.actions.declare_directory(
        ctx.attr.module + ".obj_dir")

    verilog_files = []
    for file in all_files:
        if file.extension in ["dat", "mem"]:
            continue
        verilog_files.append(file)

    command = [
        "verilator",
        "--binary",
    ]
    verilog_dirs = dict()
    for file in verilog_files:
        verilog_dirs[file.dirname] = None
    for verilog_file in verilog_files:
        command.append(verilog_file.path)
    command.append("-Mdir")
    command.append(verilator_objdir_output.path)
    command.append("-o")
    command.append(verilator_binary_output.path)

    ctx.actions.run_shell(
        outputs=[verilator_objdir_output, verilator_binary_output],
        inputs=verilog_files,
        command = " ".join(command),
        use_default_shell_env = True,
    )

    return [DefaultInfo(runfiles=ctx.runfiles(files=[verilator_objdir_output]),
                        executable=verilator_binary_output)]

_verilator_testbench_test = rule(
    _verilator_testbench_test_impl,
    attrs = {
        "srcs": attr.label_list(allow_files = True),
        "deps": attr.label(
            doc = "The verilog target to create a test bench for.",
            providers = [VerilogInfo],
            mandatory = True,
        ),
        "module": attr.string(
            doc = "The name of the verilog module to verilate.",
            mandatory = True,
        ),
    },
    test = True,
)

def verilator_testbench_test(name, tags=[], **kwargs):
    _verilator_testbench_test(name = name, tags = ["verilator"] + tags, **kwargs)


# Number of CPUs reserved per Verilate action in Bazel's local scheduler.
# Sourced from `nproc` at workspace-fetch time so we don't oversubscribe
# small hosts (a hardcoded 8 was blocking 6-core boxes from scheduling
# more than one action at a time).
_verilator_make_parallelism = MAKE_JOBS

def _verilator_resource_estimator(os, input_size):
    # Cap the scheduler reservation at 4 so multiple actions can still run
    # in parallel on larger hosts; the `make -j` inside the action is free
    # to use more threads if the scheduler hands them over.
    return {"cpu": min(_verilator_make_parallelism, 4), "memory": 4096}

def _verilator_model_impl(ctx):
    hdl_toplevel = ctx.attr.hdl_toplevel
    outdir_name = hdl_toplevel + "_build"

    cc_toolchain = find_cc_toolchain(ctx)
    compiler_executable = cc_toolchain.compiler_executable
    ar_executable = cc_toolchain.ar_executable
    ld_executable = cc_toolchain.ld_executable

    # Collect DPI/C++ dependencies
    dpi_srcs_dict = {}
    dpi_includes = []
    dpi_files_dict = {}
    verilog_srcs = []

    def add_dpi_src(f):
        if type(f) == "File" and f.extension in ["cc", "cpp", "cxx", "c", "a", "o"]:
            dpi_srcs_dict[f.path] = "$PWD/" + f.path
            dpi_files_dict[f.path] = f

    def add_dpi_file(f):
        if type(f) == "File":
            dpi_files_dict[f.path] = f

    # We need to collect CC sources transitively
    for dep in ctx.attr.deps:
        if CcInfo in dep:
            cc_info = dep[CcInfo]

            # Transitive includes
            for inc in cc_info.compilation_context.includes.to_list():
                dpi_includes.append("-I" + inc)
            for inc in cc_info.compilation_context.quote_includes.to_list():
                dpi_includes.append("-I" + inc)
            for inc in cc_info.compilation_context.system_includes.to_list():
                dpi_includes.append("-I" + inc)

            # Transitive headers
            for f in cc_info.compilation_context.headers.to_list():
                add_dpi_file(f)

            # Transitive sources
            # Bazel rules often put sources in DefaultInfo
            for f in dep[DefaultInfo].files.to_list():
                add_dpi_src(f)
                if f.extension in ["h", "hh", "hpp"]:
                    add_dpi_file(f)

            # Check transitive linker inputs for sources that might be hidden
            # This is necessary for targets that don't have sources in DefaultInfo
            for li in cc_info.linking_context.linker_inputs.to_list():
                for lib in li.libraries:
                    if lib.static_library:
                        add_dpi_file(lib.static_library)
                    if lib.pic_static_library:
                        add_dpi_file(lib.pic_static_library)
                    if lib.objects:
                        for obj in lib.objects:
                            add_dpi_file(obj)

        if VerilogInfo in dep:
            verilog_srcs.append(dep[VerilogInfo].dag)

    # Collect all input files for the action and their paths
    all_inputs_dict = {}
    verilog_paths = []

    def add_input(f):
        if type(f) == "File":
            all_inputs_dict[f.path] = f
            return True
        return False

    for f in dpi_files_dict.values():
        add_input(f)

    # Process verilog sources collected from deps and direct attributes
    for f in verilog_srcs:
        if type(f) == "File":
            if add_input(f):
                verilog_paths.append(f.path)
        elif hasattr(f, "to_list"):  # It's a depset from VerilogInfo.dag
            for node in f.to_list():
                for s in node.srcs:
                    if add_input(s):
                        verilog_paths.append(s.path)

    if ctx.attr.verilog_source:
        f = ctx.file.verilog_source
        add_input(f)
        verilog_paths.append(f.path)

    for f in ctx.files.verilog_sources:
        add_input(f)
        verilog_paths.append(f.path)

    for f in ctx.files.source_files:
        add_input(f)
        verilog_paths.append(f.path)

    for f in ctx.files.source_file_deps:
        add_input(f)

    for f in ctx.files.include_dirs_deps:
        add_input(f)

    vlt_file = ctx.actions.declare_file(hdl_toplevel + ".vlt")
    ctx.actions.expand_template(
        output = vlt_file,
        template = ctx.file.vlt_tpl,
        substitutions = {"{HDL_TOPLEVEL}": hdl_toplevel},
    )
    add_input(vlt_file)

    output_file = ctx.actions.declare_file(outdir_name + "/" + hdl_toplevel)
    make_log = ctx.actions.declare_file(outdir_name + "/make.log")
    outdir = output_file.dirname

    verilator_root = "$PWD/{}.runfiles/coralnpu_hw/external/verilator".format(ctx.executable._verilator_bin.path)
    uvm_lib_path = "$PWD/{}".format(ctx.files._uvm_lib[0].dirname)
    coralnpu_mpact_lib_path = "$PWD/{}".format(ctx.files.coralnpu_mpact_lib[0].path)

    # Prepend $PWD to paths for verilator to find them in the sandbox
    verilog_sources_str = " ".join(["$PWD/" + p if not p.startswith("/") else p for p in verilog_paths])

    include_dirs_str = " ".join(["-I" + p.path for p in ctx.files.include_dirs])

    verilator_cmd = " ".join("""
        VERILATOR_ROOT={verilator_root} {verilator} \
            -cc \
            --exe \
            --main \
            -Mdir {outdir} \
            --top-module {hdl_toplevel} \
            --vpi \
            --prefix Vtop \
            -o {hdl_toplevel} \
            {include_dirs_str}
            -I"{uvm_lib_path}/src" \
	        "{uvm_lib_path}/src/uvm_pkg.sv" \
	        "{uvm_lib_path}/src/dpi/uvm_dpi.cc" \
            "{coralnpu_mpact_lib_path}" \
            {trace} \
            {cflags} \
            -I. -Ihdl/verilog {dpi_includes} \
            $PWD/{vlt_file} \
            {dpi_srcs} \
            {verilog_sources}
    """.strip().split("\n")).format(
        verilator = ctx.executable._verilator_bin.path,
        verilator_root = verilator_root,
        outdir = outdir,
        hdl_toplevel = hdl_toplevel,
        include_dirs_str = include_dirs_str,
        uvm_lib_path = uvm_lib_path,
        coralnpu_mpact_lib_path = coralnpu_mpact_lib_path,
        cflags = " ".join(ctx.attr.cflags),
        dpi_includes = " ".join({inc: None for inc in dpi_includes}.keys()),  # Unique includes
        vlt_file = vlt_file.path,
        dpi_srcs = " ".join(dpi_srcs_dict.values()),
        verilog_sources = verilog_sources_str,
        trace = "--trace" if ctx.attr.trace else "",
    )

    make_cmd = "PATH=`dirname {ld}`:$PATH make -j {parallelism} -C {outdir} -f Vtop.mk {trace} CXX={cxx} AR={ar} LINK={cxx} > {make_log} 2>&1".format(
        outdir = outdir,
        make_log = make_log.path,
        trace = "VM_TRACE=1" if ctx.attr.trace else "",
        ar = ar_executable,
        ld = ld_executable,
        cxx = compiler_executable,
        parallelism = _verilator_make_parallelism,
    )

    script = " && ".join([verilator_cmd.strip(), make_cmd])

    ctx.actions.run_shell(
        outputs = [output_file, make_log],
        tools = ctx.files._verilator_bin,
        inputs = depset(
            [f for f in all_inputs_dict.values()],
            transitive = [
                depset(ctx.files._verilator),
                depset(ctx.files._uvm_lib),
                depset(ctx.files.coralnpu_mpact_lib),
            ],
        ),
        command = script,
        mnemonic = "Verilate",
        resource_set = _verilator_resource_estimator,
    )

    return [
        DefaultInfo(
            files = depset([output_file, make_log]),
            runfiles = ctx.runfiles(files = [output_file, make_log]),
            executable = output_file,
        ),
        OutputGroupInfo(
            all_files = depset([output_file, make_log]),
        ),
    ]

verilator_model = rule(
    doc = """Builds a standalone Verilator model.

    This rule takes a verilog source file and a toplevel module name and
    builds a verilator model.

    It returns a DefaultInfo provider with an executable that can be run
    to execute the simulation.

    Attributes:
        verilog_source: The verilog source file to build the model from.
        hdl_toplevel: The name of the toplevel module.
        cflags: A list of flags to pass to the compiler.
        deps: Additional C++/DPI dependencies (CcInfo).
    """,
    implementation = _verilator_model_impl,
    attrs = {
        "verilog_source": attr.label(allow_single_file = True, mandatory = False),
        "verilog_sources": attr.label_list(allow_files = [".v", ".sv"]),
        "include_dirs": attr.label_list(allow_files = True),
        "include_dirs_deps": attr.label_list(allow_files = True),
        "source_files": attr.label_list(allow_files = True),
        "source_file_deps": attr.label_list(allow_files = True),
        "hdl_toplevel": attr.string(mandatory = True),
        "cflags": attr.string_list(default = []),
        "deps": attr.label_list(providers = [[DefaultInfo], [CcInfo], [VerilogInfo]]),
        "trace": attr.bool(default = False),
        "vlt_tpl": attr.label(
            default = "@coralnpu_hw//rules:default.vlt.tpl",
            allow_single_file = True,
        ),
        "_verilator": attr.label(
            default = "@verilator//:verilator",
            executable = True,
            cfg = "exec",
        ),
        "_verilator_bin": attr.label(
            default = "@verilator//:verilator_bin",
            executable = True,
            cfg = "exec",
        ),
        "_uvm_lib": attr.label(
            default = "@uvm-verilator//:all_srcs",
            allow_files = True,
        ),
        "coralnpu_mpact_lib": attr.label(
            allow_files = True,
        ),
    },
    executable = True,
    toolchains = ["@bazel_tools//tools/cpp:toolchain_type"],
)
