/**
 * sine_wave_gen.sv - Sine Wave Generator using DPI-C
 *
 * EDUCATIONAL PURPOSE:
 * This module demonstrates DPI-C integration by generating a continuous-time
 * sine wave using a C math library function. It's a simple, visual example
 * perfect for learning DPI-C concepts.
 *
 * KEY CONCEPTS DEMONSTRATED:
 * 1. DPI-C import statement
 * 2. Real number arithmetic in SystemVerilog
 * 3. Pure function annotation for optimization
 * 4. Parameter-based configuration
 * 5. Time tracking for continuous-time waveform generation
 *
 * USAGE:
 * This is NOT synthesizable code - it's for simulation only.
 * The 'real' type and DPI-C calls cannot be synthesized to hardware.
 * Use this for:
 *   - Testbench stimulus generation
 *   - Behavioral modeling
 *   - Algorithm verification
 */

`timescale 1ns / 1ps

module sine_wave_gen #(
    // Waveform parameters (all use 'real' for floating-point precision)
    parameter real FREQ = 1.0e6,           // Frequency in Hz (1 MHz default)
    parameter real AMPLITUDE = 2.5,        // Peak amplitude in volts
    parameter real OFFSET = 2.5,           // DC offset in volts (0V = OFFSET - AMPLITUDE)
    parameter real SAMPLE_RATE = 100.0e6   // Sampling rate in Hz (100 MHz = 10ns period)
) (
    input  logic clk,        // Sample clock
    input  logic rst_n,      // Active-low asynchronous reset
    output real  sine_out    // Sine wave output (continuous value)
);

    //==========================================================================
    // DPI-C IMPORT DECLARATION
    //==========================================================================
    // This is the key line for DPI-C integration!
    //
    // Syntax: import "DPI-C" [pure] function <return_type> <name>(<args>);
    //
    // - "DPI-C": Specifies Direct Programming Interface for C
    // - "pure": Optional keyword indicating function has no side effects
    //           Allows Verilator to optimize better (can cache results, reorder calls)
    // - "real": Return type (maps to C 'double')
    // - "dpi_sin": Function name (must match C function exactly)
    // - "input real x": Input argument (maps to C 'double x')
    //
    // The actual implementation is in dpi/dpi_math.c
    //
    import "DPI-C" pure function real dpi_sin(input real x);

    //==========================================================================
    // CONSTANTS
    //==========================================================================
    // Mathematical constants for phase calculation
    // Note: SystemVerilog doesn't have built-in PI, so we define it
    localparam real PI = 3.14159265358979323846;
    localparam real TWO_PI = 2.0 * PI;  // Full cycle = 2π radians

    //==========================================================================
    // TIME TRACKING
    //==========================================================================
    // For continuous-time waveform generation, we need to track elapsed time
    // in seconds (real-world time units, not simulation time units)

    real time_seconds;        // Current time in seconds
    real phase;               // Current phase angle in radians
    integer sample_count;     // Number of samples since reset (for time calculation)

    //==========================================================================
    // TIME COUNTER
    //==========================================================================
    // This sequential block updates time on every clock edge
    // Time = sample_count / SAMPLE_RATE gives us real-world seconds
    //
    // Example: If SAMPLE_RATE = 100 MHz (100e6 Hz)
    //          Then sample_count=100 → time_seconds = 100/100e6 = 1 microsecond
    //
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset: Start counting from zero
            sample_count <= 0;
            time_seconds <= 0.0;
        end else begin
            // Increment sample counter
            sample_count <= sample_count + 1;

            // Convert sample count to real-world seconds
            // Note: real'() casts integer to real for floating-point division
            time_seconds <= real'(sample_count) / SAMPLE_RATE;
        end
    end

    //==========================================================================
    // SINE WAVE GENERATION
    //==========================================================================
    // This combinational block generates the sine wave output
    //
    // Mathematical relationship:
    //   y(t) = OFFSET + AMPLITUDE * sin(2π * FREQ * t)
    //
    // Where:
    //   - t = time_seconds (current time)
    //   - FREQ = frequency in Hz
    //   - 2π * FREQ * t = phase angle in radians
    //   - sin() returns value in range [-1, +1]
    //   - AMPLITUDE scales to desired voltage swing
    //   - OFFSET shifts to desired DC level
    //
    // Example with default parameters:
    //   FREQ = 1 MHz, AMPLITUDE = 2.5V, OFFSET = 2.5V
    //   → Output swings from 0V to 5V with 1 MHz frequency
    //
    always_comb begin
        // Calculate phase angle (radians)
        phase = TWO_PI * FREQ * time_seconds;

        // Generate sine wave using DPI-C function
        // This is where the C function is called!
        sine_out = OFFSET + AMPLITUDE * dpi_sin(phase);
    end

    //==========================================================================
    // SYNTHESIS NOTE
    //==========================================================================
    // This module is NOT synthesizable because:
    // 1. 'real' type is not synthesizable (represents continuous values)
    // 2. DPI-C functions are simulation-only
    // 3. Division by SAMPLE_RATE in time calculation is not hardware-friendly
    //
    // For actual hardware sine wave generation, you would use:
    // - CORDIC algorithm (coordinate rotation digital computer)
    // - Lookup tables (ROM-based)
    // - Direct Digital Synthesis (DDS) cores
    //
    // This module is perfect for:
    // - Generating stimulus in testbenches
    // - Behavioral modeling of analog circuits
    // - Algorithm verification before hardware implementation

endmodule

/**
 * USAGE EXAMPLE:
 *
 * // Instantiate a 10 MHz sine wave generator
 * real my_sine;
 * sine_wave_gen #(
 *     .FREQ(10.0e6),        // 10 MHz frequency
 *     .AMPLITUDE(1.0),      // ±1V swing
 *     .OFFSET(0.0),         // Centered at 0V
 *     .SAMPLE_RATE(1.0e9)   // 1 GHz sampling (1ns period)
 * ) sine_gen (
 *     .clk(clk),
 *     .rst_n(rst_n),
 *     .sine_out(my_sine)
 * );
 *
 * PARAMETER SELECTION GUIDE:
 *
 * 1. FREQ (Frequency):
 *    - Choose based on your application
 *    - For visible waveforms: 100 kHz - 10 MHz
 *    - Must be << SAMPLE_RATE/2 (Nyquist theorem)
 *
 * 2. AMPLITUDE:
 *    - Peak amplitude (not peak-to-peak!)
 *    - Example: AMPLITUDE=2.5 gives ±2.5V swing (5V peak-to-peak)
 *
 * 3. OFFSET:
 *    - DC level of waveform
 *    - Example: OFFSET=2.5, AMPLITUDE=2.5 gives 0-5V range
 *
 * 4. SAMPLE_RATE:
 *    - Should match your clock frequency
 *    - Higher sampling → smoother waveform
 *    - Rule of thumb: SAMPLE_RATE ≥ 10 * FREQ for clean waveform
 */
