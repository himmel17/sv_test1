#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulator Abstraction Layer for SystemVerilog Test Framework

Provides a unified interface for multiple simulators (Verilator, VCS)
with concrete implementations for each simulator's specific requirements.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import subprocess
import shutil
import re


def parse_timeout(timeout_str):
    """
    Parse timeout string with unit suffix and convert to seconds.

    Supports formats: "10000ns", "50us", "100ms", "5s"
    Also supports integers (us assumed for backward compatibility)

    Args:
        timeout_str: String with unit suffix or integer (us assumed)

    Returns:
        float: Timeout in seconds

    Raises:
        ValueError: If format is invalid
    """
    if isinstance(timeout_str, (int, float)):
        print(f"Warning: timeout_us (integer) is deprecated. Use timeout: \"{int(timeout_str)}us\" instead.")
        return timeout_str / 1_000_000

    if not isinstance(timeout_str, str):
        raise ValueError(f"Invalid timeout format: {timeout_str}")

    match = re.match(r'^(\d+\.?\d*)\s*(ns|us|ms|s)$', timeout_str.strip())
    if not match:
        raise ValueError(
            f"Invalid timeout format: {timeout_str}. "
            f"Expected format: '<number><unit>' (e.g., '50us', '10000ns')"
        )

    value = float(match.group(1))
    unit = match.group(2)

    conversions = {
        'ns': 1e-9,
        'us': 1e-6,
        'ms': 1e-3,
        's': 1.0
    }

    return value * conversions[unit]


def parse_sim_timeout(timeout_str, timescale_unit_str='1ns'):
    """
    Parse simulation timeout string and convert to numeric value in timescale units.

    Examples:
        parse_sim_timeout("50us", "1ns")   -> 50000
        parse_sim_timeout("50us", "1ps")   -> 50000000
        parse_sim_timeout("100ns", "1ps")  -> 100000

    Args:
        timeout_str: String with unit suffix (e.g., "50us", "10000ns")
        timescale_unit_str: Timescale unit from SystemVerilog (e.g., "1ns", "1ps")

    Returns:
        int: Timeout value in timescale units

    Raises:
        ValueError: If format is invalid
    """
    if not isinstance(timeout_str, str):
        raise ValueError(f"Invalid sim_timeout format: {timeout_str}")

    timeout_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timeout_str.strip())
    if not timeout_match:
        raise ValueError(
            f"Invalid sim_timeout format: {timeout_str}. "
            f"Expected format: '<number><unit>' (e.g., '50us', '10000ns')"
        )

    timeout_value = float(timeout_match.group(1))
    timeout_unit = timeout_match.group(2)

    timescale_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timescale_unit_str.strip())
    if not timescale_match:
        raise ValueError(
            f"Invalid timescale format: {timescale_unit_str}. "
            f"Expected format: '<number><unit>' (e.g., '1ns', '1ps')"
        )

    timescale_coefficient = float(timescale_match.group(1))
    timescale_unit = timescale_match.group(2)

    time_to_seconds = {
        'fs': 1e-15,
        'ps': 1e-12,
        'ns': 1e-9,
        'us': 1e-6,
        'ms': 1e-3,
        's': 1.0
    }

    timeout_seconds = timeout_value * time_to_seconds[timeout_unit]
    timescale_seconds_per_unit = timescale_coefficient * time_to_seconds[timescale_unit]
    result = timeout_seconds / timescale_seconds_per_unit

    return round(result)


def extract_timescale(sv_file_path):
    """
    Parse timescale directive from SystemVerilog file.

    Args:
        sv_file_path: Path to SystemVerilog file

    Returns:
        tuple: (unit, precision) e.g., ('1ns', '1ps') or (None, None)
    """
    try:
        with open(sv_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'`timescale\s+(\d+\.?\d*\s*\w+)\s*/\s*(\d+\.?\d*\s*\w+)', line.strip())
                if match:
                    unit = match.group(1).replace(' ', '')
                    precision = match.group(2).replace(' ', '')
                    return (unit, precision)
    except FileNotFoundError:
        print(f"Warning: File not found: {sv_file_path}")
    except Exception as e:
        print(f"Warning: Error reading {sv_file_path}: {e}")

    return (None, None)


