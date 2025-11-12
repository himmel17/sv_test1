# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SystemVerilog SerDes伝送路回路（SerDes transmission line circuit）開発・検証環境。Verilatorシミュレータ + GTKWave波形ビューアを使用。

**Purpose**: SerDes（Serializer/Deserializer）circuit development with automated testing infrastructure.

**Current Status**:
- ✅ **Specifications Complete**: Comprehensive Markdown specifications for FFE, DFE, CTLE, system architecture, and test strategy
- ✅ **Test Framework Ready**: YAML-driven test infrastructure with Verilator + GTKWave
- ✅ **Working Examples**: Two example modules (counter, demux_4bit) demonstrating test patterns
- 🚧 **Next Phase**: RTL implementation of SerDes modules based on specifications

## Quick Setup

```bash
# Install dependencies
sudo apt install verilator gtkwave python3  # Ubuntu/Debian

# Setup Python environment with uv (uses pyproject.toml)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync              # Creates venv + installs dependencies (includes dev tools by default)

# Production only (exclude dev tools)
uv sync --no-dev

# Run tests (uv run python3 uses the virtual environment automatically)
uv run python3 scripts/run_test.py --all
```

## Test Framework Architecture

### YAML-Based Test Configuration System

The project uses a **centralized YAML configuration** (`tests/test_config.yaml`) to manage multiple test cases. This architecture enables scaling from single module tests to complex integration tests without modifying Python code.

**Key Components:**

1. **`tests/test_config.yaml`** - Central test registry
   - Defines all available tests
   - Per-test Verilator flags
   - RTL file dependencies (supports subdirectory paths like `tx/tx_ffe.sv`)
   - Enable/disable individual tests
   - Simulation timeout configuration (`sim_timeout`)
   - Execution timeout configuration (`execution_timeout`)
   - **Subdirectory Support**:
     - `testbench_file`: Can specify paths like `tx/tx_ffe_tb.sv` (relative to `tb/`)
     - `rtl_files`: Can specify paths like `tx/tx_ffe.sv` (relative to `rtl/`)

2. **`scripts/run_test.py`** - Test orchestrator (YAML-driven)
   - `TestConfig` class: Parses YAML, filters enabled tests
   - `TestRunner` class: Executes individual tests (compile → simulate → report)
   - Generates per-test VCD files: `sim/waves/{test_name}.vcd`
   - `parse_sim_timeout()`: Converts timeout strings to numeric values for Verilator `-G` parameter

3. **Flow**: YAML → TestConfig → TestRunner → Verilator (with `-GSIM_TIMEOUT=value`) → VCD → (Optional) GTKWave

### Important: VCD File Naming Convention

Each test generates its own VCD file named `{test_name}.vcd` in `sim/waves/`. Testbenches must use `$dumpfile("sim/waves/{test_name}.vcd")` matching the test name in YAML config.

### Timeout Configuration

The framework supports two types of timeouts:

1. **Simulation Timeout** (`sim_timeout` in test config)
   - Represents **simulation time** (not real-world time)
   - Passed to testbench via Verilator's `-G` parameter: `-GSIM_TIMEOUT=value`
   - Testbenches must declare: `module xxx_tb #(parameter SIM_TIMEOUT = default_value);`
   - Supports units: `ns`, `us`, `ms`, `s` (e.g., `"50us"`, `"10000ns"`)
   - Converted based on `timescale 1ns/1ps` (e.g., `"50us"` → `50000` time units)

2. **Execution Timeout** (`execution_timeout` in verilator config)
   - Represents **real-world execution time** (wall-clock time)
   - Used by Python's `subprocess.run(timeout=...)` to prevent Verilator freeze
   - Global setting for all tests (in `verilator` section of YAML)
   - Example: `"30s"` gives 30 seconds for executable to complete

## Common Commands

### Running Tests with uv (Recommended)

`uv run` automatically uses the virtual environment, no activation needed:

```bash
# List all available tests
uv run python3 scripts/run_test.py --list

# Run all enabled tests (default)
uv run python3 scripts/run_test.py --all

# Run specific test
uv run python3 scripts/run_test.py --test counter

# Run with waveform viewer
uv run python3 scripts/run_test.py --test counter --view

# Clean build
uv run python3 scripts/run_test.py --clean --test counter
```

### Alternative: Activate Virtual Environment First

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS

