#!/usr/bin/env python3
"""
Waveform Reader for Verification Scripts (VCD / FST)

The test framework writes sim/waves/{test_name}.vcd or .fst depending on the
Verilator trace flag (--trace / --trace-fst) or the per-test wave_format key.
Before each simulation, the waveform of the other format is removed, so
normally only one of them exists.

This module locates that file and reads signals with pywellen, which supports
both VCD and FST through the same API.
"""

from pathlib import Path

import pywellen

# Search order when both formats exist is decided by modification time
WAVE_EXTENSIONS = ('.fst', '.vcd')


def find_wave_file(test_name, waves_dir='sim/waves'):
    """
    Locate the waveform file of a test (.fst or .vcd).

    If both exist (e.g. created manually), the newer one is used with a warning.

    Args:
        test_name: Test name in tests/test_config.yaml
        waves_dir: Waveform directory

    Returns:
        Path or None: Waveform file path, or None if not found
    """
    candidates = [Path(waves_dir) / f"{test_name}{ext}" for ext in WAVE_EXTENSIONS]
    existing = [p for p in candidates if p.exists()]

    if not existing:
        return None

    if len(existing) > 1:
        newest = max(existing, key=lambda p: p.stat().st_mtime)
        print(f"WARNING: Both {existing[0].name} and {existing[1].name} exist; "
              f"using the newer one: {newest}")
        return newest

    return existing[0]


def read_signals(wave_path, signal_names):
    """
    Read value changes of signals from a VCD or FST file.

    Args:
        wave_path: Path to VCD or FST file
        signal_names: Full hierarchical names (e.g. 'top_tb.amp_out')

    Returns:
        dict: {name: [(time, value), ...]} in time order

    Raises:
        KeyError: If a signal is not found (message lists available signals)
    """
    waveform = pywellen.Waveform(str(wave_path))
    variables = {var.full_name: var for var in waveform.all_vars()}

    missing = [name for name in signal_names if name not in variables]
    if missing:
        available = '\n'.join(f"  - {name}" for name in variables)
        raise KeyError(f"Signal not found: {', '.join(missing)}\nAvailable signals:\n{available}")

    result = {}
    for name in signal_names:
        signal = variables[name].signal
        result[name] = [signal[i] for i in range(len(signal))]

    return result