class BaseSimulator(ABC):
    """
    Abstract base class for SystemVerilog simulators.

    Defines the interface that all simulator implementations must follow.
    """

    def __init__(self, project_root, project_config, sim_config, test_config):
        """
        Initialize simulator with project and test configurations.

        Args:
            project_root: Path to project root directory
            project_config: Project configuration from YAML
            sim_config: Simulator-specific configuration from YAML
            test_config: Test-specific configuration from YAML
        """
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.sim_config = sim_config
        self.test_config = test_config

        # Common paths
        self.rtl_dir = self.project_root / project_config.get('rtl_dir', 'rtl')
        self.tb_dir = self.project_root / project_config.get('tb_dir', 'tb')
        self.waves_dir = self.project_root / project_config.get('waves_dir', 'sim/waves')

        # Test-specific attributes
        self.test_name = test_config['name']
        self.top_module = test_config['top_module']
        self.testbench_file = test_config['testbench_file']
        self.rtl_files = test_config.get('rtl_files', [])
        self.vcd_file = self.waves_dir / f"{self.test_name}.vcd"

    @abstractmethod
    def get_work_dir(self) -> Path:
        """Return simulator-specific work directory for compilation artifacts."""
        pass

    @abstractmethod
    def get_executable_path(self) -> Path:
        """Return path to compiled simulation executable."""
        pass

    @abstractmethod
    def compile(self) -> bool:
        """
        Compile the design with simulator-specific commands.

        Returns:
            bool: True if compilation succeeded, False otherwise
        """
        pass

    @abstractmethod
    def run_simulation(self) -> bool:
        """
        Execute the compiled simulation.

        Returns:
            bool: True if simulation succeeded, False otherwise
        """
        pass

    @abstractmethod
    def clean(self):
        """Clean simulator-specific artifacts."""
        pass

    def get_effective_timescale(self):
        """
        Determine effective timescale for this test.

        Strategy:
        1. Auto-detect from testbench file
        2. Fallback to RTL files if testbench has no timescale
        3. Default to 1ns/1ps if no timescale found

        Returns:
            tuple: (unit, precision) e.g., ('1ns', '1ps')
        """
        tb_file = self.tb_dir / self.testbench_file
        tb_timescale = extract_timescale(tb_file)

        if tb_timescale != (None, None):
            return tb_timescale

        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            rtl_timescale = extract_timescale(rtl_path)
            if rtl_timescale != (None, None):
                print(f"   Warning: Using timescale from RTL file {rtl_file} (testbench has none)")
                return rtl_timescale

        print(f"   Warning: No timescale found, defaulting to 1ns/1ps")
        return ('1ns', '1ps')

    def validate_timescales(self):
        """Validate timescale consistency across source files."""
        timescales = []

        tb_file = self.tb_dir / self.testbench_file
        tb_ts = extract_timescale(tb_file)
        if tb_ts != (None, None):
            timescales.append(('testbench', self.testbench_file, tb_ts[0]))

        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            rtl_ts = extract_timescale(rtl_path)
            if rtl_ts != (None, None):
                timescales.append(('RTL', rtl_file, rtl_ts[0]))

        if timescales:
            unique_timescales = set(ts[2] for ts in timescales)
            if len(unique_timescales) > 1:
                print(f"   ⚠️  WARNING: Mixed timescales detected in test '{self.test_name}':")
                for file_type, filename, ts in timescales:
                    print(f"      {file_type:10s}: {filename:30s} → timescale {ts}")
                print(f"      Using testbench timescale for simulation timeout calculation")


