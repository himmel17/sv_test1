#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SystemVerilog Testbench Runner with Verilator (YAML Config Version)
Manages compilation, simulation, and waveform viewing for multiple test modules
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import shutil

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip3 install pyyaml")
    sys.exit(1)

import re


def extract_timescale(sv_file_path):
    """
    Parse timescale directive from SystemVerilog file.

    Args:
        sv_file_path: Path to SystemVerilog file

    Returns:
        tuple: (unit, precision) e.g., ('1ns', '1ps') or ('1ps', '1fs')
               Returns (None, None) if no timescale found

    Examples:
        `timescale 1ns / 1ps  → ('1ns', '1ps')
        `timescale 1ps/1fs    → ('1ps', '1fs')
        `timescale 100fs/1fs  → ('100fs', '1fs')
    """
    try:
        with open(sv_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: `timescale <unit> / <precision>
                # Supports whitespace variations and coefficients (e.g., 100fs)
                match = re.match(r'`timescale\s+(\d+\.?\d*\s*\w+)\s*/\s*(\d+\.?\d*\s*\w+)', line.strip())
                if match:
                    unit = match.group(1).replace(' ', '')  # Remove any whitespace
                    precision = match.group(2).replace(' ', '')
                    return (unit, precision)
    except FileNotFoundError:
        print(f"Warning: File not found: {sv_file_path}")
    except Exception as e:
        print(f"Warning: Error reading {sv_file_path}: {e}")

    return (None, None)


def parse_timeout(timeout_str):
    """
    Parse timeout string with unit suffix and convert to seconds.

    Supported formats:
        "10000ns"   -> 0.00001 seconds
        "50us"      -> 0.00005 seconds
        "100ms"     -> 0.1 seconds
        "5s"        -> 5.0 seconds
        50000 (int) -> interpret as microseconds (backward compatibility)

    Args:
        timeout_str: String with unit suffix or integer (us assumed)

    Returns:
        float: Timeout in seconds

    Raises:
        ValueError: If format is invalid
    """
    # Backward compatibility: if integer, treat as microseconds
    if isinstance(timeout_str, (int, float)):
        print(f"Warning: timeout_us (integer) is deprecated. Use timeout: \"{int(timeout_str)}us\" instead.")
        return timeout_str / 1_000_000  # Convert us to seconds

    # Parse string format
    if not isinstance(timeout_str, str):
        raise ValueError(f"Invalid timeout format: {timeout_str}")

    # Extract number and unit
    match = re.match(r'^(\d+\.?\d*)\s*(ns|us|ms|s)$', timeout_str.strip())
    if not match:
        raise ValueError(f"Invalid timeout format: {timeout_str}. Expected format: '<number><unit>' (e.g., '50us', '10000ns')")

    value = float(match.group(1))
    unit = match.group(2)

    # Convert to seconds
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

    This function is timescale-aware: it correctly converts the timeout duration
    to the number of time units based on the testbench's actual timescale.

    Examples:
        parse_sim_timeout("50us", "1ns")   -> 50000      (50μs = 50000 × 1ns)
        parse_sim_timeout("50us", "1ps")   -> 50000000   (50μs = 50000000 × 1ps)
        parse_sim_timeout("100ns", "1ps")  -> 100000     (100ns = 100000 × 1ps)
        parse_sim_timeout("1ms", "100fs")  -> 10000000000 (1ms = 10^10 × 100fs)

    Args:
        timeout_str: String with unit suffix (e.g., "50us", "10000ns", "1ms")
        timescale_unit_str: Timescale unit from SystemVerilog (e.g., "1ns", "1ps", "100fs")

    Returns:
        int: Timeout value in timescale units (for use with -GSIM_TIMEOUT parameter)

    Raises:
        ValueError: If format is invalid
    """
    if not isinstance(timeout_str, str):
        raise ValueError(f"Invalid sim_timeout format: {timeout_str}")

    # Parse timeout string (e.g., "50us" -> value=50, unit="us")
    timeout_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timeout_str.strip())
    if not timeout_match:
        raise ValueError(
            f"Invalid sim_timeout format: {timeout_str}. "
            f"Expected format: '<number><unit>' (e.g., '50us', '10000ns')"
        )

    timeout_value = float(timeout_match.group(1))
    timeout_unit = timeout_match.group(2)

    # Parse timescale unit (e.g., "1ns" -> coefficient=1, unit="ns")
    #                         "100fs" -> coefficient=100, unit="fs")
    timescale_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timescale_unit_str.strip())
    if not timescale_match:
        raise ValueError(
            f"Invalid timescale format: {timescale_unit_str}. "
            f"Expected format: '<number><unit>' (e.g., '1ns', '1ps', '100fs')"
        )

    timescale_coefficient = float(timescale_match.group(1))
    timescale_unit = timescale_match.group(2)

    # Conversion factors to seconds
    time_to_seconds = {
        'fs': 1e-15,
        'ps': 1e-12,
        'ns': 1e-9,
        'us': 1e-6,
        'ms': 1e-3,
        's': 1.0
    }

    # Convert timeout to seconds
    timeout_seconds = timeout_value * time_to_seconds[timeout_unit]

    # Convert timescale unit to seconds (accounting for coefficient)
    timescale_seconds_per_unit = timescale_coefficient * time_to_seconds[timescale_unit]

    # Calculate number of timescale units needed for the timeout duration
    result = timeout_seconds / timescale_seconds_per_unit

    # Return as integer with proper rounding (not truncation)
    # Use round() to handle floating-point precision issues (e.g., 49999.9999... → 50000)
    return round(result)


class TestConfig:
    """Manages test configuration from YAML file"""

    def __init__(self, config_file):
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(self.config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.project = self.config.get('project', {})
        self.verilator = self.config.get('verilator', {})
        self.tests = self.config.get('tests', [])

    def get_enabled_tests(self):
        """Return list of enabled test configurations"""
        return [test for test in self.tests if test.get('enabled', True)]

    def get_test(self, test_name):
        """Get specific test configuration by name"""
        for test in self.tests:
            if test['name'] == test_name:
                return test
        return None

    def list_tests(self):
        """List all available tests"""
        return [test['name'] for test in self.tests]


class TestRunner:
    """Runs individual test cases"""

    def __init__(self, project_root, project_config, verilator_config, test_config):
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.verilator_config = verilator_config
        self.test_config = test_config

        # Setup paths
        self.rtl_dir = self.project_root / project_config.get('rtl_dir', 'rtl')
        self.tb_dir = self.project_root / project_config.get('tb_dir', 'tb')
        self.sim_dir = self.project_root / project_config.get('sim_dir', 'sim')
        self.obj_dir = self.project_root / project_config.get('obj_dir', 'sim/obj_dir')
        self.waves_dir = self.project_root / project_config.get('waves_dir', 'sim/waves')

        # Test-specific attributes
        self.test_name = test_config['name']
        self.top_module = test_config['top_module']
        self.testbench_file = test_config['testbench_file']
        self.rtl_files = test_config.get('rtl_files', [])
        self.vcd_file = self.waves_dir / f"{self.test_name}.vcd"
        self.executable = self.obj_dir / f"V{self.top_module}"

    def get_effective_timescale(self):
        """
        Determine effective timescale for this test.

        Strategy (Hybrid Approach):
        1. If 'timescale' explicitly set in test config YAML, use that (override)
        2. Otherwise, auto-detect from testbench file
        3. Validate: warn if RTL files have different timescales

        Returns:
            tuple: (unit, precision) e.g., ('1ns', '1ps')
                   Defaults to ('1ns', '1ps') if not found
        """
        # Check for explicit YAML override first
        if 'timescale' in self.test_config:
            yaml_timescale = self.test_config['timescale']
            # YAML format is just the unit (e.g., "1ns"), add default precision
            return (yaml_timescale, '1ps')  # Default precision

        # Auto-detect from testbench file
        tb_file = self.tb_dir / self.testbench_file
        tb_timescale = extract_timescale(tb_file)

        # If testbench has timescale, use it
        if tb_timescale != (None, None):
            return tb_timescale

        # Fallback: check RTL files
        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            rtl_timescale = extract_timescale(rtl_path)
            if rtl_timescale != (None, None):
                print(f"   Warning: Using timescale from RTL file {rtl_file} (testbench has none)")
                return rtl_timescale

        # Ultimate fallback: default to 1ns/1ps (Verilator default)
        print(f"   Warning: No timescale found, defaulting to 1ns/1ps")
        return ('1ns', '1ps')

    def validate_timescales(self):
        """
        Validate timescale consistency across all source files.
        Prints warnings if mixed timescales detected.
        """
        timescales = []

        # Check testbench
        tb_file = self.tb_dir / self.testbench_file
        tb_ts = extract_timescale(tb_file)
        if tb_ts != (None, None):
            timescales.append(('testbench', self.testbench_file, tb_ts[0]))

        # Check RTL files
        for rtl_file in self.rtl_files:
            rtl_path = self.rtl_dir / rtl_file
            rtl_ts = extract_timescale(rtl_path)
            if rtl_ts != (None, None):
                timescales.append(('RTL', rtl_file, rtl_ts[0]))

        # Check for inconsistencies
        if timescales:
            unique_timescales = set(ts[2] for ts in timescales)
            if len(unique_timescales) > 1:
                print(f"   ⚠️  WARNING: Mixed timescales detected in test '{self.test_name}':")
                for file_type, filename, ts in timescales:
                    print(f"      {file_type:10s}: {filename:30s} → timescale {ts}")
                print(f"      Using testbench timescale for simulation timeout calculation")

    def clean(self):
        """Clean simulation artifacts for this test"""
        print(f"🧹 Cleaning artifacts for test '{self.test_name}'...")
        if self.obj_dir.exists():
            shutil.rmtree(self.obj_dir)
            print(f"   Removed {self.obj_dir}")
        if self.vcd_file.exists():
            self.vcd_file.unlink()
            print(f"   Removed {self.vcd_file}")
        print("✓ Clean complete\n")

    def verilate(self):
        """Compile SystemVerilog with Verilator"""
        print(f"🔨 Compiling test '{self.test_name}' with Verilator...")

        # Build command
        cmd = ["verilator"]

        # Add common flags
        cmd.extend(self.verilator_config.get('common_flags', []))

        # Add test-specific flags
        cmd.extend(self.test_config.get('verilator_extra_flags', []))

        # Add output directory
        cmd.extend(["-Mdir", str(self.obj_dir)])

        # Add top module
        cmd.extend(["--top-module", self.top_module])

        # Add RTL search path
        cmd.extend(["-y", str(self.rtl_dir)])

        # Add simulation timeout parameter if specified
        if 'sim_timeout' in self.test_config:
            # Validate timescale consistency and show warnings
            self.validate_timescales()

            # Get effective timescale for this test
            timescale_unit, timescale_precision = self.get_effective_timescale()

            # Convert timeout string to numeric value in timescale units
            sim_timeout_str = self.test_config['sim_timeout']
            sim_timeout_value = parse_sim_timeout(sim_timeout_str, timescale_unit)

            cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")
            print(f"   Simulation timeout: {sim_timeout_str} → {sim_timeout_value} time units (timescale: {timescale_unit}/{timescale_precision})")

        # Add RTL files explicitly (supports subdirectory paths like tx/tx_ffe.sv)
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

    def run_simulation(self):
        """Execute the simulation"""
        print(f"🚀 Running simulation for '{self.test_name}'...")

        if not self.executable.exists():
            print(f"✗ Executable not found: {self.executable}")
            return False

        # Get execution timeout from verilator config (for freeze protection)
        timeout_seconds = None
        if 'execution_timeout' in self.verilator_config:
            timeout_seconds = parse_timeout(self.verilator_config['execution_timeout'])
            print(f"   Execution timeout: {self.verilator_config['execution_timeout']} ({timeout_seconds}s)")

        try:
            # Make sure waves directory exists
            self.waves_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                [str(self.executable)],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )

            print(result.stdout)
            if result.stderr:
                print(result.stderr)

            # Check if VCD file was created
            if self.vcd_file.exists():
                vcd_size = self.vcd_file.stat().st_size
                print(f"✓ Simulation complete (VCD: {vcd_size} bytes)\n")
                return True
            else:
                print("⚠ VCD file not generated (may be normal for some tests)\n")
                return True  # Not necessarily a failure

        except subprocess.TimeoutExpired:
            print(f"✗ Simulation TIMEOUT (exceeded {timeout_seconds}s)")
            print(f"   The testbench may have an infinite loop or insufficient timeout value")
            return False

        except subprocess.CalledProcessError as e:
            print("✗ Simulation FAILED")
            print(f"\nStdout:\n{e.stdout}")
            print(f"\nStderr:\n{e.stderr}")
            return False

    def view_waveform(self):
        """Open GTKWave to view waveform"""
        if not self.vcd_file.exists():
            print(f"✗ VCD file not found: {self.vcd_file}")
            return False

        print(f"📊 Opening GTKWave with {self.vcd_file}...")

        try:
            subprocess.Popen(
                ["gtkwave", str(self.vcd_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓ GTKWave launched\n")
            return True

        except FileNotFoundError:
            print("✗ GTKWave not found. Please install gtkwave.")
            return False

    def run(self, view=False):
        """Run complete test flow for this test"""
        print("=" * 70)
        print(f"  Test: {self.test_name}")
        if 'description' in self.test_config:
            print(f"  Description: {self.test_config['description']}")
        print("=" * 70)
        print()

        # Compile
        if not self.verilate():
            return False

        # Simulate
        if not self.run_simulation():
            return False

        # View waveform if requested
        if view and self.vcd_file.exists():
            self.view_waveform()

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Run SystemVerilog tests with Verilator (YAML-based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all enabled tests
  python3 run_test.py --all

  # Run specific test
  python3 run_test.py --test counter --view

  # List available tests
  python3 run_test.py --list

  # Use custom config file
  python3 run_test.py --config my_tests.yaml --test counter
        """
    )

    parser.add_argument(
        "--config",
        default="tests/test_config.yaml",
        help="Path to YAML config file (default: tests/test_config.yaml)"
    )
    parser.add_argument(
        "--test",
        help="Run specific test by name"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all enabled tests"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available tests"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean simulation artifacts before running"
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only clean artifacts, don't run tests"
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="Open GTKWave after simulation"
    )

    args = parser.parse_args()

    # Get project root
    project_root = Path(__file__).parent.parent

    # Load configuration
    try:
        config = TestConfig(project_root / args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except yaml.YAMLError as e:
        print(f"Error parsing YAML config: {e}")
        return 1

    # List tests
    if args.list:
        print("\nAvailable tests:")
        print("-" * 60)
        for test in config.tests:
            status = "✓" if test.get('enabled', True) else "✗"
            name = test['name']
            desc = test.get('description', 'No description')
            print(f"  {status} {name:20s} - {desc}")
        print()
        return 0

    # Determine which tests to run
    if args.test:
        # Run specific test
        test_config = config.get_test(args.test)
        if not test_config:
            print(f"Error: Test '{args.test}' not found")
            print(f"Available tests: {', '.join(config.list_tests())}")
            return 1

        if not test_config.get('enabled', True):
            print(f"Warning: Test '{args.test}' is disabled in config")

        tests_to_run = [test_config]

    elif args.all:
        # Run all enabled tests
        tests_to_run = config.get_enabled_tests()
        if not tests_to_run:
            print("No enabled tests found in config")
            return 1

    else:
        # Default: run all enabled tests
        tests_to_run = config.get_enabled_tests()
        if not tests_to_run:
            print("No enabled tests found in config")
            print("Use --list to see available tests")
            return 1

    # Execute tests
    results = {}
    for test_config in tests_to_run:
        runner = TestRunner(
            project_root=project_root,
            project_config=config.project,
            verilator_config=config.verilator,
            test_config=test_config
        )

        # Clean if requested
        if args.clean or args.clean_only:
            runner.clean()

        # Skip running if clean-only
        if args.clean_only:
            continue

        # Run test
        success = runner.run(view=args.view)
        results[test_config['name']] = success

    # Print summary
    if not args.clean_only and results:
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)

        for test_name, success in results.items():
            status = "✓ PASSED" if success else "✗ FAILED"
            print(f"  {test_name:30s} {status}")

        print("-" * 70)
        print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")
        print("=" * 70)

        return 0 if failed == 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
