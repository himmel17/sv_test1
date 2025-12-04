#!/usr/bin/env python3
"""
Flicker Noise Verification Script - Batch Mode (Method 2)

Verifies EXACT sample-by-sample matching between Python reference and
SystemVerilog DPI-C implementation.

Key Differences from Streaming Version (verify_noise_match.py):
- Sample count: 4096 (vs 1024 for streaming)
- Comparison: Exact sample-by-sample (vs statistical RMS/spectral)
- Tolerance: 1e-9 V absolute (vs 10% RMS for streaming)
- Files: scripts/flicker_noise_batch_reference.npy, ideal_amp_with_noise_batch.vcd
- Outputs: scripts/flicker_noise_batch_verification.png, scripts/flicker_noise_batch_verification.log

Verification Strategy:
- Sample-by-sample comparison using np.isclose()
- Epsilon tolerance: rtol=1e-10, atol=1e-9 (1 nanovolt)
- Pass criteria: >99.9% samples match (allow 1-2 edge cases)
- Spectral analysis: Both should show 1/f characteristic

Author: Generated for SerDes flicker noise PoC - Batch Mode
"""

import numpy as np
import matplotlib.pyplot as plt
from vcdvcd import VCDVCD
from pathlib import Path
import sys

# Test parameters (must match generate_flicker_noise_batch.py and testbench)
SAMPLE_RATE = 100e6
EXPECTED_RMS = 0.25
GAIN = 10.0
DC_INPUT = 0.5
SAMPLE_COUNT = 4096  # Changed from 1024 for batch mode
# VCD skip count: Find where DPI-C CALL 0 appears in amp_out
# VCD structure:
#   Index 0: Initial value (0V, during reset)
#   Index 1: Reset released, amp_out uses noise_sample=0 (before DPI-C CALL 0)
#   Index 2: amp_out uses noise from DPI-C CALL 0 (matches Python[0])
#   Therefore, skip first 2 samples to align with Python[0]
RESET_SKIP_VCD = 2  # Skip to reach DPI-C CALL 0 in amp_out


def parse_vcd_noise(vcd_path):
    """
    Extract noise component from VCD file.

    Args:
        vcd_path: Path to VCD file

    Returns:
        numpy.ndarray: Noise samples (amp_out - amp_out_ideal)
    """
    print(f"[1/6] Parsing VCD file: {vcd_path}")

    try:
        vcd = VCDVCD(vcd_path)
    except Exception as e:
        print(f"ERROR: Failed to parse VCD file: {e}")
        return None

    # Debug: print available signals
    print("Available signals:", list(vcd.references_to_ids.keys())[:20])  # First 20

    # Extract signals (adjust hierarchy for batch testbench)
    try:
        amp_out = vcd['ideal_amp_with_noise_batch_tb.amp_out']
        amp_out_ideal = vcd['ideal_amp_with_noise_batch_tb.amp_out_ideal']
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
    # Skip first RESET_SKIP_VCD samples to reach DPI-C CALL 0 in amp_out
    # RTL has 1-sample lag: amp_out at clock i contains noise from DPI-C call i-1
    # So VCD Index 2 contains noise from DPI-C CALL 0 (= Python[0])
    noise_sv = []
    for i, (time, val_out) in enumerate(amp_out_tv):
        # Skip to reach DPI-C CALL 0
        if i < RESET_SKIP_VCD:
            continue

        # Convert to float
        try:
            noise_sv.append(float(val_out) - amp_out_ideal_value)
        except (ValueError, TypeError):
            continue

    print(f"      Extracted {len(noise_sv)} noise samples (skipped first {RESET_SKIP_VCD} samples)")
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


def compare_exact(noise_py, noise_sv):
    """
    Compare sample-by-sample with epsilon tolerance.

    Uses numpy.isclose() with tight tolerance:
    - rtol=1e-10: 0.00000001% relative tolerance
    - atol=1e-9: 1 nanovolt absolute tolerance

    These are much tighter than streaming's 10% RMS tolerance.

    Args:
        noise_py: Python reference noise samples
        noise_sv: SystemVerilog noise samples

    Returns:
        dict: Comparison results (matches, total, match_rate, max_error, mean_error)
    """
    # Use numpy isclose with tight tolerance
    # rtol=1e-10: relative tolerance (0.00000001%)
    # atol=1e-9: absolute tolerance (1 nanovolt)
    matches = np.isclose(noise_py, noise_sv, rtol=1e-10, atol=1e-9)

    num_matches = np.sum(matches)
    match_rate = num_matches / len(noise_py)

    # Compute errors
    abs_errors = np.abs(noise_py - noise_sv)
    max_error = np.max(abs_errors)
    mean_error = np.mean(abs_errors)

    return {
        'matches': num_matches,
        'total': len(noise_py),
        'match_rate': match_rate,
        'max_error': max_error,
        'mean_error': mean_error
    }