class VerilatorSimulator(BaseSimulator):
    """Verilator simulator implementation."""

    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('obj_dir', 'sim/obj_dir')

    def get_executable_path(self) -> Path:
        return self.get_work_dir() / f"V{self.top_module}"

    def compile(self) -> bool:
        """Compile design with Verilator."""
        print(f"🔨 Compiling test '{self.test_name}' with Verilator...")

        cmd = ["verilator"]

        # Add common flags
        cmd.extend(self.sim_config.get('common_flags', []))

        # Add test-specific flags
        cmd.extend(self.test_config.get('verilator_extra_flags', []))

        # Add output directory
        cmd.extend(["-Mdir", str(self.get_work_dir())])

        # Add top module
        cmd.extend(["--top-module", self.top_module])

        # Add RTL search path
        cmd.extend(["-y", str(self.rtl_dir)])

        # Add simulation timeout parameter if specified
        if 'sim_timeout' in self.test_config:
            self.validate_timescales()

            timescale_unit, timescale_precision = self.get_effective_timescale()
            sim_timeout_str = self.test_config['sim_timeout']
            sim_timeout_value = parse_sim_timeout(sim_timeout_str, timescale_unit)

            cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")
            print(f"   Simulation timeout: {sim_timeout_str} → {sim_timeout_value} time units (timescale: {timescale_unit}/{timescale_precision})")

        # Add RTL files
        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            cmd.append(str(rtl_path))

        # Add testbench file
        cmd.append(str(self.tb_dir / self.testbench_file))

        print(f"   Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True
            )

            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)

            print("✓ Compilation successful\n")
            return True

        except subprocess.CalledProcessError as e:
            print("✗ Compilation FAILED")
            print(f"\nStdout:\n{e.stdout}")
            print(f"\nStderr:\n{e.stderr}")
            return False

    def run_simulation(self) -> bool:
        """Execute Verilator simulation."""
        print(f"🚀 Running simulation for '{self.test_name}'...")

        executable = self.get_executable_path()
        if not executable.exists():
            print(f"✗ Executable not found: {executable}")
            return False

        timeout_seconds = None
        if 'execution_timeout' in self.sim_config:
            timeout_seconds = parse_timeout(self.sim_config['execution_timeout'])
            print(f"   Execution timeout: {self.sim_config['execution_timeout']} ({timeout_seconds}s)")

        try:
            self.waves_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [str(executable)],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )

            print(result.stdout)
            if result.stderr:
                print(result.stderr)

            if self.vcd_file.exists():
                vcd_size = self.vcd_file.stat().st_size
                print(f"✓ Simulation complete (VCD: {vcd_size} bytes)\n")
                return True
            else:
                print("⚠ VCD file not generated (may be normal for some tests)\n")
                return True

        except subprocess.TimeoutExpired:
            print(f"✗ Simulation TIMEOUT (exceeded {timeout_seconds}s)")
            print(f"   The testbench may have an infinite loop or insufficient timeout value")
            return False

        except subprocess.CalledProcessError as e:
            print("✗ Simulation FAILED")
            print(f"\nStdout:\n{e.stdout}")
            print(f"\nStderr:\n{e.stderr}")
            return False

    def clean(self):
        """Clean Verilator artifacts."""
        print(f"🧹 Cleaning artifacts for test '{self.test_name}'...")

        work_dir = self.get_work_dir()
        if work_dir.exists():
            shutil.rmtree(work_dir)
            print(f"   Removed {work_dir}")

        if self.vcd_file.exists():
            self.vcd_file.unlink()
            print(f"   Removed {self.vcd_file}")

        print("✓ Clean complete\n")


