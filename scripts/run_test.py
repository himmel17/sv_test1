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

# Import simulator abstraction layer
from simulators import SimulatorFactory


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
    """Runs individual test cases using simulator abstraction"""

    def __init__(self, project_root, project_config, test_config, simulator_type=None):
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.test_config = test_config

        # Determine simulator type: CLI override > test config > project default > 'verilator'
        if simulator_type is None:
            simulator_type = test_config.get('simulator') or \
                           project_config.get('default_simulator', 'verilator')

        self.simulator_type = simulator_type

        # Get simulator-specific configuration
        simulators_config = project_config.get('simulators', {})
        if simulator_type in simulators_config:
            sim_config = simulators_config[simulator_type]
        else:
            # Backward compatibility: if no 'simulators' section, try legacy 'verilator' config
            if simulator_type == 'verilator' and 'verilator' in project_config:
                sim_config = project_config['verilator']
            else:
                sim_config = {}

        # Create simulator instance using factory
        self.simulator = SimulatorFactory.create_simulator(
            simulator_type,
            project_root,
            project_config,
            sim_config,
            test_config
        )

        # Test attributes (for reporting)
        self.test_name = test_config['name']
        self.vcd_file = self.simulator.vcd_file

    def clean(self):
        """Clean simulation artifacts for this test"""
        self.simulator.clean()

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
        print(f"  Simulator: {self.simulator_type}")
        print("=" * 70)
        print()

        # Compile
        if not self.simulator.compile():
            return False

        # Simulate
        if not self.simulator.run_simulation():
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
    parser.add_argument(
        "--simulator",
        choices=["verilator", "vcs"],
        help="Override simulator selection (default: from config)"
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
        # Pass full config (including simulators section), not just config.project
        full_config = {
            **config.project,
            'simulators': config.config.get('simulators', {}),
            'verilator': config.config.get('verilator', {})  # Backward compatibility
        }
        runner = TestRunner(
            project_root=project_root,
            project_config=full_config,
            test_config=test_config,
            simulator_type=args.simulator  # CLI override (None if not specified)
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
