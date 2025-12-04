/**
 * dpi_flicker_noise_batch.c - Batch-mode DPI-C Flicker Noise Generator
 *
 * Implements Method 2 from dpi/batch_implementation_notes.md:
 * - Loads pre-generated noise samples from binary file at initialization
 * - Returns samples sequentially on each call
 * - Achieves exact sample-by-sample matching with Python reference
 *
 * Key Differences from Streaming Version (dpi_flicker_noise.c):
 * - Algorithm: Pre-loaded from file (vs computed on-the-fly)
 * - State: 4096-element array + index (vs 10 noise sources + counter)
 * - Memory: ~32 KB (vs ~80 bytes)
 * - Computation: O(1) per call (vs O(10) per call)
 * - Match: Exact sample-by-sample (vs statistical only)
 *
 * Author: Generated for SerDes flicker noise PoC - Batch Mode
 * Date: 2025
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

//==============================================================================
// CONFIGURATION
//==============================================================================
#define MAX_SAMPLES 4096
#define NOISE_DATA_FILE "dpi/flicker_noise_batch.bin"

//==============================================================================
// STATIC STATE (persists between DPI-C calls)
//==============================================================================
static double preloaded_noise[MAX_SAMPLES];  // Pre-loaded noise array
static int current_index = 0;                 // Current read index
static int initialized = 0;                   // Initialization flag
static int num_samples_loaded = 0;            // Actual samples loaded from file

//==============================================================================
// INITIALIZATION FUNCTION
//==============================================================================
/**
 * Load noise samples from binary file.
 * Called automatically on first invocation of dpi_flicker_noise_batch().
 *
 * Binary Format:
 * - Data type: IEEE 754 double precision (8 bytes per sample)
 * - Byte order: Native (little-endian on x86/ARM)
 * - Size: MAX_SAMPLES × 8 = 32,768 bytes
 * - No header, just raw double array
 *
 * Error Handling:
 * - File not found: Prints error, fills with zeros (fallback)
 * - Partial read: Prints warning, uses available samples
 * - Both cases set initialized=1 to prevent repeated attempts
 */
static void init_flicker_noise_batch() {
    FILE *f = fopen(NOISE_DATA_FILE, "rb");

    if (f == NULL) {
        fprintf(stderr, "\n");
        fprintf(stderr, "========================================\n");
        fprintf(stderr, "ERROR: Cannot open %s\n", NOISE_DATA_FILE);
        fprintf(stderr, "========================================\n");
        fprintf(stderr, "Run the following command to generate:\n");
        fprintf(stderr, "  uv run python3 scripts/generate_flicker_noise_batch.py\n");
        fprintf(stderr, "\n");
        fprintf(stderr, "Falling back to zeros for all samples.\n");
        fprintf(stderr, "========================================\n");

        // Fill with zeros as fallback
        memset(preloaded_noise, 0, sizeof(preloaded_noise));
        num_samples_loaded = MAX_SAMPLES;
        initialized = 1;
        return;
    }

    // Read binary data (IEEE 754 double precision)
    num_samples_loaded = fread(preloaded_noise, sizeof(double), MAX_SAMPLES, f);
    fclose(f);

    // Check if we got all expected samples
    if (num_samples_loaded < MAX_SAMPLES) {
        fprintf(stderr, "\n");
        fprintf(stderr, "========================================\n");
        fprintf(stderr, "WARNING: Partial binary file read\n");
        fprintf(stderr, "========================================\n");
        fprintf(stderr, "Loaded %d samples (expected %d)\n",
                num_samples_loaded, MAX_SAMPLES);
        fprintf(stderr, "Binary file may be truncated or corrupted.\n");
        fprintf(stderr, "Re-run: uv run python3 scripts/generate_flicker_noise_batch.py\n");
        fprintf(stderr, "========================================\n");
    } else {
        // Success message
        fprintf(stderr, "[DPI-C INFO] Loaded %d noise samples from %s (%.1f KB)\n",
                num_samples_loaded, NOISE_DATA_FILE,
                (num_samples_loaded * sizeof(double)) / 1024.0);

        // Debug: Print first 10 samples for verification
        fprintf(stderr, "[DPI-C DEBUG] First 10 samples from binary:\n");
        for (int i = 0; i < 10 && i < num_samples_loaded; i++) {
            fprintf(stderr, "  [%3d] %11.6f\n", i, preloaded_noise[i]);
        }
    }

    current_index = 0;
    initialized = 1;
}

