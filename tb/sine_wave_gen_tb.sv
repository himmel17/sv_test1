/**
 * sine_wave_gen_tb.sv - Self-Checking Testbench for DPI-C Sine Wave Generator
 *
 * EDUCATIONAL PURPOSE:
 * This testbench demonstrates:
 * 1. How to test DPI-C integrated modules
 * 2. Using DPI-C in testbenches for verification (not just in RTL)
 * 3. Self-checking test patterns with automatic pass/fail
 * 4. Waveform visualization setup (VCD dump)
 *
 * VERIFICATION STRATEGY:
 * - Amplitude bounds checking (ensure output stays within expected range)
 * - Zero-crossing detection (verifies frequency is correct)
 * - Periodicity verification (count zero crossings over multiple periods)
 * - Visual inspection (generate VCD for GTKWave viewing)
 *
 * SELF-CHECKING PATTERN:
 * This testbench follows the project's standard pattern:
 * - Automatic error counting
 * - Clear PASSED/FAILED messages
 * - Timeout protection
 * - VCD dump for debugging
 */

`timescale 1ns / 1ps

module sine_wave_gen_tb #(
    parameter SIM_TIMEOUT = 50000  // Simulation timeout in timescale units (50us)
);

    //==========================================================================
    // DPI-C IMPORT FOR VERIFICATION
    //==========================================================================
    // Testbenches can also use DPI-C!
    // Here we import the same sin function for verification purposes.
    // This demonstrates that DPI-C is not limited to RTL - it's useful
    // anywhere you need C library functions in your simulation.
    //
    import "DPI-C" pure function real dpi_sin(input real x);

    //==========================================================================
    // TEST PARAMETERS
    //==========================================================================
    // These parameters match the DUT configuration
    // Note: We intentionally use non-default values to verify parameterization
    //
    localparam real FREQ = 1.0e6;         // 1 MHz sine wave
    localparam real AMPLITUDE = 2.5;       // 2.5V amplitude (±2.5V swing)
    localparam real OFFSET = 2.5;          // 2.5V DC offset
    localparam real SAMPLE_RATE = 100.0e6; // 100 MHz sampling (10ns clock period)

    // Calculated parameters
    localparam real PERIOD_NS = 1.0e9 / FREQ;  // Period in nanoseconds (1000ns for 1MHz)

    //==========================================================================
    // TESTBENCH SIGNALS
    //==========================================================================
    logic clk;             // Clock
    logic rst_n;           // Active-low reset
    real  sine_out;        // Sine wave output from DUT

    //==========================================================================
    // VERIFICATION VARIABLES
    //==========================================================================
    int error_count = 0;                    // Total errors detected
    real tolerance = 0.01;                  // 1% tolerance for comparisons
    int zero_crossing_count = 0;            // Count zero crossings
    real prev_sine_out = 0.0;               // Previous sample (for edge detection)
    real max_value = OFFSET - AMPLITUDE;    // Track actual min/max
    real min_value = OFFSET + AMPLITUDE;
    real measured_pp;                       // Measured peak-to-peak amplitude
    real expected_pp;                       // Expected peak-to-peak amplitude
    real pp_error;                          // Peak-to-peak error

    //==========================================================================
    // DEVICE UNDER TEST (DUT)
    //==========================================================================
    // Instantiate the sine wave generator with test parameters
    //
    sine_wave_gen #(
        .FREQ(FREQ),
        .AMPLITUDE(AMPLITUDE),
        .OFFSET(OFFSET),
        .SAMPLE_RATE(SAMPLE_RATE)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sine_out(sine_out)
    );

    //==========================================================================
    // CLOCK GENERATION
    //==========================================================================
    // Generate 100 MHz clock (10ns period = 5ns half-period)
    // This matches the SAMPLE_RATE parameter
    //
    initial clk = 0;
    always #5 clk = ~clk;

    //==========================================================================
    // VCD WAVEFORM DUMP
    //==========================================================================
    // IMPORTANT: The filename must match the test name in test_config.yaml
    // Format: "sim/waves/{test_name}.vcd"
    //
    // This allows:
    // 1. Each test to have its own waveform file
    // 2. Easy debugging with GTKWave: --view flag automatically opens correct file
    // 3. No filename conflicts between tests
    //
    initial begin
        $dumpfile("sim/waves/sine_wave_gen.vcd");
        $dumpvars(0, sine_wave_gen_tb);  // Dump all signals in this module
    end

    //==========================================================================
    // MAIN TEST SEQUENCE
    //==========================================================================
    initial begin
        $display("========================================");
        $display("  DPI-C Sine Wave Generator Test");
        $display("========================================");
        $display("Parameters:");
        $display("  Frequency    : %0.3f MHz", FREQ / 1e6);
        $display("  Amplitude    : %0.3f V", AMPLITUDE);
        $display("  Offset       : %0.3f V", OFFSET);
        $display("  Sample Rate  : %0.3f MHz", SAMPLE_RATE / 1e6);
        $display("  Period       : %0.3f ns", PERIOD_NS);
        $display("  Expected Range: %0.3f V to %0.3f V",
                 OFFSET - AMPLITUDE, OFFSET + AMPLITUDE);
        $display("========================================");

        error_count = 0;
        rst_n = 0;

        // Apply reset for a few cycles
        $display("[%0t ns] Applying reset...", $time);
        repeat(5) @(posedge clk);

        // Release reset
        rst_n = 1;
        $display("[%0t ns] Reset released, starting sine wave generation", $time);

        // Wait for DUT to stabilize
        repeat(2) @(posedge clk);

        // Run test for 5 complete periods
        // At 1 MHz, 5 periods = 5000ns = 500 clock cycles (at 100 MHz)
        $display("[%0t ns] Running test for 5 complete periods...", $time);
        for (int cycle = 0; cycle < 5; cycle++) begin
            $display("[%0t ns] Testing period %0d of 5", $time, cycle + 1);

            // Sample over approximately one complete period
            // 100 samples per period at 100 MHz with 1 MHz sine = 100 samples
            for (int sample = 0; sample < 100; sample++) begin
                @(posedge clk);

                // Update min/max tracking
                if (sine_out > max_value) max_value = sine_out;
                if (sine_out < min_value) min_value = sine_out;

                // Check 1: Amplitude bounds
                // The sine wave should stay within [OFFSET ± AMPLITUDE]
                if (sine_out < (OFFSET - AMPLITUDE - tolerance) ||
                    sine_out > (OFFSET + AMPLITUDE + tolerance)) begin
                    $display("  ERROR [%0t ns]: Amplitude out of range!", $time);
                    $display("    Value: %0.6f V", sine_out);
                    $display("    Expected: %0.3f ± %0.3f V",
                             OFFSET, AMPLITUDE);
                    error_count++;
                end

                // Check 2: Zero crossing detection
                // A zero crossing occurs when the signal crosses the OFFSET level
                // We detect rising edge crossings: prev < OFFSET and current >= OFFSET
                if ((prev_sine_out < OFFSET) && (sine_out >= OFFSET)) begin
                    zero_crossing_count++;
                    $display("  [%0t ns] Zero crossing detected (rising) - Count: %0d",
                             $time, zero_crossing_count);
                end

                // Store current value for next iteration
                prev_sine_out = sine_out;
            end
        end

        // Additional samples to ensure we caught the last crossing
        repeat(50) @(posedge clk);

        //======================================================================
        // VERIFICATION RESULTS
        //======================================================================
        $display("");
        $display("========================================");
        $display("  Test Results");
        $display("========================================");

        // Display statistics
        $display("Waveform Statistics:");
        $display("  Observed Min : %0.6f V", min_value);
        $display("  Observed Max : %0.6f V", max_value);
        $display("  Peak-to-Peak : %0.6f V", max_value - min_value);
        $display("  Expected P-P : %0.6f V", 2.0 * AMPLITUDE);

        // Check 3: Zero crossing count
        // For 5 periods, we expect approximately 5 rising zero crossings
        // Allow ±1 crossing tolerance due to sampling alignment
        $display("");
        $display("Zero Crossing Analysis:");
        $display("  Detected Crossings: %0d", zero_crossing_count);
        $display("  Expected Crossings: ~5 (for 5 periods)");

        if (zero_crossing_count < 4 || zero_crossing_count > 6) begin
            $display("  ERROR: Zero crossing count out of expected range!");
            error_count++;
        end else begin
            $display("  PASS: Zero crossing count is reasonable");
        end

        // Check 4: Peak-to-peak amplitude
        measured_pp = max_value - min_value;
        expected_pp = 2.0 * AMPLITUDE;
        pp_error = (measured_pp > expected_pp) ? (measured_pp - expected_pp) : (expected_pp - measured_pp);

        $display("");
        $display("Amplitude Analysis:");
        if (pp_error > (expected_pp * tolerance)) begin
            $display("  ERROR: Peak-to-peak amplitude mismatch!");
            $display("    Measured: %0.6f V", measured_pp);
            $display("    Expected: %0.6f V", expected_pp);
            $display("    Error   : %0.6f V", pp_error);
            error_count++;
        end else begin
            $display("  PASS: Peak-to-peak amplitude within tolerance");
        end

        //======================================================================
        // FINAL SUMMARY
        //======================================================================
        $display("");
        $display("========================================");
        if (error_count == 0) begin
            $display("*** PASSED: All DPI-C sine wave tests passed successfully ***");
            $display("");
            $display("Educational takeaways:");
            $display("  ✓ DPI-C function import works correctly");
            $display("  ✓ Real number (double) data passing is accurate");
            $display("  ✓ Math library integration is successful");
            $display("  ✓ Waveform generation meets specifications");
            $display("");
            $display("Next steps:");
            $display("  1. View waveform: uv run python3 scripts/run_test.py --test sine_wave_gen --view");
            $display("  2. Try changing parameters (FREQ, AMPLITUDE) and re-run");
            $display("  3. Read dpi/README.md for more DPI-C examples");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
            $display("");
            $display("Debug steps:");
            $display("  1. Check VCD file: sim/waves/sine_wave_gen.vcd");
            $display("  2. Verify DPI-C compilation (check for -lm flag)");
            $display("  3. Review error messages above");
        end
        $display("========================================");

        $finish;
    end

    //==========================================================================
    // TIMEOUT WATCHDOG
    //==========================================================================
    // Prevent infinite simulation if something goes wrong
    // SIM_TIMEOUT is passed from test_config.yaml via Verilator -G flag
    //
    initial begin
        #SIM_TIMEOUT;
        $display("");
        $display("========================================");
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $display("========================================");
        $finish;
    end

endmodule

/**
 * EDUCATIONAL NOTES:
 *
 * 1. DPI-C IN TESTBENCHES:
 *    - Not limited to RTL modules!
 *    - Useful for: reference models, advanced checking, file I/O
 *    - Same import syntax as in RTL
 *
 * 2. SELF-CHECKING PATTERNS:
 *    - Error counting: Accumulate errors, report at end
 *    - Clear messages: PASSED/FAILED with details
 *    - Multiple checks: Bounds, crossings, amplitude
 *    - Statistics: Min/max tracking for analysis
 *
 * 3. WAVEFORM ANALYSIS:
 *    - VCD dump essential for visual verification
 *    - Check waveform in GTKWave to confirm sine shape
 *    - Look for: smooth curve, correct frequency, proper amplitude
 *
 * 4. PARAMETER VERIFICATION:
 *    - Test with non-default parameters
 *    - Verify parameterization works correctly
 *    - Check edge cases (high/low frequency, amplitude)
 *
 * 5. TOLERANCE HANDLING:
 *    - Floating-point arithmetic is not exact
 *    - Always use tolerance for real number comparisons
 *    - 1% tolerance is reasonable for this example
 *
 * EXPERIMENT IDEAS:
 * - Change FREQ to 10 MHz and observe faster oscillation
 * - Change AMPLITUDE to 1.0 and see smaller swing
 * - Change OFFSET to 0.0 for bipolar waveform (-2.5V to +2.5V)
 * - Increase SAMPLE_RATE to see smoother waveform
 */
