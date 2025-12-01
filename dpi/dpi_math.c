/**
 * dpi_math.c - DPI-C Math Function Wrappers
 *
 * This file demonstrates DPI-C (Direct Programming Interface - C) integration
 * between SystemVerilog and C code. DPI-C allows SystemVerilog to call C functions
 * directly, enabling:
 *   - Use of existing C libraries (like math.h)
 *   - Integration of complex algorithms implemented in C
 *   - Hardware-software co-simulation
 *
 * EDUCATIONAL PURPOSE:
 * This is a simple example showing how to wrap C math functions for use in
 * SystemVerilog simulations. The sine function is ideal for learning because:
 *   1. It's simple to understand
 *   2. Results are easy to visualize (waveforms)
 *   3. Demonstrates real↔double type mapping
 *
 * COMPILATION:
 * With Verilator, this file is automatically included when referenced in the
 * SystemVerilog import statement. No manual compilation needed.
 * Just add it to the verilator command: verilator ... dpi/dpi_math.c
 */

#include <math.h>

// Note: svdpi.h is optional but recommended for type definitions
// #include <svdpi.h>

/**
 * DPI-C Function: dpi_sin
 *
 * Computes the sine of an angle in radians.
 *
 * IMPORTANT NOTES:
 * 1. extern "C" linkage:
 *    - Prevents C++ name mangling
 *    - Required for DPI-C to find the function
 *    - Even in pure C files, it's good practice for clarity
 *
 * 2. Data type mapping:
 *    - SystemVerilog 'real' ↔ C 'double' (64-bit IEEE 754)
 *    - SystemVerilog 'shortreal' ↔ C 'float' (32-bit IEEE 754)
 *    - For high precision, always use real/double
 *
 * 3. Pure functions:
 *    - This function has no side effects (doesn't modify global state)
 *    - Can be declared as "pure" in SystemVerilog for optimization
 *    - Verilator can better optimize pure functions
 *
 * @param x - Angle in radians (input)
 * @return Sine of x, range [-1.0, 1.0]
 */
#ifdef __cplusplus
extern "C" {
#endif

double dpi_sin(double x) {
    // Direct call to standard C math library
    // The math.h sin() function is highly optimized and accurate
    return sin(x);
}

/**
 * DPI-C Function: dpi_cos
 *
 * Computes the cosine of an angle in radians.
 * Included for completeness and to show multiple DPI-C functions in one file.
 *
 * @param x - Angle in radians (input)
 * @return Cosine of x, range [-1.0, 1.0]
 */
double dpi_cos(double x) {
    return cos(x);
}

#ifdef __cplusplus
}
#endif

/**
 * USAGE IN SYSTEMVERILOG:
 *
 * 1. Import the function:
 *    import "DPI-C" function real dpi_sin(input real x);
 *
 * 2. Call it like any SystemVerilog function:
 *    real result;
 *    result = dpi_sin(3.14159 / 2.0);  // Returns ~1.0
 *
 * 3. For pure functions, add "pure" keyword:
 *    import "DPI-C" pure function real dpi_sin(input real x);
 *
 * LINKING NOTES:
 * - The math library must be linked: -LDFLAGS -lm
 * - Add to test_config.yaml verilator_extra_flags:
 *     verilator_extra_flags:
 *       - -LDFLAGS
 *       - -lm
 *
 * VERILATOR SPECIFICS:
 * - Verilator generates V<top>__Dpi.h with function prototypes
 * - Functions are linked automatically during compilation
 * - No special flags needed beyond -lm for math library
 *
 * COMMON PITFALLS:
 * 1. Forgetting extern "C" → Name mangling errors
 * 2. Type mismatch → Use real↔double, int↔int32_t
 * 3. Missing -lm flag → Undefined reference to 'sin'
 * 4. Side effects in "pure" functions → Incorrect optimization
 */