class VCSSimulator(BaseSimulator):
    """Synopsys VCS simulator implementation."""

    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('vcs_dir', 'sim/vcs')

    def get_executable_path(self) -> Path:
        return self.get_work_dir() / "simv"

    def compile(self) -> bool:
        """Compile design with VCS."""
        print(f"🔨 Compiling test '{self.test_name}' with VCS...")

        work_dir = self.get_work_dir()
        work_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["vcs"]

        # Add common flags
        cmd.extend(self.sim_config.get('common_flags', []))

        # Add test-specific flags
        cmd.extend(self.test_config.get('vcs_extra_flags', []))

        # Output executable path
        cmd.extend(["-o", str(self.get_executable_path())])

        # Add simulation timeout parameter if specified
        if 'sim_timeout' in self.test_config:
            self.validate_timescales()

            timescale_unit, timescale_precision = self.get_effective_timescale()
            sim_timeout_str = self.test_config['sim_timeout']
            sim_timeout_value = parse_sim_timeout(sim_timeout_str, timescale_unit)

            # VCS uses +define+ for parameters
            cmd.append(f"+define+SIM_TIMEOUT={sim_timeout_value}")
            print(f"   Simulation timeout: {sim_timeout_str} → {sim_timeout_value} time units (timescale: {timescale_unit}/{timescale_precision})")

        # Add RTL files
        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            cmd.append(str(rtl_path))

        # Add testbench file
        cmd.append(str(self.tb_dir / self.testbench_file))

        print(f"   Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True
            )

            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)

            print("✓ Compilation successful\n")
            return True

        except subprocess.CalledProcessError as e:
            print("✗ Compilation FAILED")
            print(f"\nStdout:\n{e.stdout}")
            print(f"\nStderr:\n{e.stderr}")
            return False

    def run_simulation(self) -> bool:
        """Execute VCS simulation."""
        print(f"🚀 Running simulation for '{self.test_name}'...")

        executable = self.get_executable_path()
        if not executable.exists():
            print(f"✗ Executable not found: {executable}")
            return False

        timeout_seconds = None
        if 'execution_timeout' in self.sim_config:
            timeout_seconds = parse_timeout(self.sim_config['execution_timeout'])
            print(f"   Execution timeout: {self.sim_config['execution_timeout']} ({timeout_seconds}s)")

        try:
            self.waves_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [str(executable)],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )

            print(result.stdout)
            if result.stderr:
                print(result.stderr)

            if self.vcd_file.exists():
                vcd_size = self.vcd_file.stat().st_size
                print(f"✓ Simulation complete (VCD: {vcd_size} bytes)\n")
                return True
            else:
                print("⚠ VCD file not generated (may be normal for some tests)\n")
                return True

        except subprocess.TimeoutExpired:
            print(f"✗ Simulation TIMEOUT (exceeded {timeout_seconds}s)")
            print(f"   The testbench may have an infinite loop or insufficient timeout value")
            return False

        except subprocess.CalledProcessError as e:
            print("✗ Simulation FAILED")
            print(f"\nStdout:\n{e.stdout}")
            print(f"\nStderr:\n{e.stderr}")
            return False

    def clean(self):
        """Clean VCS artifacts."""
        print(f"🧹 Cleaning artifacts for test '{self.test_name}'...")

        work_dir = self.get_work_dir()
        if work_dir.exists():
            shutil.rmtree(work_dir)
            print(f"   Removed {work_dir}")

        # VCS also creates csrc/ and *.daidir in current directory
        csrc_dir = self.project_root / "csrc"
        if csrc_dir.exists():
            shutil.rmtree(csrc_dir)
            print(f"   Removed {csrc_dir}")

        simv_daidir = self.project_root / "simv.daidir"
        if simv_daidir.exists():
            shutil.rmtree(simv_daidir)
            print(f"   Removed {simv_daidir}")

        ucli_key = self.project_root / "ucli.key"
        if ucli_key.exists():
            ucli_key.unlink()
            print(f"   Removed {ucli_key}")

        if self.vcd_file.exists():
            self.vcd_file.unlink()
            print(f"   Removed {self.vcd_file}")

        print("✓ Clean complete\n")


class SimulatorFactory:
    """Factory for creating simulator instances."""

    @staticmethod
    def create_simulator(simulator_type: str, project_root, project_config,
                        sim_config, test_config) -> BaseSimulator:
        """
        Create a simulator instance based on type.

        Args:
            simulator_type: 'verilator' or 'vcs'
            project_root: Path to project root
            project_config: Project configuration
            sim_config: Simulator-specific configuration
            test_config: Test configuration

        Returns:
            BaseSimulator: Appropriate simulator instance

        Raises:
            ValueError: If simulator type is unknown
        """
        simulators = {
            'verilator': VerilatorSimulator,
            'vcs': VCSSimulator
        }

        if simulator_type not in simulators:
            raise ValueError(
                f"Unknown simulator: {simulator_type}. "
                f"Available simulators: {', '.join(simulators.keys())}"
            )

        return simulators[simulator_type](
            project_root, project_config, sim_config, test_config
        )