# Then run with python3
python3 scripts/run_test.py --list
python3 scripts/run_test.py --all
```

### Adding New Tests

**4-step process** (all required):

1. Create RTL module in `rtl/{module}.sv`
   - Include `timescale 1ns / 1ps` at the top

2. Create testbench in `tb/{module}_tb.sv`
   - Include `timescale 1ns / 1ps` at the top
   - Declare with timeout parameter: `module {module}_tb #(parameter SIM_TIMEOUT = default_value);`
   - Must include `$dumpfile("sim/waves/{test_name}.vcd")`
   - Must include self-checking logic with pass/fail output
   - Include timeout watchdog:
     ```systemverilog
     initial begin
         #SIM_TIMEOUT;
         $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
         $finish;
     end
     ```

3. Add test definition to `tests/test_config.yaml`:
   ```yaml
   - name: {test_name}
     enabled: true
     description: "Brief description"
     top_module: {module}_tb
     testbench_file: {module}_tb.sv  # Supports subdirectory: tx/tx_ffe_tb.sv
     rtl_files:
       - {module}.sv                  # Supports subdirectory: tx/tx_ffe.sv
       - common.sv                    # Can mix root and subdirectory paths
     verilator_extra_flags: []        # Optional: add flags like --trace-underscore
     sim_timeout: "50us"              # Simulation time timeout (passed via -GSIM_TIMEOUT)
   ```

   **Subdirectory Example** (for SerDes modules in `rtl/tx/`, `rtl/rx/`):
   ```yaml
   - name: tx_ffe
     enabled: true
     description: "Transmit FFE (Feed-Forward Equalizer)"
     top_module: tx_ffe_tb
     testbench_file: tx/tx_ffe_tb.sv  # Resolved to tb/tx/tx_ffe_tb.sv
     rtl_files:
       - tx/tx_ffe.sv                  # Resolved to rtl/tx/tx_ffe.sv
       - serdes_common.sv              # Resolved to rtl/serdes_common.sv
     verilator_extra_flags: []
     sim_timeout: "100us"
   ```

4. Run: `uv run scripts/run_test.py --test {test_name}`

## Testbench Pattern

All testbenches should follow this self-checking pattern (see `tb/counter_tb.sv` and `tb/demux_4bit_tb.sv`):

```systemverilog
`timescale 1ns / 1ps