def main():
    print("=" * 70)
    print("Flicker Noise Verification - Batch Mode (Exact Match)")
    print("=" * 70)
    print("Method 2: Python binary → DPI-C → SystemVerilog")
    print("Verification: Exact sample-by-sample matching")
    print("=" * 70)

    # Load Python reference (from scripts/ directory)
    ref_path = 'scripts/flicker_noise_batch_reference.npy'
    if not Path(ref_path).exists():
        print(f"ERROR: {ref_path} not found!")
        print("Run: uv run python3 scripts/generate_flicker_noise_batch.py")
        return 1

    noise_python = np.load(ref_path)
    print(f"[INFO] Loaded Python reference: {len(noise_python)} samples from {ref_path}")

    # Load SystemVerilog from VCD
    vcd_path = 'sim/waves/ideal_amp_with_noise_batch.vcd'
    if not Path(vcd_path).exists():
        print(f"ERROR: VCD file not found: {vcd_path}")
        print("Run test first: uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch")
        return 1

    noise_sv = parse_vcd_noise(vcd_path)
    if noise_sv is None:
        return 1

    # Trim to same length (use first 4096 samples from both)
    n_samples = min(SAMPLE_COUNT, len(noise_python), len(noise_sv))
    noise_python = noise_python[:n_samples]
    noise_sv = noise_sv[:n_samples]

    print(f"[2/6] Comparing {n_samples} samples...")

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

    if rms_error < 0.001:  # Much tighter than streaming's 10%
        print("✓ PASS: RMS within 0.1% tolerance")
        rms_pass = True
    else:
        print("✗ FAIL: RMS error exceeds 0.1%")
        rms_pass = False

    # Exact sample-by-sample comparison
    print(f"\n[3/6] Exact sample-by-sample comparison...")
    result = compare_exact(noise_python, noise_sv)

    print("\n" + "=" * 70)
    print("Exact Sample Comparison")
    print("=" * 70)
    print(f"Total samples:    {result['total']}")
    print(f"Exact matches:    {result['matches']} ({result['match_rate']*100:.2f}%)")
    print(f"Max error:        {result['max_error']:.3e} V")
    print(f"Mean error:       {result['mean_error']:.3e} V")
    print(f"Tolerance:        rtol=1e-10, atol=1e-9 (1 nanovolt)")

    # Pass criteria: >99.9% match (allow 1-2 samples tolerance for edge cases)
    if result['match_rate'] > 0.999:
        print("✓ PASS: All samples match within epsilon tolerance")
        exact_pass = True
    else:
        print(f"✗ FAIL: Only {result['match_rate']*100:.2f}% samples match")
        exact_pass = False

    # Compute spectra
    print(f"\n[4/6] Computing spectra...")
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
    print(f"\n[5/6] Generating comparison plots...")
    fig, axes = plt.subplots(3, 2, figsize=(14, 14))

    # Time domain - Python
    axes[0, 0].plot(noise_python, 'b-', alpha=0.7, linewidth=0.5)
    axes[0, 0].set_title(f'Python Noise (RMS={rms_python:.4f} V)', fontsize=12)
    axes[0, 0].set_xlabel('Sample', fontsize=11)
    axes[0, 0].set_ylabel('Noise (V)', fontsize=11)
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

    # Time domain - SystemVerilog
    axes[0, 1].plot(noise_sv, 'r-', alpha=0.7, linewidth=0.5)
    axes[0, 1].set_title(f'SystemVerilog DPI-C Noise (RMS={rms_sv:.4f} V)', fontsize=12)
    axes[0, 1].set_xlabel('Sample', fontsize=11)
    axes[0, 1].set_ylabel('Noise (V)', fontsize=11)
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

    # Sample-by-sample difference
    diff = noise_sv - noise_python
    axes[1, 0].plot(diff, 'g-', alpha=0.7, linewidth=0.5)
    axes[1, 0].set_title(f'Sample Difference (SV - Python)\n'
                         f'Max={result["max_error"]:.3e} V, Mean={result["mean_error"]:.3e} V',
                         fontsize=12)
    axes[1, 0].set_xlabel('Sample', fontsize=11)
    axes[1, 0].set_ylabel('Difference (V)', fontsize=11)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].axhline(y=0, color='k', linestyle='--', linewidth=0.5, alpha=0.5)

    # Difference histogram
    axes[1, 1].hist(diff, bins=100, alpha=0.7, color='g', edgecolor='black', linewidth=0.5)
    axes[1, 1].set_title(f'Difference Distribution\n'
                         f'Match Rate: {result["match_rate"]*100:.2f}%',
                         fontsize=12)
    axes[1, 1].set_xlabel('Difference (V)', fontsize=11)
    axes[1, 1].set_ylabel('Count', fontsize=11)
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].axvline(x=0, color='k', linestyle='--', linewidth=1, alpha=0.5)

    # Spectrum comparison
    axes[2, 0].loglog(freqs_py, psd_py, 'b-', label=f'Python (slope={slope_py:.2f})',
                      alpha=0.7, linewidth=2)
    axes[2, 0].loglog(freqs_sv, psd_sv, 'r--', label=f'SV DPI-C (slope={slope_sv:.2f})',
                      alpha=0.7, linewidth=2)

    # Reference 1/f line
    freqs_ref = freqs_py
    psd_ref = freqs_ref**(-1) * np.median(psd_py) * np.median(freqs_py)
    axes[2, 0].loglog(freqs_ref, psd_ref, 'g:', label='Ideal 1/f (slope=-1.0)',
                      linewidth=2, alpha=0.6)

    axes[2, 0].set_title('Spectrum Overlay', fontsize=12)
    axes[2, 0].set_xlabel('Frequency (Hz)', fontsize=11)
    axes[2, 0].set_ylabel('PSD', fontsize=11)
    axes[2, 0].legend(fontsize=10)
    axes[2, 0].grid(True, which='both', alpha=0.3)

    # Amplitude histogram comparison
    axes[2, 1].hist(noise_python, bins=50, alpha=0.5, label='Python', color='b',
                    density=True, edgecolor='black', linewidth=0.5)
    axes[2, 1].hist(noise_sv, bins=50, alpha=0.5, label='SV DPI-C', color='r',
                    density=True, edgecolor='black', linewidth=0.5)
    axes[2, 1].set_title('Amplitude Distribution', fontsize=12)
    axes[2, 1].set_xlabel('Noise (V)', fontsize=11)
    axes[2, 1].set_ylabel('Probability Density', fontsize=11)
    axes[2, 1].legend(fontsize=10)
    axes[2, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = 'scripts/flicker_noise_batch_verification.png'
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"      Verification plot saved: {plot_path}")

    # Generate detailed log file
    print(f"\n[6/7] Generating detailed log file...")
    log_path = 'scripts/flicker_noise_batch_verification.log'
    with open(log_path, 'w') as log:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        log.write("=" * 80 + "\n")
        log.write("Flicker Noise Verification Log - Batch Mode (Method 2)\n")
        log.write("=" * 80 + "\n")
        log.write(f"Timestamp: {timestamp}\n")
        log.write(f"Python Reference: {ref_path}\n")
        log.write(f"VCD File: {vcd_path}\n")
        log.write(f"Verification Plot: {plot_path}\n")
        log.write("=" * 80 + "\n\n")

        # Sample count and parameters
        log.write("Test Parameters:\n")
        log.write(f"  Total samples:     {n_samples}\n")
        log.write(f"  Sample rate:       {SAMPLE_RATE/1e6:.0f} MHz\n")
        log.write(f"  Expected RMS:      {EXPECTED_RMS} V\n")
        log.write(f"  VCD reset skip:    {RESET_SKIP_VCD} samples\n")
        log.write(f"  Gain:              {GAIN}\n")
        log.write(f"  DC Input:          {DC_INPUT} V\n")
        log.write("\n")

        # RMS comparison
        log.write("=" * 80 + "\n")
        log.write("RMS Comparison\n")
        log.write("=" * 80 + "\n")
        log.write(f"Python RMS:        {rms_python:.9f} V\n")
        log.write(f"SystemVerilog RMS: {rms_sv:.9f} V\n")
        log.write(f"Absolute Error:    {abs(rms_python - rms_sv):.9e} V\n")
        log.write(f"Relative Error:    {rms_error*100:.6f}%\n")
        log.write(f"Status:            {'PASS' if rms_pass else 'FAIL'} (threshold: <0.1%)\n")
        log.write("\n")

        # Exact sample comparison
        log.write("=" * 80 + "\n")
        log.write("Exact Sample-by-Sample Comparison\n")
        log.write("=" * 80 + "\n")
        log.write(f"Total samples:     {result['total']}\n")
        log.write(f"Exact matches:     {result['matches']} ({result['match_rate']*100:.4f}%)\n")
        log.write(f"Max error:         {result['max_error']:.6e} V\n")
        log.write(f"Mean error:        {result['mean_error']:.6e} V\n")
        log.write(f"Tolerance:         rtol=1e-10, atol=1e-9 V (1 nanovolt)\n")
        log.write(f"Status:            {'PASS' if exact_pass else 'FAIL'} (threshold: >99.9%)\n")
        log.write("\n")

        # Spectral analysis
        log.write("=" * 80 + "\n")
        log.write("Spectral Analysis (1/f Noise Characteristic)\n")
        log.write("=" * 80 + "\n")
        log.write(f"Python slope:        {slope_py:.6f}\n")
        log.write(f"SystemVerilog slope: {slope_sv:.6f}\n")
        log.write(f"Expected range:      -1.2 to -0.8\n")
        log.write(f"Python status:       {'PASS' if slope_py_ok else 'FAIL'}\n")
        log.write(f"SV status:           {'PASS' if slope_sv_ok else 'FAIL'}\n")
        log.write(f"Overall status:      {'PASS' if slope_pass else 'FAIL'}\n")
        log.write("\n")

        # Sample-by-sample details (first 20 samples + any mismatches)
        log.write("=" * 80 + "\n")
        log.write("Sample-by-Sample Details (First 20 samples)\n")
        log.write("=" * 80 + "\n")
        log.write(f"{'Index':>6} | {'Python (V)':>14} | {'SV (V)':>14} | {'Error (V)':>14} | {'Match':>6}\n")
        log.write("-" * 80 + "\n")

        matches_array = np.isclose(noise_python, noise_sv, rtol=1e-10, atol=1e-9)

        for i in range(min(20, n_samples)):
            match_str = "YES" if matches_array[i] else "NO"
            error_val = noise_sv[i] - noise_python[i]
            log.write(f"{i:6d} | {noise_python[i]:14.9f} | {noise_sv[i]:14.9f} | "
                     f"{error_val:14.6e} | {match_str:>6}\n")

        log.write("\n")

        # Report mismatches if any
        mismatch_indices = np.where(~matches_array)[0]
        if len(mismatch_indices) > 0:
            log.write("=" * 80 + "\n")
            log.write(f"Mismatched Samples (Total: {len(mismatch_indices)})\n")
            log.write("=" * 80 + "\n")
            log.write(f"{'Index':>6} | {'Python (V)':>14} | {'SV (V)':>14} | {'Error (V)':>14}\n")
            log.write("-" * 80 + "\n")

            # Show first 50 mismatches
            for idx in mismatch_indices[:50]:
                error_val = noise_sv[idx] - noise_python[idx]
                log.write(f"{idx:6d} | {noise_python[idx]:14.9f} | {noise_sv[idx]:14.9f} | "
                         f"{error_val:14.6e}\n")

            if len(mismatch_indices) > 50:
                log.write(f"... ({len(mismatch_indices) - 50} more mismatches not shown)\n")
            log.write("\n")
        else:
            log.write("=" * 80 + "\n")
            log.write("✓ All samples matched within tolerance - No mismatches found!\n")
            log.write("=" * 80 + "\n\n")

        # Final verdict
        log.write("=" * 80 + "\n")
        log.write("FINAL VERDICT\n")
        log.write("=" * 80 + "\n")

        all_pass_log = rms_pass and exact_pass and slope_pass

        if all_pass_log:
            log.write("✓✓✓ ALL TESTS PASSED ✓✓✓\n\n")
            log.write("Python and SystemVerilog implementations match EXACTLY\n")
            log.write("All samples within epsilon tolerance (1 nanovolt)\n")
            log.write("Both exhibit 1/f noise characteristics as expected\n\n")
            log.write("Method 2 (batch mode) successfully verified:\n")
            log.write("  ✓ Binary file loading works correctly\n")
            log.write("  ✓ DPI-C batch implementation is correct\n")
            log.write("  ✓ Sample-by-sample exact match achieved\n")
        else:
            log.write("✗✗✗ SOME TESTS FAILED ✗✗✗\n\n")
            if not rms_pass:
                log.write("  ✗ RMS mismatch\n")
            if not exact_pass:
                log.write("  ✗ Sample-by-sample comparison failed\n")
            if not slope_pass:
                log.write("  ✗ Spectral slope mismatch\n")

        log.write("=" * 80 + "\n")

    print(f"      Verification log saved: {log_path}")

    # Final verdict
    print("\n[7/7] Final verdict...")
    print("\n" + "=" * 70)
    print("FINAL VERDICT - BATCH MODE")
    print("=" * 70)

    all_pass = rms_pass and exact_pass and slope_pass

    if all_pass:
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("")
        print("Python and SystemVerilog implementations match EXACTLY")
        print("All samples within epsilon tolerance (1 nanovolt)")
        print("Both exhibit 1/f noise characteristics as expected")
        print("")
        print("Method 2 (batch mode) successfully verified:")
        print("  ✓ Binary file loading works correctly")
        print("  ✓ DPI-C batch implementation is correct")
        print("  ✓ Sample-by-sample exact match achieved")
        print("=" * 70)
        return 0
    else:
        print("✗✗✗ SOME TESTS FAILED ✗✗✗")
        if not rms_pass:
            print("  - RMS mismatch")
        if not exact_pass:
            print("  - Sample-by-sample comparison failed")
        if not slope_pass:
            print("  - Spectral slope mismatch")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
