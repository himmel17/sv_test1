#!/usr/bin/env python3
"""
Flicker (1/f) Noise Generator - Batch Mode (Method 2)

Generates 4096 flicker noise samples using the Voss-McCartney algorithm and saves
them to a binary file for DPI-C loading. This implements Method 2 from
dpi/batch_implementation_notes.md.

Key Differences from Streaming Version (generate_flicker_noise.py):
- Sample count: 4096 (vs 1024 for streaming)
- Output: Binary file (dpi/flicker_noise_batch.bin) for DPI-C loading
- Purpose: Exact sample-by-sample matching with SystemVerilog

Author: Generated for SerDes flicker noise PoC - Batch Mode
"""

import random
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Algorithm parameters
N_SOURCES = 10          # Number of noise sources (covers ~100kHz to 50MHz range)
SEED = 42               # Fixed seed for deterministic generation
TARGET_RMS = 0.25       # Target noise RMS (±5% of 5V output)
SAMPLES = 4096          # Changed from 1024 - larger for batch mode demonstration
SAMPLE_RATE = 100e6     # 100 MHz sampling rate


def voss_mccartney_noise(n_samples, n_sources=10, seed=42):
    """
    Generate 1/f (flicker) noise using Voss-McCartney algorithm.

    The algorithm uses N binary random sources, each updated at a different rate:
    - Source 0: Updated every sample (every 2^0 = 1 samples)
    - Source 1: Updated every 2^1 = 2 samples
    - Source 2: Updated every 2^2 = 4 samples
    - ...
    - Source i: Updated every 2^i samples

    The different update rates create a power spectrum where low frequencies
    have more power than high frequencies, approximating 1/f behavior.

    Args:
        n_samples: Number of samples to generate (should be power of 2 for FFT)
        n_sources: Number of binary noise sources (10-16 typical)
        seed: Random seed for reproducibility

    Returns:
        numpy.ndarray: Noise samples with approximate 1/f spectrum and TARGET_RMS
    """
    random.seed(seed)

    # Initialize N noise sources with random values
    sources = [random.uniform(-1, 1) for _ in range(n_sources)]
    noise = []

    for i in range(n_samples):
        # Update sources based on update pattern
        for j in range(n_sources):
            if i % (2**j) == 0:
                sources[j] = random.uniform(-1, 1)

        # Sum all sources
        sample = sum(sources)
        noise.append(sample)

    # Convert to numpy array
    noise = np.array(noise)

    # Normalize: remove DC, scale to target RMS
    noise = noise - np.mean(noise)
    current_rms = np.sqrt(np.mean(noise**2))

    if current_rms > 0:
        noise = noise * (TARGET_RMS / current_rms)

    return noise


