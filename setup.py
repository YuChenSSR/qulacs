import os
import platform
import subprocess
import sys

from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext

VERSION = "0.2.0"
PROJECT_NAME = "qulacs-osaka"


def _get_n_cpus(platform_name: str) -> str:
    """Get the number of logical CPUs.

    Args:
        platform_name: Assumed to the return value of `platform.system()`.
    """
    command = [""]
    if platform_name == "Linux":
        command = ["nproc"]
    elif platform_name == "Darwin":
        command = ["sysctl", "-n", "hw.ncpu"]

    try:
        # Output contains newline character, so strip it.
        n_cpus = subprocess.check_output(command).strip().decode("utf-8")
    except PermissionError:
        # A case that the `command` is not available on the machine.
        # `subprocess.check_output("")` also throws this error.
        n_cpus = ""
    return n_cpus


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    user_options = build_ext.user_options + [
        ("opt-flags=", "o", "optimization flags for compiler")
    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.opt_flags = None

    def finalize_options(self):
        build_ext.finalize_options(self)

    def run(self):
        try:
            subprocess.check_output(["cmake", "--version"])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the following extensions: "
                + ", ".join(e.name for e in self.extensions)
            )

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        build_args, cmake_args = self._generate_args(ext)

        if self.opt_flags is not None:
            opt_flags = self.opt_flags
        elif os.getenv("QULACS_OPT_FLAGS"):
            opt_flags = os.getenv("QULACS_OPT_FLAGS")
        else:
            opt_flags = None
        if opt_flags:
            cmake_args += ["-DOPT_FLAGS=" + opt_flags]

        if os.getenv("USE_GPU"):
            cmake_args += ["-DUSE_GPU:STR=" + os.getenv("USE_GPU")]
        
        if os.getenv("USE_OMP"):
            cmake_args += ["-DUSE_OMP:STR=" + os.getenv("USE_OMP")]

        env = os.environ.copy()
        env["CXXFLAGS"] = '{} -DVERSION_INFO=\\"{}\\"'.format(
            env.get("CXXFLAGS", ""), self.distribution.get_version()
        )
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        build_dir = os.path.join(os.getcwd(), "build")
        os.makedirs(build_dir, exist_ok=True)
        subprocess.check_call(
            ["cmake", ext.sourcedir] + cmake_args, cwd=build_dir, env=env
        )
        subprocess.check_call(
            ["cmake", "--build", ".", "--target", "python"] + build_args, cwd=build_dir
        )

    def _generate_args(self, ext):
        # Following directories are created by cmake automatically.
        # Directory to output archive file.
        archive_dir = os.path.join(os.getcwd(), "lib")
        # Directory to output .so file generated by pybind.
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        # Directory to output test binaries.
        bindir = os.path.join(os.getcwd(), "bin")
        cmake_args = [
            "-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY=" + archive_dir,
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=" + extdir,
            "-DCMAKE_RUNTIME_OUTPUT_DIRECTORY=" + bindir,
            "-DPYTHON_EXECUTABLE=" + sys.executable,
            "-DPYTHON_SETUP_FLAG:STR=Yes",
            "-DUSE_GPU:STR=No",
        ]

        cfg = "Debug" if self.debug else "Release"
        build_args = ["--config", cfg]

        if platform.system() == "Windows":
            cmake_args += [
                "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir),
                "-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir),
            ]
            if sys.maxsize > 2 ** 32:
                cmake_args += ["-A", "x64"]
            build_args += ["--", "/m"]
        else:
            gcc = os.getenv("C_COMPILER", "gcc")
            gxx = os.getenv("CXX_COMPILER", "g++")
            if gcc is None or gxx is None:
                raise RuntimeError(
                    "gcc/g++ must be installed to build the following extensions: "
                    + ", ".join(e.name for e in self.extensions)
                )

            cmake_args += ["-DCMAKE_C_COMPILER=" + gcc]
            cmake_args += ["-DCMAKE_CXX_COMPILER=" + gxx]
            cmake_args += ["-DCMAKE_BUILD_TYPE=" + cfg]

            n_cpus = _get_n_cpus(platform.system())
            build_args += ["--", f"-j{n_cpus}"]

        return build_args, cmake_args


setup(
    name=PROJECT_NAME,
    version=VERSION,
    author="QunaSys",
    author_email="qulacs@qunasys.com",
    url="http://www.qulacs.org",
    description="Quantum circuit simulator for research",
    long_description="",
    package_dir={"": "pysrc"},
    packages=find_packages(exclude=["test*"]) + find_packages("pysrc"),
    package_data={"": ["py.typed", "*.pyi"]},
    include_package_data=True,
    ext_modules=[CMakeExtension("qulacs_core")],
    cmdclass=dict(build_ext=CMakeBuild),
    zip_safe=False,
    test_suite="test",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Communications :: Email",
    ],
)
