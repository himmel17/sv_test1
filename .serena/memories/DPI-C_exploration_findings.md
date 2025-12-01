# DPI-C Implementation Patterns - Codebase Exploration

## Executive Summary

This is a SystemVerilog SerDes project with complete DPI-C infrastructure and educational examples. The project demonstrates:
- Working DPI-C integration (math library functions)
- Comprehensive YAML-driven test framework
- Self-checking testbench patterns
- Multi-simulator support (Verilator, VCS)

## Key Findings

### 1. DPI-C Function Signature Patterns

**C Implementation Pattern** (`dpi/dpi_math.c`):
```c
#ifdef __cplusplus
extern "C" {
#endif

double dpi_sin(double x) {
    return sin(x);
}

double dpi_cos(double x) {
    return cos(x);
}

#ifdef __cplusplus
}
#endif
```

**Key Elements**:
- `extern "C"` prevents name mangling (CRITICAL for DPI-C)
- Uses standard C types: `double` for IEEE 754 64-bit floats
- Pure functions (no side effects) can be optimized
- Math library linkage required: `-lm` flag

**SystemVerilog Import Pattern** (`rtl/sine_wave_gen.sv`):
```systemverilog
import "DPI-C" pure function real dpi_sin(input real x);
```

**Data Type Mapping**:
- SystemVerilog `real` ↔ C `double` (64-bit IEEE 754)
- SystemVerilog `shortreal` ↔ C `float` (32-bit, less common)

### 2. Test Configuration Integration

**YAML Entry Format** (`tests/test_config.yaml`):
```yaml
- name: sine_wave_gen
  enabled: true
  description: "DPI-C sine wave generator - educational example"
  top_module: sine_wave_gen_tb
  testbench_file: sine_wave_gen_tb.sv
  rtl_files:
    - sine_wave_gen.sv
  verilator_extra_flags:
    - ../dpi/dpi_math.c      # DPI-C C source file
    - -LDFLAGS               # Linker flags marker
    - -lm                    # Link math library
  sim_timeout: "50us"        # Simulation timeout
```

**Important Details**:
- `verilator_extra_flags` can include C source files directly
- Path to C file is relative to testbench location
- `-LDFLAGS` marker indicates following flags are for linker
- `-lm` is essential for math.h functions (sin, cos, sqrt, etc.)
- `sim_timeout` auto-converts based on detected timescale

### 3. Testbench Self-Checking Pattern

**Key Structure** (`tb/sine_wave_gen_tb.sv`):
- Always include `timescale 1ns / 1ps` at top
- Declare timeout as module parameter (allows `-G` override)
- VCD filename must match test name in YAML (e.g., `sim/waves/sine_wave_gen.vcd`)
- Use `error_count` accumulation pattern
- Clear PASSED/FAILED messages
- Timeout watchdog protection for infinite loop protection
- Multiple verification checks: bounds, zero-crossings, amplitude

**Best Practices**:
- DPI-C can be imported in testbenches too (not just RTL)
- Use `real` type throughout for floating-point
- Include tolerance for floating-point comparisons (e.g., 1%)
- Track min/max for statistical analysis
- Clean output messages with clear test identification

### 4. Project Directory Structure

```
sv_test1/
├── dpi/                    # DPI-C C source files
│   ├── dpi_math.c         # Sin/cos implementation
│   ├── README.md          # Comprehensive DPI-C tutorial
│   └── README_ja.md       # Japanese DPI-C tutorial
├── rtl/                   # RTL modules (Design Under Test)
│   ├── counter.sv         # Basic counter example
│   ├── demux_4bit.sv      # Multiplexer example
│   ├── sine_wave_gen.sv   # DPI-C example module
│   ├── tx/               # Transmitter modules (future)
│   ├── rx/               # Receiver modules (future)
│   └── ...
├── tb/                    # Testbenches
│   ├── counter_tb.sv
│   ├── demux_4bit_tb.sv
│   ├── sine_wave_gen_tb.sv
│   └── tx/, rx/          # Subdirectories for future tests
├── tests/
│   └── test_config.yaml   # Central test registry
├── scripts/
│   ├── run_test.py        # Test orchestrator
│   └── simulators.py      # Simulator abstraction layer
├── sim/
│   ├── waves/            # VCD output files
│   ├── obj_dir/          # Verilator artifacts
│   └── vcs/              # VCS artifacts
└── spec/
    ├── ffe_specification_ja.md
    ├── dfe_specification_ja.md
    ├── ctle_specification_ja.md
    ├── serdes_architecture_ja.md
    └── test_strategy_ja.md
```

### 5. Timescale Handling