module {module}_tb #(
    parameter SIM_TIMEOUT = 50000  // Default timeout in timescale units
);
    // Clock generation (if needed)
    logic clk = 0;
    always #5 clk = ~clk;  // 100MHz

    // VCD dump - IMPORTANT: Path must match test name in YAML
    // The path is always sim/waves/{test_name}.vcd regardless of subdirectory location
    initial begin
        $dumpfile("sim/waves/{test_name}.vcd");
        $dumpvars(0, {module}_tb);
    end

    // Self-checking with error counting
    int error_count = 0;

    // Test sequence
    initial begin
        // Test logic with checks
        if (condition) begin
            $display("ERROR: ...");
            error_count++;
        end

        // Summary
        if (error_count == 0) begin
            $display("*** PASSED: All tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end

        $finish;
    end

    // Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $finish;
    end
endmodule
```

## SystemVerilog Style Notes

- **Timescale**: Always include `timescale 1ns / 1ps` at the top of all `.sv` files
- **Reset**: Use active-low synchronous reset (`rst_n`)
- **Clocking**: Sequential logic in `always_ff @(posedge clk)`
- **Combinational**: Use `always_comb` or `assign` (not `always @*`)
- **Overflow flags**: Prefer combinational logic (e.g., `assign overflow = (count == 8'hFF)`) for immediate response
- **Testbench parameters**: Declare timeout as module parameter to allow Verilator `-G` override

## Verilator-Specific Requirements

- **Timing support required**: All tests use `--timing` flag (Verilator 5.0+)
- **Binary mode**: Tests use `--binary` for automatic main() generation
- **Parameter passing**: Uses `-G` option to pass simulation timeout to testbench (e.g., `-GSIM_TIMEOUT=50000`)
- **Timescale**: All `.sv` files now include `timescale 1ns / 1ps`, so `-Wno-TIMESCALEMOD` flag is used
- **Warnings**: `-Wno-TIMESCALEMOD` suppresses timescale warnings for consistency

## Project Goals (SerDes Development)

This is a **SerDes development project** with comprehensive specifications. Currently includes two working examples:

- `counter.sv` - 8-bit synchronous counter with overflow detection
- `demux_4bit.sv` - 4-bit 1:4 demultiplexer

### SerDes Specifications (Completed)

Detailed specifications are available in `spec/` directory for implementation:

**Equalization Blocks**:
- **FFE (Feed-Forward Equalizer)**: 7-tap FIR filter for pre/post-cursor ISI cancellation
- **DFE (Decision Feedback Equalizer)**: 5-tap feedback with NRZ/PAM4 slicer
- **CTLE (Continuous-Time Linear Equalizer)**: Analog high-pass filter using Real Number Modeling

**System Architecture**:
- **Transmitter**: DAC-based with FFE pre-emphasis, serializer
- **Receiver**: ADC-based with CTLE → FFE → DFE cascade, CDR, deserializer
- **Modulation**: NRZ (2-level) and PAM4 (4-level)
- **Data Rate**: 10-25 Gbps targeting PCIe Gen3/4/5 compliance

See `spec/serdes_architecture.md` for complete system overview.

### Future SerDes Modules (To Be Implemented)

Based on specifications, the following modules will be implemented:

**Transmitter Path** (`rtl/tx/`):
- `tx_ffe.sv` - Transmit FFE (pre-emphasis)
- `serializer.sv` - Parallel-to-serial converter
- `dac_model.sv` - DAC behavioral model
- `serdes_tx.sv` - Top-level transmitter

**Receiver Path** (`rtl/rx/`):
- `adc_model.sv` - ADC behavioral model
- `ctle_rnm.sv` - CTLE analog equalizer (Real Number Modeling)
- `rx_ffe.sv` - Receive FFE (7-tap)
- `dfe.sv` - DFE (5-tap decision feedback)
- `cdr.sv` - Clock data recovery
- `deserializer.sv` - Serial-to-parallel converter
- `serdes_rx.sv` - Top-level receiver

**Supporting Modules**:
- `serdes_common.sv` - Common definitions and parameters
- `channel_model.sv` - Transmission line model
- `nrz_encoder.sv` / `pam4_encoder.sv` - Modulation helpers

Each new module must:
- Include `timescale 1ns / 1ps`
- Have a parameterized testbench with `SIM_TIMEOUT` parameter
- Be registered in `tests/test_config.yaml` with `sim_timeout` setting
- Follow the add-new-test pattern above (supports subdirectory paths in YAML)
- Implement interfaces as specified in `spec/` documents
- Use appropriate subdirectory structure (e.g., `rtl/tx/`, `rtl/rx/`, `tb/tx/`, `tb/rx/`)

## Dependencies

- **Verilator** 5.0+ (verified: 5.042) - SystemVerilog simulator
- **GTKWave** 3.3+ (verified: 3.3.104) - Waveform viewer
- **Python** 3.12+ with PyYAML
  - **Recommended**: Use `uv` with `pyproject.toml`
    - `uv sync` - Install runtime + dev dependencies (pyyaml, black, flake8, etc.) **[DEFAULT]**
    - `uv sync --no-dev` - Install runtime only (pyyaml) for production
    - Benefits: Fast, reproducible (`uv.lock`), modern (PEP 735 dependency groups)
  - Alternative (pip):
    - `pip3 install -r requirements.txt` - Runtime only
    - `pip3 install -r requirements-dev.txt` - Runtime + dev tools

## File Organization

- `spec/` - **Specification documents** (Markdown format)
  - `ffe_specification.md` - FFE (Feed-Forward Equalizer) detailed specification
  - `dfe_specification.md` - DFE (Decision Feedback Equalizer) detailed specification
  - `ctle_specification.md` - CTLE (Continuous-Time Linear Equalizer) detailed specification
  - `serdes_architecture.md` - Complete SerDes system architecture and integration
  - `test_strategy.md` - Comprehensive verification plan and test methodology
- `rtl/` - RTL modules (DUT - Design Under Test)
  - `counter.sv` - 8-bit synchronous counter (example)
  - `demux_4bit.sv` - 4-bit 1:4 demultiplexer (example)
  - `tx/` - Transmitter modules (to be implemented from specifications)
  - `rx/` - Receiver modules (to be implemented from specifications)
  - `channel/` - Channel models (to be implemented)
  - `modulation/` - Modulation encoders/decoders (to be implemented)
- `tb/` - Testbenches with self-checking logic
  - `counter_tb.sv` - Counter testbench (example)
  - `demux_4bit_tb.sv` - Demultiplexer testbench (example)
  - `tx/` - Transmitter testbenches (supports subdirectories)
  - `rx/` - Receiver testbenches (supports subdirectories)
- `tests/test_config.yaml` - **Central test registry** (modify to add tests)
- `scripts/run_test.py` - Test orchestrator (rarely needs modification)
- `pyproject.toml` - **Python dependencies** (runtime + dev tools) - Primary source
- `uv.lock` - Lockfile for reproducible builds (committed to git)
- `requirements.txt` - Legacy pip dependencies - runtime only (backward compatibility)
- `requirements-dev.txt` - Legacy pip dependencies - runtime + dev tools (backward compatibility)
- `.venv/` - Python virtual environment (uv) (gitignored)
- `sim/obj_dir/` - Verilator compilation artifacts (gitignored)
- `sim/waves/` - VCD waveform files (gitignored)

## Specification Documents (spec/)

Comprehensive Markdown specifications for SerDes equalization blocks and system architecture. These documents serve as the foundation for RTL implementation.

### Block-Level Specifications

#### 1. FFE (Feed-Forward Equalizer) - `spec/ffe_specification.md`
- **Type**: Digital FIR filter (7-tap configurable)
- **Purpose**: Pre/post-cursor ISI cancellation using feedforward equalization
- **Key Features**:
  - 8-bit data path with 10-bit signed coefficients
  - Programmable tap weights for adaptive equalization
  - Multiply-accumulate (MAC) with overflow protection
- **Test Plan**: 6 unit tests (impulse response, pre-emphasis, coefficient update, NRZ/PAM4 patterns)
- **Implementation**: Standard SystemVerilog with signed arithmetic

#### 2. DFE (Decision Feedback Equalizer) - `spec/dfe_specification.md`
- **Type**: Nonlinear feedback filter (5-tap configurable)
- **Purpose**: Post-cursor ISI cancellation using decision feedback
- **Key Features**:
  - Integrated slicer for NRZ (2-level) and PAM4 (4-level) detection
  - Feedback path with timing-critical multiply-accumulate
  - Look-ahead architecture option for >10 Gbps operation
- **Test Plan**: 7 unit tests (bypass mode, single/multi-tap feedback, PAM4 slicer, ISI cancellation, BER measurement)
- **Implementation**: Critical path optimization required for feedback loop timing closure

#### 3. CTLE (Continuous-Time Linear Equalizer) - `spec/ctle_specification.md`
- **Type**: Analog high-pass filter (behavioral model)
- **Purpose**: Frequency-dependent channel loss compensation before ADC
- **Key Features**:
  - Real Number Modeling (RNM) using SystemVerilog `real` type
  - Transfer function: H(s) = (1 + s/ωz) / [(1 + s/ωp1)(1 + s/ωp2)]
  - Programmable zero/pole placement for channel adaptation
  - Bilinear transform for discrete-time approximation
- **Test Plan**: Frequency sweep (Bode plot), DC response, peaking control, step response
- **Implementation**: Not synthesizable - simulation-only behavioral model

### System-Level Specifications

#### 4. SerDes Architecture - `spec/serdes_architecture.md`
- **Scope**: Complete transmitter-channel-receiver system
- **Transmitter Path**: Parallel Data → TX FFE → Serializer → DAC → Channel
- **Receiver Path**: Channel → ADC → CTLE → RX FFE → DFE → Deserializer → Parallel Data
- **Key Specifications**:
  - Data rates: 10-25 Gbps per lane
  - Modulation: NRZ (2-level) and PAM4 (4-level)
  - Clock architecture: Tx PLL + Rx CDR
  - PCIe Gen3/4/5 compliance requirements
- **Module Hierarchy**: Detailed RTL file organization and compilation order
- **Interface Definitions**: Port specifications for all blocks with types and widths

#### 5. Test Strategy - `spec/test_strategy.md`
- **Verification Hierarchy**: Unit → Integration → System → Compliance tests
- **Coverage Goals**:
  - Unit tests: 100% line, 95%+ branch coverage
  - Integration tests: All interfaces and clock domain crossings
  - System tests: BER < 1e-12, eye opening verification
  - Compliance tests: PCIe specification requirements
- **Test Infrastructure**:
  - Self-checking testbench patterns
  - BER measurement methodology
  - Eye diagram generation and analysis
  - Jitter injection and tolerance testing
- **Automation**: YAML-driven regression suite with HTML reporting

### Usage Guidelines

**For RTL Implementation**:
1. Start with block-level specifications (FFE, DFE, CTLE)
2. Follow interface specifications exactly (port names, widths, types)
3. Use provided SystemVerilog templates as starting point
4. Implement testbenches following self-checking patterns

**For Verification**:
1. Reference test plans in each specification
2. Use test_strategy.md for overall verification approach
3. Add tests to `tests/test_config.yaml` as modules are implemented
4. Follow hierarchical testing: unit → integration → system

**For System Integration**:
1. Reference serdes_architecture.md for module hierarchy
2. Follow specified compilation order for multi-file dependencies
3. Use serdes_common.sv for shared definitions and parameters
4. Verify clock domain crossings and reset strategies
