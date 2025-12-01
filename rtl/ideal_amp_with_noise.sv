/**
 * ideal_amp_with_noise.sv - Ideal Amplifier with Flicker Noise Injection
 *
 * Educational module demonstrating:
 * - DPI-C integration for noise modeling
 * - Ideal amplifier model (out = in × GAIN)
 * - Additive noise injection for realistic analog behavior
 *
 * Use Case: SerDes amplifier modeling with 1/f noise characteristics
 *
 * Features:
 * - Parameterized gain
 * - DPI-C flicker noise injection
 * - Dual outputs (with/without noise) for verification
 *
 * NOT SYNTHESIZABLE: Uses 'real' type and DPI-C (simulation only)
 *
 * Author: Generated for SerDes flicker noise PoC
 * Date: 2025
 */

`timescale 1ns / 1ps

module ideal_amp_with_noise #(
    parameter real GAIN = 10.0,           // Amplifier voltage gain (V/V)
    parameter real NOISE_AMPLITUDE = 1.0  // Noise scaling factor (multiplier)
) (
    input  logic clk,          // Sample clock
    input  logic rst_n,        // Active-low reset
    input  real  amp_in,       // Input voltage (V)
    output real  amp_out,      // Output voltage with noise (V)
    output real  amp_out_ideal // Output voltage without noise (V)
);

    //==========================================================================
    // DPI-C IMPORT
    //==========================================================================
    // Import flicker noise generator from C
    // IMPORTANT: NOT declared as "pure" because function has side effects (state)
    import "DPI-C" function real dpi_flicker_noise();

    //==========================================================================
    // INTERNAL SIGNALS
    //==========================================================================
    real noise_sample;   // Current noise sample from DPI-C

    //==========================================================================
    // IDEAL AMPLIFICATION
    //==========================================================================
    // Simple linear gain: out_ideal = in × GAIN
    // This represents the ideal amplifier transfer function
    // No delay, no bandwidth limit, no distortion
    assign amp_out_ideal = amp_in * GAIN;

    //==========================================================================
    // NOISE INJECTION
    //==========================================================================
    // Sample noise on each clock edge
    // Add scaled noise to ideal output
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset: clear noise and output
            noise_sample <= 0.0;
            amp_out <= 0.0;
        end else begin
            // Get new noise sample from DPI-C function
            // This function updates its internal state on each call
            noise_sample <= dpi_flicker_noise();

            // Inject noise: out = out_ideal + noise_amplitude × noise
            // NOISE_AMPLITUDE allows scaling noise up/down
            amp_out <= amp_out_ideal + (NOISE_AMPLITUDE * noise_sample);
        end
    end

    //==========================================================================
    // ASSERTIONS (Optional, for debugging)
    //==========================================================================
    // Check that output stays within reasonable bounds
    // For GAIN=10, DC_IN=0.5, noise_RMS=0.25: output should be 5.0 ± ~0.75
    // Allow ±3σ margin: [4.25, 5.75]
    //
    // Uncomment for debugging:
    // property output_bounds;
    //     @(posedge clk) disable iff (!rst_n)
    //     (amp_out >= 3.0) && (amp_out <= 7.0);
    // endproperty
    //
    // assert property (output_bounds)
    //     else $warning("Output out of expected range: %f", amp_out);

endmodule
