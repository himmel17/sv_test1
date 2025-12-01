/**
 * ideal_amp_with_noise_tb.sv - Testbench for Ideal Amplifier with Flicker Noise
 *
 * Test Strategy:
 * - Apply constant DC input (0.5V)
 * - Run for exactly 1024 samples (for FFT analysis with power-of-2 samples)
 * - Self-check: output within bounds [GAIN×DC_IN ± 3×NOISE_RMS]
 * - Generate VCD for Python verification script
 *
 * Verification Approach:
 * - Testbench checks bounds (±3σ, expect 99.7% within bounds)
 * - Python script compares with reference (RMS, spectral slope)
 *
 * Author: Generated for SerDes flicker noise PoC
 * Date: 2025
 */

`timescale 1ns / 1ps

module ideal_amp_with_noise_tb #(
    parameter SIM_TIMEOUT = 15000  // 15us timeout (1024 samples @ 100MHz = 10.24us + margin)
);

    //==========================================================================
    // TEST PARAMETERS
    //==========================================================================
    localparam real DC_INPUT = 0.5;           // Constant DC input voltage (V)
    localparam real GAIN = 10.0;              // Amplifier gain
    localparam real NOISE_AMPLITUDE = 1.0;    // Noise scaling (1.0 = full RMS=0.25)
    localparam real EXPECTED_OUTPUT = DC_INPUT * GAIN;  // 5.0V
    localparam real NOISE_RMS = 0.25;         // Expected noise RMS (V)
    localparam int SAMPLE_COUNT = 1024;       // Number of valid samples for FFT (power of 2)
    localparam int RESET_SKIP = 20;           // Skip initial samples after reset for stability
    localparam int TOTAL_SAMPLES = SAMPLE_COUNT + RESET_SKIP;  // Total samples including reset skip

    // Self-check bounds: ±3σ (99.7% of samples should be within)
    localparam real LOWER_BOUND = EXPECTED_OUTPUT - 3.0 * NOISE_RMS;  // 4.25V
    localparam real UPPER_BOUND = EXPECTED_OUTPUT + 3.0 * NOISE_RMS;  // 5.75V

    //==========================================================================
    // TESTBENCH SIGNALS
    //==========================================================================
    logic clk;
    logic rst_n;
    real  amp_in;
    real  amp_out;
    /* verilator lint_off UNUSEDSIGNAL */
    real  amp_out_ideal;  // Used in VCD for Python verification script
    /* verilator lint_on UNUSEDSIGNAL */

    //==========================================================================
    // VERIFICATION VARIABLES
    //==========================================================================
    int error_count = 0;
    int sample_num = 0;
    int out_of_bounds_count = 0;
    real min_output = UPPER_BOUND;
    real max_output = LOWER_BOUND;

    //==========================================================================
    // DEVICE UNDER TEST (DUT)
    //==========================================================================
    ideal_amp_with_noise #(
        .GAIN(GAIN),
        .NOISE_AMPLITUDE(NOISE_AMPLITUDE)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .amp_in(amp_in),
        .amp_out(amp_out),
        .amp_out_ideal(amp_out_ideal)
    );

    //==========================================================================
    // CLOCK GENERATION
    //==========================================================================
    // 100 MHz clock (10ns period)
    initial clk = 0;
    always #5 clk = ~clk;

    //==========================================================================
    // VCD WAVEFORM DUMP
    //==========================================================================
    // CRITICAL: Filename must match test name in test_config.yaml
    initial begin
        $dumpfile("sim/waves/ideal_amp_with_noise.vcd");
        $dumpvars(0, ideal_amp_with_noise_tb);
    end

    //==========================================================================
    // DC INPUT STIMULUS
    //==========================================================================
    // Apply constant DC input throughout simulation
    initial begin
        amp_in = DC_INPUT;  // Constant 0.5V
    end

    //==========================================================================
    // MAIN TEST SEQUENCE
    //==========================================================================
    initial begin
        $display("========================================");
        $display("  Ideal Amplifier with Flicker Noise Test");
        $display("========================================");
        $display("Parameters:");
        $display("  DC Input      : %0.3f V", DC_INPUT);
        $display("  Gain          : %0.1f", GAIN);
        $display("  Expected Out  : %0.3f V", EXPECTED_OUTPUT);
        $display("  Noise RMS     : %0.3f V", NOISE_RMS);
        $display("  Bounds        : [%0.3f, %0.3f] V (±3σ)",
                 LOWER_BOUND, UPPER_BOUND);
        $display("  Sample Count  : %0d", SAMPLE_COUNT);
        $display("========================================");

        // Initialize
        error_count = 0;
        out_of_bounds_count = 0;
        rst_n = 0;

        // Apply reset
        $display("[%0t ns] Applying reset...", $time);
        repeat(10) @(posedge clk);

        // Release reset
        rst_n = 1;
        $display("[%0t ns] Reset released, starting data collection", $time);

        // Wait for DPI-C initialization and circuit stabilization
        repeat(5) @(posedge clk);

        // Collect samples including reset skip period
        $display("[%0t ns] Collecting %0d samples (%0d valid + %0d reset skip)...",
                 $time, TOTAL_SAMPLES, SAMPLE_COUNT, RESET_SKIP);

        for (sample_num = 0; sample_num < TOTAL_SAMPLES; sample_num++) begin
            @(posedge clk);

            // Track min/max for statistics
            if (amp_out > max_output) max_output = amp_out;
            if (amp_out < min_output) min_output = amp_out;

            // Self-check: output within bounds
            if (amp_out < LOWER_BOUND || amp_out > UPPER_BOUND) begin
                out_of_bounds_count++;

                // Report first few errors
                if (out_of_bounds_count <= 5) begin
                    $display("  WARNING [%0t ns] Sample %0d: Output %0.6f V outside bounds",
                             $time, sample_num, amp_out);
                end
            end

            // Periodic progress (every 256 samples)
            if (sample_num % 256 == 0 && sample_num > 0) begin
                $display("  [%0t ns] Progress: %0d/%0d samples",
                         $time, sample_num, TOTAL_SAMPLES);
            end
        end

        // Additional samples to ensure VCD capture complete
        repeat(10) @(posedge clk);

        //======================================================================
        // FINAL RESULTS
        //======================================================================
        $display("");
        $display("========================================");
        $display("  Test Results");
        $display("========================================");
        $display("Samples Collected: %0d (including %0d reset skip)", TOTAL_SAMPLES, RESET_SKIP);
        $display("Valid Samples: %0d", SAMPLE_COUNT);
        $display("Output Range: %0.6f to %0.6f V", min_output, max_output);
        $display("Out-of-bounds: %0d (%.1f%%)",
                 out_of_bounds_count,
                 100.0 * out_of_bounds_count / TOTAL_SAMPLES);

        // Statistical expectation: ~0.3% should be outside ±3σ
        // Allow <1% tolerance for stochastic variation
        if (out_of_bounds_count < TOTAL_SAMPLES * 0.01) begin  // <1% tolerance
            $display("✓ PASS: Out-of-bounds count within expected range");
        end else begin
            $display("✗ FAIL: Excessive out-of-bounds samples");
            error_count++;
        end

        $display("");
        $display("Next Steps:");
        $display("  1. Run Python verification:");
        $display("     uv run python3 scripts/verify_noise_match.py");
        $display("  2. View waveform:");
        $display("     gtkwave sim/waves/ideal_amp_with_noise.vcd");
        $display("  3. Check spectrum:");
        $display("     open flicker_noise_verification.png");

        $display("");
        if (error_count == 0) begin
            $display("========================================");
            $display("*** PASSED: Testbench checks passed ***");
            $display("========================================");
        end else begin
            $display("========================================");
            $display("*** FAILED: %0d errors detected ***", error_count);
            $display("========================================");
        end

        $finish;
    end

    //==========================================================================
    // TIMEOUT WATCHDOG
    //==========================================================================
    initial begin
        #SIM_TIMEOUT;
        $display("");
        $display("========================================");
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $display("========================================");
        $finish;
    end

endmodule