def analyze_spectrum(noise, sample_rate, save_path='flicker_noise_batch_spectrum.png'):
    """
    Compute and plot power spectral density showing 1/f characteristic.

    Args:
        noise: Noise samples
        sample_rate: Sampling rate in Hz
        save_path: Output PNG file path

    Returns:
        tuple: (frequencies, psd, slope) where slope should be ≈ -1
    """
    # Remove DC component
    noise_ac = noise - np.mean(noise)

    # Apply Hann window to reduce spectral leakage
    window = np.hanning(len(noise_ac))
    noise_windowed = noise_ac * window

    # Compute FFT
    fft_result = np.fft.fft(noise_windowed)
    frequencies = np.fft.fftfreq(len(noise_windowed), 1/sample_rate)

    # Compute power spectral density (positive frequencies only)
    psd = np.abs(fft_result[:len(fft_result)//2])**2
    freqs_positive = frequencies[:len(frequencies)//2]

    # Log-log plot to visualize 1/f
    # Skip DC (f=0) and very low frequencies
    valid_idx = freqs_positive > (sample_rate / len(noise_ac))
    freqs_log = freqs_positive[valid_idx]
    psd_log = psd[valid_idx]

    # Fit line in log-log space to extract slope
    log_freqs = np.log10(freqs_log)
    log_psd = np.log10(psd_log)
    slope, intercept = np.polyfit(log_freqs, log_psd, 1)

    # Plot
    plt.figure(figsize=(10, 6))
    plt.loglog(freqs_log, psd_log, 'b-', label='Measured PSD', alpha=0.7, linewidth=1.5)
    plt.loglog(freqs_log, 10**(slope*log_freqs + intercept),
               'r--', label=f'Fitted slope: {slope:.2f}', linewidth=2)

    # Reference 1/f line
    ref_slope = -1.0
    ref_intercept = intercept + (slope - ref_slope) * np.mean(log_freqs)
    plt.loglog(freqs_log, 10**(ref_slope*log_freqs + ref_intercept),
               'g:', label='Ideal 1/f (slope=-1.0)', linewidth=2, alpha=0.7)

    plt.xlabel('Frequency (Hz)', fontsize=12)
    plt.ylabel('Power Spectral Density', fontsize=12)
    plt.title(f'Flicker Noise Spectrum (Batch Mode) - Voss-McCartney Algorithm\n'
              f'N={N_SOURCES} sources, {SAMPLES} samples @ {sample_rate/1e6:.0f} MHz',
              fontsize=14)
    plt.grid(True, which='both', alpha=0.3)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()

    return freqs_log, psd_log, slope


def compute_raw_rms(n_samples, n_sources, seed):
    """
    Compute raw RMS (before normalization) for empirical scaling factor.

    This value is needed for the C implementation to scale output correctly.

    Args:
        n_samples: Number of samples
        n_sources: Number of noise sources
        seed: Random seed

    Returns:
        float: Raw RMS value
    """
    random.seed(seed)
    sources = [random.uniform(-1, 1) for _ in range(n_sources)]
    noise = []

    for i in range(n_samples):
        for j in range(n_sources):
            if i % (2**j) == 0:
                sources[j] = random.uniform(-1, 1)
        noise.append(sum(sources))

    noise = np.array(noise)
    noise_ac = noise - np.mean(noise)
    raw_rms = np.sqrt(np.mean(noise_ac**2))

    return raw_rms


def save_binary(noise, filepath='dpi/flicker_noise_batch.bin'):
    """
    Save noise samples to binary file for DPI-C loading (Method 2).

    Binary Format:
    - Data type: IEEE 754 double precision (float64)
    - Byte order: Native (little-endian on x86/ARM)
    - Size: N samples × 8 bytes/sample
    - No header, just raw double array

    Args:
        noise: Noise samples (numpy array)
        filepath: Output binary file path

    Returns:
        int: Number of bytes written
    """
    # Convert to Path object for easier file size retrieval
    filepath = Path(filepath)

    # Save as binary (IEEE 754 double precision)
    noise.astype(np.float64).tofile(str(filepath))

    # Get file size
    file_size = filepath.stat().st_size

    print(f"      Binary saved: {filepath}")
    print(f"      File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    print(f"      Format: IEEE 754 double precision (8 bytes/sample)")

    return file_size


def main():
    """Main execution: generate noise, analyze spectrum, save reference data."""
    print("=" * 70)
    print("Flicker Noise Generation - Batch Mode (Method 2)")
    print("=" * 70)
    print(f"Algorithm: Voss-McCartney")
    print(f"Parameters:")
    print(f"  N_SOURCES    : {N_SOURCES}")
    print(f"  SEED         : {SEED}")
    print(f"  TARGET_RMS   : {TARGET_RMS}")
    print(f"  SAMPLES      : {SAMPLES} (4x larger than streaming)")
    print(f"  SAMPLE_RATE  : {SAMPLE_RATE/1e6:.0f} MHz")
    print(f"  Sim Time     : {SAMPLES/(SAMPLE_RATE/1e6):.2f} us")
    print("=" * 70)

    # Compute raw RMS for C implementation reference
    raw_rms = compute_raw_rms(SAMPLES, N_SOURCES, SEED)
    print(f"\n[INFO] Raw RMS (before normalization): {raw_rms:.6f}")
    print(f"       Use this value in C code: raw_rms = {raw_rms:.4f}")

    # Generate noise
    print(f"\n[1/5] Generating {SAMPLES} noise samples...")
    noise = voss_mccartney_noise(SAMPLES, N_SOURCES, SEED)

    # Compute statistics
    rms = np.sqrt(np.mean(noise**2))
    peak_to_peak = np.max(noise) - np.min(noise)
    mean_val = np.mean(noise)

    print(f"[2/5] Computing statistics...")
    print(f"      Mean         : {mean_val:.6f} (should be ~0)")
    print(f"      RMS          : {rms:.6f} (target: {TARGET_RMS:.6f})")
    print(f"      Peak-to-peak : {peak_to_peak:.6f}")
    print(f"      Min/Max      : {np.min(noise):.6f} / {np.max(noise):.6f}")

    # Analyze spectrum
    print(f"[3/5] Analyzing spectrum...")
    freqs, psd, slope = analyze_spectrum(noise, SAMPLE_RATE, save_path='scripts/flicker_noise_batch_spectrum.png')
    print(f"      Spectral slope: {slope:.3f} (target: -1.0 for 1/f)")
    print(f"      Frequency range: {freqs[0]/1e3:.1f} kHz to {freqs[-1]/1e6:.1f} MHz")

    if -1.2 < slope < -0.8:
        print(f"      ✓ PASS: Slope indicates 1/f characteristic")
        slope_pass = True
    else:
        print(f"      ✗ WARNING: Slope deviates from expected 1/f")
        slope_pass = False

    # Save reference data
    print(f"[4/5] Saving reference data...")

    # Save NumPy array for Python verification (in scripts/ directory)
    np.save('scripts/flicker_noise_batch_reference.npy', noise)
    print(f"      NumPy reference saved: scripts/flicker_noise_batch_reference.npy")

    # Save spectrum plot (already saved in scripts/ directory by analyze_spectrum)
    print(f"      Spectrum plot saved: scripts/flicker_noise_batch_spectrum.png")

    # Save binary for DPI-C loading (Method 2)
    print(f"[5/5] Saving binary for DPI-C (Method 2)...")
    binary_size = save_binary(noise, 'dpi/flicker_noise_batch.bin')

    # Verify binary size
    expected_size = SAMPLES * 8  # 8 bytes per double
    if binary_size == expected_size:
        print(f"      ✓ Binary size correct: {binary_size} == {expected_size}")
    else:
        print(f"      ✗ WARNING: Binary size mismatch: {binary_size} != {expected_size}")

    # Final summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"RMS Error        : {abs(rms - TARGET_RMS)/TARGET_RMS * 100:.2f}%")
    print(f"Spectral Slope   : {slope:.3f}")
    print(f"Binary File      : dpi/flicker_noise_batch.bin ({binary_size:,} bytes)")
    print(f"Status           : {'PASS' if slope_pass else 'WARNING'}")
    print("=" * 70)
    print("")
    print("Next Steps:")
    print("  1. Run simulation:")
    print("     uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch")
    print("  2. Verify exact match:")
    print("     uv run python3 scripts/verify_noise_match_batch.py")
    print("  3. Check output files:")
    print("     - Reference: scripts/flicker_noise_batch_reference.npy")
    print("     - Spectrum:  scripts/flicker_noise_batch_spectrum.png")
    print("     - Log file:  scripts/flicker_noise_batch_verification.log")
    print("=" * 70)

    return 0 if slope_pass else 1


if __name__ == "__main__":
    exit(main())