//==============================================================================
// DPI-C EXPORTED FUNCTION
//==============================================================================
/**
 * DPI-C Function: dpi_flicker_noise_batch
 *
 * Returns one pre-loaded noise sample per call.
 *
 * Operation:
 * 1. Initialize on first call (loads binary file)
 * 2. Return sample at current_index
 * 3. Increment index for next call
 * 4. Wrap to beginning if index exceeds loaded samples (loop)
 *
 * State Management:
 * - Static array persists across calls
 * - Initialization happens once automatically
 * - Index wraps to 0 when exceeding sample count (prevents overflow)
 *
 * Returns:
 *   double: Pre-loaded noise sample (zero-mean, RMS ≈ 0.25V)
 *
 * Notes:
 * - This function has side effects (updates static state)
 * - Do NOT declare as "pure" in SystemVerilog import
 * - Thread-safe for single-threaded simulation only
 * - Samples come from Python reference (exact match possible)
 * - If binary file missing, returns zeros (fallback behavior)
 */
double dpi_flicker_noise_batch(void) {
    // Initialize on first call
    if (!initialized) {
        init_flicker_noise_batch();
    }

    // Wrap index if exceeded (loop back to beginning)
    if (current_index >= num_samples_loaded) {
        current_index = 0;
    }

    // Return current sample and advance index
    return preloaded_noise[current_index++];
}

/**
 * DPI-C Function: dpi_flicker_noise (wrapper)
 *
 * Wrapper function for compatibility with RTL that expects dpi_flicker_noise().
 * Simply calls dpi_flicker_noise_batch() internally.
 *
 * This allows the same RTL (ideal_amp_with_noise.sv) to work with both
 * streaming and batch DPI-C implementations without modification.
 *
 * Returns:
 *   double: Pre-loaded noise sample (same as dpi_flicker_noise_batch)
 */
double dpi_flicker_noise(void) {
    static int call_count = 0;
    double result = dpi_flicker_noise_batch();

    // Debug: Print first 30 calls to track function invocation
    if (call_count < 30) {
        fprintf(stderr, "[DPI-C CALL %3d] index=%d, value=%.6f\n",
                call_count, current_index - 1, result);
    }
    call_count++;

    return result;
}

#ifdef __cplusplus
}
#endif

/**
 * =============================================================================
 * IMPLEMENTATION NOTES
 * =============================================================================
 *
 * 1. Comparison with Streaming Version (dpi_flicker_noise.c):
 *
 *    | Feature            | Streaming              | Batch (this file)      |
 *    |--------------------|------------------------|------------------------|
 *    | Algorithm          | Voss-McCartney compute | Pre-loaded from file   |
 *    | State              | 10 sources + counter   | 4096 array + index     |
 *    | Memory             | ~80 bytes              | ~32 KB                 |
 *    | Per-call compute   | O(10) - sum sources    | O(1) - array lookup    |
 *    | RNG                | C rand()               | Python reference       |
 *    | Match with Python  | Statistical only       | Exact sample-by-sample |
 *
 * 2. Binary File Format:
 *    - Generated by: scripts/generate_flicker_noise_batch.py
 *    - Format: IEEE 754 double precision (8 bytes per sample)
 *    - Byte order: Native (little-endian on x86/ARM)
 *    - Total size: 4096 × 8 = 32,768 bytes
 *    - No header, just contiguous double array
 *
 * 3. File Path:
 *    - Relative path: dpi/flicker_noise_batch.bin
 *    - Verilator runs from project root, so this path works
 *    - VCS may need adjustment (untested)
 *
 * 4. Error Handling:
 *    - File not found: Fallback to zeros, print clear error message
 *    - Partial read: Use available samples, print warning
 *    - Both cases allow simulation to continue (graceful degradation)
 *
 * 5. Index Wrapping:
 *    - When current_index >= num_samples_loaded, wrap to 0
 *    - Prevents buffer overflow
 *    - Allows simulation to run beyond 4096 samples (repeats pattern)
 *
 * 6. Performance:
 *    - Initialization: ~100 μs (file I/O, one-time cost)
 *    - Per-call: ~1 ns (single array access)
 *    - Total: ~2x faster than streaming for 4096+ samples
 *
 * 7. Thread Safety:
 *    - NOT thread-safe (uses static variables without locking)
 *    - Assumes single-threaded simulation (standard for Verilator)
 *    - Multiple DPI-C calls from different threads would cause race conditions
 *
 * 8. Verilator Compilation:
 *    - Add to test_config.yaml:
 *      verilator_extra_flags:
 *        - ../dpi/dpi_flicker_noise_batch.c
 *    - No special libraries needed (stdio.h, stdlib.h only)
 *    - No -lm flag required (unlike dpi_math.c with sin/cos)
 *
 * 9. Verification Workflow:
 *    Step 1: Generate binary
 *      uv run python3 scripts/generate_flicker_noise_batch.py
 *    Step 2: Run simulation
 *      uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch
 *    Step 3: Verify exact match
 *      uv run python3 scripts/verify_noise_match_batch.py
 *
 * 10. Debugging:
 *     - If "Cannot open file" error:
 *       Check: ls -lh dpi/flicker_noise_batch.bin (should be 32,768 bytes)
 *     - If verification fails:
 *       Check: Binary file was generated with same SEED and SAMPLES
 *     - If partial read warning:
 *       Re-generate binary file (may be corrupted)
 *
 * =============================================================================
 */
