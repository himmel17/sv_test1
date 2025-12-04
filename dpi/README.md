# DPI-C Tutorial and Reference

**Direct Programming Interface for C (DPI-C)** - Comprehensive educational guide for SystemVerilog-C integration.

## Table of Contents

1. [What is DPI-C?](#what-is-dpi-c)
2. [When to Use DPI-C](#when-to-use-dpi-c)
3. [Basic Concepts](#basic-concepts)
4. [Data Type Mapping](#data-type-mapping)
5. [Import vs Export](#import-vs-export)
6. [Sine Wave Example Walkthrough](#sine-wave-example-walkthrough)
7. [Verilator-Specific Considerations](#verilator-specific-considerations)
8. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
9. [Advanced Topics](#advanced-topics)
10. [FAQ](#faq)

---

## What is DPI-C?

**DPI-C** (Direct Programming Interface for C) is an IEEE 1800 SystemVerilog standard that enables:

- **Calling C functions from SystemVerilog** - Access existing C libraries, algorithms, and code
- **Calling SystemVerilog from C** - Create custom C models that interact with hardware
- **Mixed-language simulation** - Combine hardware description with software models

### Key Benefits

✅ **Leverage existing C code** - Don't rewrite math libraries, file I/O, complex algorithms
✅ **Performance** - C implementations can be faster than equivalent SystemVerilog
✅ **Simplicity** - Some operations are more natural in C (strings, pointers, malloc)
✅ **Integration** - Connect hardware simulation with software models
✅ **Testbench power** - Use C libraries for advanced verification (JSON, regex, networking)

### What DPI-C is NOT

❌ **Not synthesizable** - DPI-C is simulation-only, cannot be converted to hardware
❌ **Not a replacement for RTL** - Use for modeling and verification, not implementation
❌ **Not portable to all simulators** - Some features vary between tools

---

## When to Use DPI-C

### Good Use Cases

| Use Case | Example | Why DPI-C? |
|----------|---------|------------|
| **Math functions** | sin, cos, sqrt, log | C math.h is optimized and accurate |
| **File I/O** | Read stimulus, write results | C file operations are powerful |
| **Reference models** | Golden algorithm in C | Compare RTL against trusted C |
| **Complex data structures** | Linked lists, hash tables | C pointers and malloc are natural |
| **External libraries** | Image processing, crypto | Reuse existing validated code |
| **Performance** | Heavy computation | C can be faster than SV loops |

### Bad Use Cases

| Use Case | Why Bad? | Alternative |
|----------|----------|-------------|
| Simple logic | Overhead not worth it | Pure SystemVerilog |
| Synthesizable code | DPI-C doesn't synthesize | Write RTL directly |
| Portable testbenches | Tool-specific behavior | SystemVerilog only |
| Debugging | Harder to trace bugs | SV is easier to debug |

**Rule of Thumb:** If you can easily do it in SystemVerilog, do it in SystemVerilog. Use DPI-C when C provides clear advantages.

---

## Basic Concepts

### The Import Statement

**SystemVerilog side:** Declare a C function for import

```systemverilog
// Basic import
import "DPI-C" function real dpi_sin(input real x);

// Pure function (no side effects - enables optimization)
import "DPI-C" pure function real dpi_sin(input real x);

// Function with multiple arguments
import "DPI-C" function int add(input int a, input int b);

// Context import (advanced - provides simulation context)
import "DPI-C" context function void debug_print(input string msg);
```

**C side:** Implement the function

```c
#include <math.h>

// Always use extern "C" to prevent name mangling
#ifdef __cplusplus
extern "C" {
#endif

double dpi_sin(double x) {
    return sin(x);
}

int add(int a, int b) {
    return a + b;
}

#ifdef __cplusplus
}
#endif
```

### The Export Statement

**SystemVerilog side:** Export a function for C to call

```systemverilog
export "DPI-C" function my_sv_function;

function int my_sv_function(int x);
    return x * 2;
endfunction
```

**C side:** Call the SystemVerilog function

```c
extern int my_sv_function(int x);

int some_c_code() {
    int result = my_sv_function(42);  // Calls SystemVerilog
    return result;
}
```

---

## Data Type Mapping

### Basic Types (Exact Mapping)

| SystemVerilog | C Type | Size | Notes |
|---------------|--------|------|-------|
| `byte` | `char` | 8 bits | Signed |
| `shortint` | `short` | 16 bits | Signed |
| `int` | `int` | 32 bits | Signed |
| `longint` | `long long` | 64 bits | Signed |
| `real` | `double` | 64 bits | IEEE 754 |
| `shortreal` | `float` | 32 bits | IEEE 754 |
| `string` | `const char*` | - | Null-terminated |
| `chandle` | `void*` | - | Opaque pointer |

### Packed Arrays (Bit Vectors)

```systemverilog
// SystemVerilog
import "DPI-C" function void process_bits(input bit [31:0] data);

// C implementation
#include <svdpi.h>
void process_bits(svBitVecVal data) {
    // data is a 32-bit value
}
```

### Important Rules

1. **Always use `input` direction** for DPI-C imports (most reliable)
2. **Avoid `output` and `inout`** - use return values instead
3. **Strings are immutable** - C receives `const char*`, cannot modify
4. **Arrays are trickier** - use open arrays or packed types
5. **Real numbers**: Use `real` ↔ `double` for precision

---

## Import vs Export

### Import (SystemVerilog calls C)

**Most common usage** - Call C libraries from your SystemVerilog testbench or model.

```systemverilog
// SystemVerilog
import "DPI-C" function real compute(input real x);

initial begin
    real result = compute(3.14);
end
```

```c
// C
double compute(double x) {
    return x * x;
}
```

### Export (C calls SystemVerilog)

**Advanced usage** - Let C code call back into your SystemVerilog.

```systemverilog
// SystemVerilog
export "DPI-C" function callback;

function void callback(int value);
    $display("Callback called with %0d", value);
endfunction
```

```c
// C
extern void callback(int value);

void some_c_function() {
    callback(42);  // Calls SystemVerilog
}
```

### When to Use Each

| Pattern | Use Import | Use Export |
|---------|------------|------------|
| Call C math library | ✅ | ❌ |
| Read file in testbench | ✅ | ❌ |
| C model needs SV state | ❌ | ✅ |
| Complex C-SV interaction | ✅ | ✅ Both |

**Tip:** Start with import-only (simpler). Add export only when you need C to call SV.

---

## Sine Wave Example Walkthrough

This project includes a complete DPI-C example demonstrating sine wave generation.

### Files Overview

```
dpi/
  dpi_math.c          ← C implementation of sin/cos wrappers
rtl/
  sine_wave_gen.sv    ← RTL module using DPI-C
tb/
  sine_wave_gen_tb.sv ← Testbench that also uses DPI-C
```

### Step-by-Step Explanation

#### Step 1: C Implementation (`dpi/dpi_math.c`)

```c
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// Simple wrapper around C standard library sin()
double dpi_sin(double x) {
    return sin(x);
}

#ifdef __cplusplus
}
#endif
```

**Key points:**
- Wraps standard `sin()` from `math.h`
- Uses `extern "C"` for proper linkage
- Returns `double` (maps to SV `real`)

#### Step 2: SystemVerilog RTL (`rtl/sine_wave_gen.sv`)

```systemverilog
module sine_wave_gen #(
    parameter real FREQ = 1.0e6,
    parameter real AMPLITUDE = 2.5,
    parameter real SAMPLE_RATE = 100.0e6
) (
    input  logic clk,
    input  logic rst_n,
    output real  sine_out
);
    // Import the C function
    import "DPI-C" pure function real dpi_sin(input real x);

    real time_seconds;
    real phase;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            time_seconds <= 0.0;
        else
            time_seconds <= time_seconds + (1.0 / SAMPLE_RATE);
    end

    always_comb begin
        phase = 2.0 * 3.14159 * FREQ * time_seconds;
        sine_out = AMPLITUDE * dpi_sin(phase);  // Call C function!
    end
endmodule
```

**Key points:**
- Declares `dpi_sin` with `import` statement
- Calls it just like a native SV function
- `pure` keyword enables optimization

#### Step 3: Testbench (`tb/sine_wave_gen_tb.sv`)

```systemverilog
module sine_wave_gen_tb;
    // Testbenches can also import DPI-C functions!
    import "DPI-C" pure function real dpi_sin(input real x);

    // ... test code ...

    // Use DPI-C for verification
    real expected = AMPLITUDE * dpi_sin(phase);
    if (sine_out != expected) begin
        $display("ERROR: Mismatch");
    end
endmodule
```

**Key points:**
- Testbenches can use DPI-C too
- Useful for reference models
- Same import syntax as RTL

#### Step 4: Compilation and Linking

In `tests/test_config.yaml`:

```yaml
- name: sine_wave_gen
  verilator_extra_flags:
    - ../dpi/dpi_math.c  # Include C source
    - -LDFLAGS           # Linker flags
    - -lm                # Link math library
```

**Verilator command generated:**
```bash
verilator --binary --timing ... \
    ../dpi/dpi_math.c \
    -LDFLAGS -lm \
    rtl/sine_wave_gen.sv tb/sine_wave_gen_tb.sv
```

#### Step 5: Running the Test

```bash
# Run simulation
uv run python3 scripts/run_test.py --test sine_wave_gen

# View waveform
uv run python3 scripts/run_test.py --test sine_wave_gen --view
```

Expected output:
```
*** PASSED: All DPI-C sine wave tests passed successfully ***
  ✓ DPI-C function import works correctly
  ✓ Real number (double) data passing is accurate
  ✓ Math library integration is successful
  ✓ Waveform generation meets specifications
```

---

## Flicker Noise Example (Advanced)

This project includes an advanced DPI-C example demonstrating **stateful** DPI-C implementation for analog noise modeling with Python-based verification.

### Purpose

Proof of Concept showing how to:
- Implement stateful algorithms in DPI-C (maintains state across calls)
- Model analog effects (1/f flicker noise) in digital simulation
- Validate C implementation against Python reference
- Perform statistical verification using VCD waveform data

### Files Overview

```
dpi/
  dpi_flicker_noise.c     ← Stateful C implementation (Voss-McCartney algorithm)
rtl/
  ideal_amp_with_noise.sv ← Ideal amplifier with noise injection
tb/
  ideal_amp_with_noise_tb.sv ← Self-checking testbench (DC input)
scripts/
  generate_flicker_noise.py  ← Python reference (streaming mode)
  generate_flicker_noise_batch.py ← Python reference (batch mode)
  verify_noise_match.py      ← Statistical verification (streaming)
  verify_noise_match_batch.py ← Exact matching verification (batch)
```

### Algorithm: Voss-McCartney 1/f Noise

The Voss-McCartney algorithm generates flicker (1/f) noise by:
1. Maintaining N noise sources (N=10 in this implementation)
2. Updating each source at different rates (source i updates every 2^i samples)
3. Summing all sources to produce 1/f power spectral density

**Characteristics:**
- Deterministic (fixed seed for reproducibility)
- Stateful (maintains noise sources and sample counter)
- Target RMS: 0.25V with empirical calibration

### Key Implementation: Stateful DPI-C

**CRITICAL**: This function is **NOT pure** - it maintains state across calls!

```c
// Static state persists across DPI-C calls
static double noise_sources[10];
static unsigned long sample_counter = 0;
static int initialized = 0;

double dpi_flicker_noise(void) {
    if (!initialized) {
        srand(42);  // Fixed seed
        for (int i = 0; i < 10; i++)
            noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
        initialized = 1;
    }

    // Update noise sources based on sample_counter
    for (int i = 0; i < 10; i++) {
        if ((sample_counter & ((1UL << i) - 1)) == 0) {
            noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
        }
    }

    double sum = 0.0;
    for (int i = 0; i < 10; i++)
        sum += noise_sources[i];

    sample_counter++;

    return sum * (0.25 / 1.757);  // Scale to target RMS
}
```

**Important Notes:**

- **Stateful via C Static Variables** (CRITICAL CONCEPT):
  - All state variables are declared with C's `static` keyword
  - **`static` variables retain their values between function calls**
  - This is fundamentally different from normal C local variables
  - **Execution sequence example**:
    ```
    Time    Event                               initialized value
    ----------------------------------------------------------------
    0ns     Program start                       0 (initialized once)
    100ns   1st clock: call dpi_flicker_noise()
            → if (!initialized) is TRUE         0
            → init_flicker_noise() executes
            → initialized = 1                   0 → 1
            → return noise value
    110ns   2nd clock: call dpi_flicker_noise()
            → if (!initialized) is FALSE        1 (RETAINED!)
            → skip initialization
            → return noise value
    120ns   3rd clock: call dpi_flicker_noise()
            → if (!initialized) is FALSE        1 (STILL RETAINED!)
            → skip initialization
            → return noise value
    ```
  - **Without `static`**: Variables would reset to initial values on every call
  - **With `static`**: Variables allocated once in program memory (not stack)
  - All three static variables persist:
    - `static int initialized`: Stays 1 after first init
    - `static double noise_sources[10]`: Array preserved across calls
    - `static unsigned long sample_counter`: Increments 0→1→2→3→...

- **NOT thread-safe**: Uses static variables without synchronization primitives

- **NOT pure**: Do NOT declare as `pure` in SystemVerilog (has side effects - modifies static state)

- **Deterministic**: Fixed seed ensures reproducibility across simulation runs

### SystemVerilog Integration

```systemverilog
module ideal_amp_with_noise #(
    parameter real GAIN = 10.0,
    parameter real NOISE_AMPLITUDE = 1.0
) (
    input  logic clk,
    input  logic rst_n,
    input  real  amp_in,
    output real  amp_out,
    output real  amp_out_ideal
);
    // IMPORTANT: NOT declared as "pure" (has side effects!)
    import "DPI-C" function real dpi_flicker_noise();

    real noise_sample;

    assign amp_out_ideal = amp_in * GAIN;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            noise_sample <= 0.0;
            amp_out <= 0.0;
        end else begin
            noise_sample <= dpi_flicker_noise();  // Get new noise sample
            amp_out <= amp_out_ideal + (NOISE_AMPLITUDE * noise_sample);
        end
    end
endmodule
```

### Verification Workflow (Streaming Mode - Method 1)

**Step 1: Generate Python Reference**
```bash
uv run python3 scripts/generate_flicker_noise.py
# Outputs: scripts/flicker_noise_reference.npy (1024 samples)
#          scripts/flicker_noise_spectrum.png (spectral plot)
```

**Step 2: Run SystemVerilog Simulation**
```bash
uv run python3 scripts/run_test.py --test ideal_amp_with_noise
# Outputs: sim/waves/ideal_amp_with_noise.vcd
# Testbench applies DC input, collects 1044 samples (20 reset skip + 1024 valid)
```

**Step 3: Statistical Verification**
```bash
uv run python3 scripts/verify_noise_match.py
# Extracts noise from VCD: amp_out - amp_out_ideal
# Compares RMS and spectral slope with Python reference
# Outputs: scripts/flicker_noise_verification.png
```

**Expected Results:**
```
======================================================================
FINAL VERDICT
======================================================================
✓✓✓ ALL TESTS PASSED ✓✓✓
Python and SystemVerilog implementations match statistically
Both exhibit 1/f noise characteristics as expected
======================================================================
RMS Error: 0.05% (0.249876V vs 0.250000V)
Spectral Slopes: Python=-1.155, SystemVerilog=-1.009 (expected: -1.0 ± 0.2)
```

### Verification Workflow (Batch Mode - Method 2)

For **exact sample-by-sample matching**, use the batch mode implementation:

**Step 1: Generate Python Reference and Binary**
```bash
uv run python3 scripts/generate_flicker_noise_batch.py
# Outputs: scripts/flicker_noise_batch_reference.npy (4096 samples)
#          scripts/flicker_noise_batch_spectrum.png (spectral plot)
#          dpi/flicker_noise_batch.bin (32 KB binary for DPI-C)
```

**Step 2: Run SystemVerilog Simulation (Batch)**
```bash
uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch
# Outputs: sim/waves/ideal_amp_with_noise_batch.vcd
# DPI-C loads pre-generated samples from binary file
```

**Step 3: Exact Matching Verification**
```bash
uv run python3 scripts/verify_noise_match_batch.py
# Sample-by-sample comparison with 1 nanovolt tolerance
# Outputs: scripts/flicker_noise_batch_verification.png
#          scripts/flicker_noise_batch_verification.log (detailed log)
```

**Expected Results:**
```
======================================================================
FINAL VERDICT - BATCH MODE
======================================================================
✓✓✓ ALL TESTS PASSED ✓✓✓
Python and SystemVerilog implementations match EXACTLY
All samples within epsilon tolerance (1 nanovolt)
======================================================================
Sample Match: 100.00% (4096/4096)
Max Error: 1.332e-15 V (floating point precision limit)
Mean Error: 2.997e-16 V
```

**Batch Mode Features:**
- Sample count: 4096 (vs 1024 for streaming)
- Verification: Exact sample-by-sample (vs statistical only)
- Tolerance: 1 nanovolt (vs 10% RMS)
- DPI-C: Pre-loaded from binary file (vs on-the-fly generation)
- Output: Detailed log file with sample-by-sample comparison

### Key Differences from Sine Wave Example

| Aspect | Sine Wave | Flicker Noise |
|--------|-----------|---------------|
| **State** | Stateless (pure) | Stateful (NOT pure) |
| **Import** | `pure function` | `function` (no pure) |
| **C variables** | None | Static variables |
| **Side effects** | None | Updates internal state |
| **Verification** | Exact comparison | Statistical comparison |
| **RNG** | None | C `rand()` (different from Python) |
| **Thread safety** | Safe | NOT thread-safe |

### Why Different RNGs Don't Matter

The C implementation uses `rand()` while Python uses `random.uniform()`. These produce **different sample values** but **identical statistical properties** (RMS, spectral slope).

**Verification Strategy:**
- ❌ Don't compare sample-by-sample (RNGs differ)
- ✅ Compare RMS (target: < 10% error)
- ✅ Compare spectral slope (target: -1.0 ± 0.2 for 1/f noise)
- ✅ Visual inspection of power spectral density

### Reset Handling

**Challenge:** First few samples after reset contain transient data

**Solution:**
- Testbench collects 1044 samples (TOTAL_SAMPLES = 1024 + 20)
- First 20 samples are "reset skip" period for circuit stabilization
- Verification script skips first 10 VCD samples (reset period)
- Compares sample_counter 0-1023 from both implementations

### Use Cases

This example demonstrates techniques for:
- **SerDes modeling**: Jitter, phase noise, channel noise
- **RF simulation**: Flicker noise in oscillators, amplifiers
- **Mixed-signal**: Analog behavioral models in digital sim
- **Algorithm validation**: Python prototype → C implementation workflow
- **Statistical verification**: VCD-based post-processing

### Educational Value

Learn:
- ✅ Stateful DPI-C design patterns
- ✅ When NOT to use `pure` keyword
- ✅ Python-to-C algorithm porting workflow
- ✅ Statistical verification techniques
- ✅ VCD parsing and post-processing
- ✅ FFT-based spectral analysis
- ✅ RNG differences and calibration

---

## Verilator-Specific Considerations

Verilator has excellent DPI-C support with some specific characteristics.

### What Works Well

✅ **Pure functions** - Highly optimized
✅ **Input arguments** - Full support
✅ **Return values** - Preferred method
✅ **Real numbers** - `real` ↔ `double` works perfectly
✅ **Standard libraries** - math.h, stdio.h, etc.

### Limitations

⚠️ **Tasks not supported** - Use functions only
⚠️ **Limited output/inout** - Prefer return values
⚠️ **No time delays** - Functions are zero-time
⚠️ **Context functions** - Limited support

### Generated Files

Verilator generates these files for DPI-C integration:

```
sim/obj_dir/
  Vsine_wave_gen_tb__Dpi.h      ← DPI-C function prototypes
  Vsine_wave_gen_tb__Dpi.cpp    ← DPI-C wrapper code
  (other Verilator files...)
```

You don't need to modify these - Verilator generates them automatically.

### Compilation Tips

1. **Include C files directly:**
   ```yaml
   verilator_extra_flags:
     - ../dpi/my_code.c
   ```

2. **Link libraries with -LDFLAGS:**
   ```yaml
   verilator_extra_flags:
     - -LDFLAGS
     - -lm        # Math library
     - -lpthread  # Threading
   ```

3. **Add include paths with -CFLAGS:**
   ```yaml
   verilator_extra_flags:
     - -CFLAGS
     - -I/path/to/includes
   ```

---

## Common Pitfalls and Solutions

### Pitfall 1: Missing Math Library

**Error:**
```
undefined reference to 'sin'
```

**Solution:**
Add `-lm` to linker flags:
```yaml
verilator_extra_flags:
  - -LDFLAGS
  - -lm
```

### Pitfall 2: Wrong Data Types

**Problem:**
```systemverilog
import "DPI-C" function int compute(input real x);  // Wrong!
```

```c
double compute(double x) {  // Returns double, not int
    return x * 2.0;
}
```

**Solution:**
Match types exactly:
```systemverilog
import "DPI-C" function real compute(input real x);  // Correct
```

### Pitfall 3: Name Mangling (C++)

**Error:**
```
undefined reference to 'dpi_sin'
```

**Cause:** Forgot `extern "C"` in C++ file.

**Solution:**
Always use:
```c
#ifdef __cplusplus
extern "C" {
#endif

double dpi_sin(double x) { ... }

#ifdef __cplusplus
}
#endif
```

### Pitfall 4: Side Effects in "pure" Functions

**Problem:**
```c
int counter = 0;

double not_pure(double x) {
    counter++;  // Side effect!
    return x * counter;
}
```

```systemverilog
// Declared as pure, but it's not!
import "DPI-C" pure function real not_pure(input real x);
```

**Result:** Verilator may cache results incorrectly.

**Solution:** Remove `pure` or remove side effects:
```systemverilog
import "DPI-C" function real not_pure(input real x);  // Not pure
```

### Pitfall 5: Floating-Point Comparison

**Problem:**
```systemverilog
if (sine_out == expected) begin  // Exact comparison - bad!
    $display("Match");
end
```

**Solution:** Use tolerance:
```systemverilog
real tolerance = 0.001;
if ($abs(sine_out - expected) < tolerance) begin  // Good
    $display("Match within tolerance");
end
```

---

## Advanced Topics

### Open Arrays

Pass variable-size arrays from SV to C.

```systemverilog
import "DPI-C" function void process_array(input real arr[]);

real my_array[100];
process_array(my_array);
```

```c
#include <svdpi.h>

void process_array(const svOpenArrayHandle arr) {
    int size = svSize(arr, 1);
    for (int i = 0; i < size; i++) {
        double* elem = (double*)svGetArrElemPtr1(arr, i);
        *elem *= 2.0;  // Modify in place
    }
}
```

### Context Functions

Access simulation context (time, scope, etc.).

```systemverilog
import "DPI-C" context function void debug_print(input string msg);
```

```c
#include <svdpi.h>

void debug_print(const char* msg) {
    const char* scope = svGetNameFromScope(svGetScope());
    printf("[%s] %s\n", scope, msg);
}
```

### Handling Strings

```systemverilog
import "DPI-C" function string to_upper(input string s);

string result = to_upper("hello");  // "HELLO"
```

```c
#include <ctype.h>
#include <string.h>

char* to_upper(const char* s) {
    static char buffer[1024];
    int i;
    for (i = 0; s[i] && i < 1023; i++) {
        buffer[i] = toupper(s[i]);
    }
    buffer[i] = '\0';
    return buffer;
}
```

**Warning:** String lifetimes are tricky. Static buffers work but aren't thread-safe.

---

## FAQ

### Q: Can I synthesize DPI-C code?

**A:** No. DPI-C is simulation-only. For hardware, you must implement the functionality in synthesizable RTL.

### Q: Which is better: import or export?

**A:** Start with import (SV calls C). It's simpler and covers 90% of use cases. Add export only if you need C to call SV.

### Q: Can I use DPI-C with VCS?

**A:** Yes! This project supports both Verilator and VCS. The DPI-C code is portable between simulators (though some advanced features may differ).

### Q: How do I debug DPI-C code?

**A:**
- Use `$display` in SV to trace calls
- Add `printf()` in C functions
- Use `gdb` with Verilator: `gdb obj_dir/Vtop`
- Check generated `V*__Dpi.h` for interface issues

### Q: What about performance?

**A:** DPI-C calls have overhead (function call across language boundary). For simple operations, pure SV may be faster. For complex algorithms, C wins. Profile before optimizing.

### Q: Can I use threads in DPI-C?

**A:** Advanced topic. Some simulators support it, but it's tricky. For this project, keep it simple - single-threaded is fine.

### Q: How do I handle errors?

**A:** Return error codes or use special values (NaN, negative values). DPI-C doesn't have exception handling across the SV-C boundary.

---

## Next Steps

### Experiment Ideas

1. **Modify the sine wave:**
   - Change frequency to 10 MHz
   - Try different amplitudes
   - Create a cosine wave (use `dpi_cos`)

2. **Add more math functions:**
   - Implement `dpi_sqrt`, `dpi_exp`, `dpi_log`
   - Create a Gaussian noise generator

3. **Combine functions:**
   - AM modulation: `carrier * (1 + depth * message)`
   - FM modulation: `sin(carrier + deviation * message)`

4. **Create reference models:**
   - Implement a filter in C
   - Compare RTL output against C "golden" model

### Learning Resources

- **IEEE 1800 Standard** - Official DPI-C specification
- **Verilator Manual** - Chapter on DPI-C (verilator.org)
- **Your simulator's docs** - VCS, Questa, etc.
- **This example code** - Read the comments carefully!

---

## Summary

**DPI-C enables powerful SystemVerilog-C integration:**

✅ Import C functions into SystemVerilog (most common)
✅ Export SV functions for C to call (advanced)
✅ Use existing C libraries (math, file I/O, etc.)
✅ Build reference models and advanced testbenches

**Key success factors:**

1. Match data types exactly (real ↔ double)
2. Use `extern "C"` in C code
3. Prefer `input` arguments and return values
4. Mark truly pure functions as `pure`
5. Link required libraries (-lm for math)

**Remember:** DPI-C is for simulation, not synthesis. Use it to enhance verification and modeling, not to avoid writing RTL!

---

**Questions?** Check the example code in `rtl/sine_wave_gen.sv` and `tb/sine_wave_gen_tb.sv` for a complete, working example.
