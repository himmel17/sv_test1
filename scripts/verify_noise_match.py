#!/usr/bin/env python3
"""
Flicker Noise Verification Script

Compares Python reference implementation vs SystemVerilog DPI-C implementation:
1. Parse VCD file to extract noise samples
2. Compute spectrum for both datasets
3. Compare RMS and spectral slope
4. Generate comparison plots

Verification Strategy:
- Statistical comparison (not sample-by-sample due to different RNGs)
- RMS error < 10% tolerance
- Spectral slope ≈ -1 ± 0.2 for both
- Visual inspection of spectral shape

Author: Generated for SerDes flicker noise PoC
"""

import numpy as np
import matplotlib.pyplot as plt
from vcdvcd import VCDVCD
from pathlib import Path
import sys

# Test parameters (must match generate_flicker_noise.py and testbench)
SAMPLE_RATE = 100e6
EXPECTED_RMS = 0.25
GAIN = 10.0
DC_INPUT = 0.5
# VCD skip count: accounts for reset period only (10 clocks)
# This ensures we compare sample_counter 0-1023 for both Python and SystemVerilog
RESET_SKIP_VCD = 10  # Skip reset period to reach valid data


def parse_vcd_noise(vcd_path):
    """
    Extract noise component from VCD file.

    Args:
        vcd_path: Path to VCD file

    Returns:
        numpy.ndarray: Noise samples (amp_out - amp_out_ideal)
    """
    print(f"[1/5] Parsing VCD file: {vcd_path}")

    try:
        vcd = VCDVCD(vcd_path)
    except Exception as e:
        print(f"ERROR: Failed to parse VCD file: {e}")
        return None

    # Debug: print available signals
    print("Available signals:", list(vcd.references_to_ids.keys())[:20])  # First 20

    # Extract signals (adjust hierarchy as needed)
    try:
        amp_out = vcd['ideal_amp_with_noise_tb.amp_out']
        amp_out_ideal = vcd['ideal_amp_with_noise_tb.amp_out_ideal']
    except KeyError as e:
        print(f"ERROR: Signal not found in VCD: {e}")
        print("Available signals:")
        for sig in vcd.references_to_ids.keys():
            print(f"  - {sig}")
        return None

    # Get time-series data
    amp_out_tv = amp_out.tv
    amp_out_ideal_tv = amp_out_ideal.tv

    # amp_out_ideal may be constant (DC value), so get its value
    if len(amp_out_ideal_tv) > 0:
        amp_out_ideal_value = float(amp_out_ideal_tv[-1][1])  # Use last (or only) value
    else:
        print("ERROR: amp_out_ideal has no values")
        return None

    print(f"      amp_out_ideal = {amp_out_ideal_value:.6f} V (constant)")

    # Extract noise: out - out_ideal
    # amp_out_ideal is constant (DC = GAIN × DC_INPUT)
    # Skip first RESET_SKIP_VCD samples to exclude reset period
    noise_sv = []
    for i, (time, val_out) in enumerate(amp_out_tv):
        # Skip reset period
        if i < RESET_SKIP_VCD:
            continue

        # Convert to float
        try:
            noise_sv.append(float(val_out) - amp_out_ideal_value)
        except (ValueError, TypeError):
            continue

    print(f"      Extracted {len(noise_sv)} noise samples (skipped first {RESET_SKIP_VCD} reset period samples)")
    return np.array(noise_sv)