**Low-speed modules** (< 1 GHz):
```systemverilog
`timescale 1ns / 1ps
```
Used for: counter, demux, general logic

**High-speed SerDes** (10-25 Gbps):
```systemverilog
`timescale 1ps / 1fs
```
Used for: FFE, DFE, CTLE modules

**Auto-Detection in Framework**:
- `run_test.py` reads testbench file
- Extracts `timescale` directive automatically
- Converts `sim_timeout` string to correct units:
  - `"50us"` with `1ns/1ps` → `50000` time units
  - `"50us"` with `1ps/1fs` → `50000000` time units

### 6. Python Dependencies

**Current** (`pyproject.toml`):
```toml
dependencies = [
    "pyyaml>=6.0",  # YAML parsing for test config
]

[dependency-groups]
dev = [
    "black>=25.11.0",
    "flake8>=7.3.0",
    "isort>=7.0.0",
    "pyright>=1.1.407",
]
```

**Notes**:
- No numpy/matplotlib/scipy currently installed
- Framework uses YAML for test configuration
- Python 3.12.11+ required
- Dependencies managed via `uv` tool

### 7. Simulator Configuration

**Verilator Flags** (in YAML):
```yaml
simulators:
  verilator:
    common_flags:
      - --binary              # Auto-generate main()
      - --timing              # Support timing (required for real)
      - -Wall                 # All warnings
      - --trace               # VCD tracing
      - -Wno-TIMESCALEMOD    # Suppress timescale warnings
    execution_timeout: "30s"  # Real-world execution limit
```

## Critical Patterns for Flicker Noise Implementation

### 1. C Function for Stochastic Noise Generation
```c
// Would use noise generator algorithm (e.g., 1/f spectral shaping)
double dpi_flicker_noise_sample(double freq_hz, int sample_num) {
    // Generate pink/white noise sample using algorithm
    // Return value in range [-1.0, 1.0] or appropriate amplitude
}
```

### 2. SystemVerilog Wrapper Module
```systemverilog
`timescale 1ps / 1fs  // High-speed SerDes timescale

module flicker_noise_gen #(
    parameter real FREQ_HZ = 1.0e6,
    parameter real AMPLITUDE = 0.1,
    parameter real SAMPLE_RATE = 1.0e9
) (
    input  logic clk,
    input  logic rst_n,
    output real  noise_out
);
    import "DPI-C" function real dpi_flicker_noise_sample(
        input real freq_hz,
        input int sample_num
    );
    
    // Implementation similar to sine_wave_gen.sv
endmodule
```

### 3. Test Configuration Entry
```yaml
- name: flicker_noise_gen
  enabled: true
  description: "Flicker noise (1/f) generator with DPI-C"
  top_module: flicker_noise_gen_tb
  testbench_file: flicker_noise_gen_tb.sv
  rtl_files:
    - flicker_noise_gen.sv
  verilator_extra_flags:
    - ../dpi/dpi_noise.c      # Flicker noise C implementation
    - -LDFLAGS
    - -lm                      # May need math library
  sim_timeout: "100us"
```

### 4. Testbench Verification Checks
- Amplitude bounds checking
- Power spectral density (1/f characteristic) if possible
- Statistics: mean, variance
- Correlation tests
- Visual inspection via VCD dump

## Potential Issues and Considerations

1. **No numerical libraries currently installed**
   - numpy/scipy not in dependencies
   - May need to add for noise analysis
   - Alternatively: implement noise in pure C

2. **Real number precision**
   - Using `real` (double) throughout
   - Sufficient for most analog modeling
   - Consider precision for very long simulations

3. **Stochastic vs Deterministic**
   - DPI-C should seed RNG properly for reproducibility
   - Consider deterministic algorithms (e.g., Perlin noise)
   - Or use random seed from simulation control

4. **Performance**
   - C implementation faster than SystemVerilog loops
   - But may still be slow for high-frequency noise
   - Consider caching or lookup tables

5. **Subdirectory Support**
   - Framework supports `tx/`, `rx/` subdirectories
   - Test paths automatically resolved
   - Example: `testbench_file: noise/flicker_noise_tb.sv` → `tb/noise/flicker_noise_tb.sv`

## Reference Files Location

- **DPI-C math example**: `dpi/dpi_math.c`
- **DPI-C tutorial**: `dpi/README.md`
- **Sine wave module**: `rtl/sine_wave_gen.sv`
- **Sine wave testbench**: `tb/sine_wave_gen_tb.sv`
- **Test config**: `tests/test_config.yaml`
- **Simulator layer**: `scripts/simulators.py`
- **Test runner**: `scripts/run_test.py`