def compute_spectrum(noise, sample_rate):
    """
    Compute power spectral density.

    Returns:
        tuple: (frequencies, psd, slope)
    """
    # Remove DC
    noise_ac = noise - np.mean(noise)

    # Window
    window = np.hanning(len(noise_ac))
    noise_windowed = noise_ac * window

    # FFT
    fft_result = np.fft.fft(noise_windowed)
    frequencies = np.fft.fftfreq(len(noise_windowed), 1/sample_rate)

    # PSD (positive frequencies only)
    psd = np.abs(fft_result[:len(fft_result)//2])**2
    freqs_positive = frequencies[:len(frequencies)//2]

    # Fit slope in log-log
    valid_idx = freqs_positive > (sample_rate / len(noise_ac))
    freqs_log = freqs_positive[valid_idx]
    psd_log = psd[valid_idx]

    log_freqs = np.log10(freqs_log)
    log_psd = np.log10(psd_log)
    slope, intercept = np.polyfit(log_freqs, log_psd, 1)

    return freqs_log, psd_log, slope


def main():
    print("=" * 70)
    print("Flicker Noise Verification: Python vs SystemVerilog DPI-C")
    print("=" * 70)

    # Load Python reference (from scripts/ directory)
    ref_path = 'scripts/flicker_noise_reference.npy'
    if not Path(ref_path).exists():
        print(f"ERROR: {ref_path} not found!")
        print("Run: uv run python3 scripts/generate_flicker_noise.py")
        return 1

    noise_python = np.load(ref_path)
    print(f"[INFO] Loaded Python reference: {len(noise_python)} samples from {ref_path}")

    # Load SystemVerilog from VCD
    vcd_path = 'sim/waves/ideal_amp_with_noise.vcd'
    if not Path(vcd_path).exists():
        print(f"ERROR: VCD file not found: {vcd_path}")
        print("Run test first: uv run python3 scripts/run_test.py --test ideal_amp_with_noise")
        return 1

    noise_sv = parse_vcd_noise(vcd_path)
    if noise_sv is None:
        return 1

    # Trim to same length (use first 1024 samples from both)
    n_samples = min(1024, len(noise_python), len(noise_sv))
    noise_python = noise_python[:n_samples]
    noise_sv = noise_sv[:n_samples]

    print(f"[2/5] Comparing {n_samples} samples...")

    # Compute statistics
    rms_python = np.sqrt(np.mean(noise_python**2))
    rms_sv = np.sqrt(np.mean(noise_sv**2))
    rms_error = abs(rms_python - rms_sv) / rms_python

    print("\n" + "=" * 70)
    print("RMS Comparison")
    print("=" * 70)
    print(f"Python RMS:        {rms_python:.6f} V")
    print(f"SystemVerilog RMS: {rms_sv:.6f} V")
    print(f"Relative Error:    {rms_error*100:.2f}%")

    if rms_error < 0.10:
        print("✓ PASS: RMS within 10% tolerance")
        rms_pass = True
    else:
        print("✗ FAIL: RMS error exceeds 10%")
        rms_pass = False

    # Compute spectra
    print(f"\n[3/5] Computing spectra...")
    freqs_py, psd_py, slope_py = compute_spectrum(noise_python, SAMPLE_RATE)
    freqs_sv, psd_sv, slope_sv = compute_spectrum(noise_sv, SAMPLE_RATE)

    print("\n" + "=" * 70)
    print("Spectral Analysis")
    print("=" * 70)
    print(f"Python slope:        {slope_py:.3f}")
    print(f"SystemVerilog slope: {slope_sv:.3f}")
    print(f"Expected slope:      -1.0 ± 0.2")

    slope_py_ok = -1.2 < slope_py < -0.8
    slope_sv_ok = -1.2 < slope_sv < -0.8

    if slope_py_ok and slope_sv_ok:
        print("✓ PASS: Both spectra show 1/f characteristic")
        slope_pass = True
    else:
        print("✗ FAIL: Spectral slopes outside expected range")
        slope_pass = False

    # Plot comparison
    print(f"\n[4/5] Generating comparison plots...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Time domain - Python
    axes[0, 0].plot(noise_python, 'b-', alpha=0.7, linewidth=0.8)
    axes[0, 0].set_title(f'Python Noise (RMS={rms_python:.4f} V)', fontsize=12)
    axes[0, 0].set_xlabel('Sample', fontsize=11)
    axes[0, 0].set_ylabel('Noise (V)', fontsize=11)
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

    # Time domain - SystemVerilog
    axes[0, 1].plot(noise_sv, 'r-', alpha=0.7, linewidth=0.8)
    axes[0, 1].set_title(f'SystemVerilog DPI-C Noise (RMS={rms_sv:.4f} V)', fontsize=12)
    axes[0, 1].set_xlabel('Sample', fontsize=11)
    axes[0, 1].set_ylabel('Noise (V)', fontsize=11)
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

    # Spectrum comparison
    axes[1, 0].loglog(freqs_py, psd_py, 'b-', label=f'Python (slope={slope_py:.2f})',
                      alpha=0.7, linewidth=2)
    axes[1, 0].loglog(freqs_sv, psd_sv, 'r--', label=f'SV DPI-C (slope={slope_sv:.2f})',
                      alpha=0.7, linewidth=2)

    # Reference 1/f line
    freqs_ref = freqs_py
    psd_ref = freqs_ref**(-1) * np.median(psd_py) * np.median(freqs_py)
    axes[1, 0].loglog(freqs_ref, psd_ref, 'g:', label='Ideal 1/f (slope=-1.0)',
                      linewidth=2, alpha=0.6)

    axes[1, 0].set_title('Spectrum Overlay', fontsize=12)
    axes[1, 0].set_xlabel('Frequency (Hz)', fontsize=11)
    axes[1, 0].set_ylabel('PSD', fontsize=11)
    axes[1, 0].legend(fontsize=10)
    axes[1, 0].grid(True, which='both', alpha=0.3)

    # Histogram comparison
    axes[1, 1].hist(noise_python, bins=50, alpha=0.5, label='Python', color='b',
                    density=True, edgecolor='black', linewidth=0.5)
    axes[1, 1].hist(noise_sv, bins=50, alpha=0.5, label='SV DPI-C', color='r',
                    density=True, edgecolor='black', linewidth=0.5)
    axes[1, 1].set_title('Amplitude Distribution', fontsize=12)
    axes[1, 1].set_xlabel('Noise (V)', fontsize=11)
    axes[1, 1].set_ylabel('Probability Density', fontsize=11)
    axes[1, 1].legend(fontsize=10)
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = 'scripts/flicker_noise_verification.png'
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"      Verification plot saved: {plot_path}")

    # Final verdict
    print("\n[5/5] Final verdict...")
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    if rms_pass and slope_pass:
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("Python and SystemVerilog implementations match statistically")
        print("Both exhibit 1/f noise characteristics as expected")
        print("=" * 70)
        return 0
    else:
        print("✗✗✗ SOME TESTS FAILED ✗✗✗")
        if not rms_pass:
            print("  - RMS mismatch")
        if not slope_pass:
            print("  - Spectral slope mismatch")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
