# FFE (Feed-Forward Equalizer) Specification

**Document Version**: 1.0
**Last Updated**: 2025-01-11
**Target**: High-Speed SerDes (10-25 Gbps) for PCIe Gen3/4/5
**Modulation**: NRZ, PAM4

---

## 1. Overview

### 1.1 Purpose

The Feed-Forward Equalizer (FFE) is a digital FIR (Finite Impulse Response) filter that compensates for channel-induced inter-symbol interference (ISI) in high-speed serial links. It operates in the transmit path (Tx FFE for pre-emphasis) or receive path (Rx FFE for post-compensation).

### 1.2 Key Features

- **7-tap FIR filter** (configurable tap count via parameter)
- **Programmable coefficients** for adaptive equalization
- **8-bit data path** (matches ADC output width in Rx)
- **Signed arithmetic** for negative tap weights
- **Synchronous operation** with single clock domain
- **PCIe-compliant** tap weight ranges and constraints

### 1.3 Block Diagram

```
          ┌────────────────────────────────────────┐
data_in   │                                        │  data_out
───────>──┤  FFE (7-tap FIR Filter)                ├──>───────
  [7:0]   │                                        │   [7:0]
          │  Tap Delay Line: D0─D1─D2─D3─D4─D5─D6  │
          │       ×    ×   ×   ×   ×   ×   ×       │
          │      C0   C1  C2  C3  C4  C5  C6       │
          │       └────┴───┴───┴───┴───┴───┴──>Σ   │
          │                                        │
coeff_in  │  Coefficient Update Interface          │
───────>──┤  (coeff_wr_en, coeff_addr, coeff_data) │
          └────────────────────────────────────────┘
     clk ──>─┐
    rst_n ──>┘
```

---

## 2. Interface Specification

### 2.1 Port Definitions

| Port Name       | Direction | Width          | Type           | Description                                      |
|-----------------|-----------|----------------|----------------|--------------------------------------------------|
| `clk`           | Input     | 1              | `logic`        | System clock (parallel data rate clock)          |
| `rst_n`         | Input     | 1              | `logic`        | Active-low synchronous reset                     |
| `data_in`       | Input     | `DATA_WIDTH`   | `logic signed` | Input data samples (8-bit default, ADC output)   |
| `data_out`      | Output    | `DATA_WIDTH`   | `logic signed` | Equalized output data                            |
| `coeff_wr_en`   | Input     | 1              | `logic`        | Coefficient write enable (update tap weights)    |
| `coeff_addr`    | Input     | `ADDR_WIDTH`   | `logic`        | Coefficient address (tap index 0-6)              |
| `coeff_data`    | Input     | `COEFF_WIDTH`  | `logic signed` | Coefficient value to write (signed tap weight)   |
| `coeff_updated` | Output    | 1              | `logic`        | Pulse indicating coefficient update completed    |

**Notes:**
- All signals synchronous to `clk`
- `data_in`, `data_out`, `coeff_data` use **signed** arithmetic
- Reset initializes all tap weights to predefined values (cursor tap = max, others = 0)

### 2.2 Parameter Definitions

| Parameter      | Default | Range      | Description                                        |
|----------------|---------|------------|----------------------------------------------------|
| `TAP_COUNT`    | 7       | 3-15       | Number of FIR filter taps (odd number preferred)   |
| `DATA_WIDTH`   | 8       | 6-12       | Data path width (bits per sample)                  |
| `COEFF_WIDTH`  | 10      | 8-16       | Coefficient width (determines precision)           |
| `ADDR_WIDTH`   | 3       | 2-4        | Coefficient address width (log2(TAP_COUNT))        |
| `CURSOR_TAP`   | 3       | 0-6        | Main tap index (typically center tap)              |
| `ACCUM_WIDTH`  | 20      | 16-32      | Internal accumulator width (prevents overflow)     |

**Parameter Selection Guidelines:**
- `COEFF_WIDTH = DATA_WIDTH + 2` (minimum for sufficient precision)
- `ACCUM_WIDTH ≥ DATA_WIDTH + COEFF_WIDTH + log2(TAP_COUNT)` (avoid overflow)
- For PAM4: `DATA_WIDTH ≥ 8` (4 symbols require good resolution)
- For NRZ: `DATA_WIDTH ≥ 6` (2 symbols, simpler)

---

## 3. Functional Description

### 3.1 FIR Filter Algorithm

The FFE implements a discrete-time FIR filter:

```
y[n] = Σ(i=0 to N-1) c[i] × x[n-i]
```

Where:
- `y[n]`: Output sample at time n
- `x[n]`: Input sample at time n
- `c[i]`: Coefficient for tap i
- `N`: Number of taps (TAP_COUNT = 7)

### 3.2 Tap Delay Line

The input signal is delayed through a shift register to create multiple time-aligned tap points:

```
Tap0 = x[n]     (current sample)
Tap1 = x[n-1]   (1 sample delayed)
Tap2 = x[n-2]   (2 samples delayed)
...
Tap6 = x[n-6]   (6 samples delayed)
```

**Implementation**: Use `logic signed [DATA_WIDTH-1:0] tap_delay [0:TAP_COUNT-1]` shift register.

### 3.3 Multiply-Accumulate (MAC) Operation

Each tap output is multiplied by its coefficient and summed:

```systemverilog
// Pseudocode for MAC operation
accumulator = 0;
for (i = 0; i < TAP_COUNT; i++) {
    product[i] = tap_delay[i] * coefficient[i];  // Signed multiplication
    accumulator += product[i];                   // Signed addition
}
data_out = accumulator >>> (COEFF_WIDTH - 1);    // Arithmetic right shift for scaling
```

**Key Points:**
- Use **signed arithmetic** for all operations
- Accumulator must be wide enough to prevent overflow (`ACCUM_WIDTH`)
- Final output scaled by right-shifting to match `DATA_WIDTH`

### 3.4 Coefficient Update Interface

Coefficients can be updated dynamically via the control interface:

**Write Operation Sequence:**
1. Assert `coeff_wr_en = 1`
2. Set `coeff_addr` to target tap index (0 to TAP_COUNT-1)
3. Set `coeff_data` to desired tap weight (signed value)
4. On next `posedge clk`, coefficient is latched
5. `coeff_updated` pulses high for 1 cycle

**Read Operation**: (Optional feature, not mandatory for v1.0)
- Future enhancement: Add `coeff_rd_en` and `coeff_q` for coefficient readback

---

## 4. Timing Requirements

### 4.1 Clock and Reset

- **Clock Frequency**: Parallel data rate (e.g., 312.5 MHz for 10 Gbps with 32-bit parallel)
- **Reset Timing**: Synchronous active-low reset
  - Assert `rst_n = 0` for ≥ 2 clock cycles
  - All tap delays cleared to 0
  - Coefficients reset to default (cursor = max, pre/post = 0)

### 4.2 Latency

- **Pipeline Latency**: 2 clock cycles (tap delay register + MAC + output register)
- **Coefficient Update Latency**: 1 clock cycle from `coeff_wr_en` assertion

### 4.3 Timing Diagram

```
Clock      : ─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─
             : └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘
rst_n      : ───────────────────────┐────────────
             :                      └───────────>
data_in    : ────<D0>────<D1>────<D2>────<D3>────
             :                |            |
             :                └─(2 cycles)─┘
data_out   : ──────────────────────<Y0>────<Y1>─
             :
coeff_wr_en: ────────┐ ┌─────────────────────────
             :       └─┘
coeff_addr : ────────<3>─────────────────────────
             :       (cursor tap)
coeff_data : ────────<512>───────────────────────
             :
coeff_upd  : ──────────┐ ┌───────────────────────
             :         └─┘
```

---

## 5. Coefficient Management

### 5.1 Coefficient Representation

Coefficients use **signed fixed-point** format:

```
Sign bit: Bit [COEFF_WIDTH-1]
Integer: Bits [COEFF_WIDTH-2:FRAC_BITS]
Fraction: Bits [FRAC_BITS-1:0]
```

**Example for COEFF_WIDTH = 10:**
- Format: S.IIIIIIII.F (1 sign + 8 integer + 1 fractional bit)
- Range: -256 to +255.5
- Resolution: 0.5 LSB

### 5.2 Default Coefficient Values (Reset State)

For 7-tap FFE with cursor at tap 3:

| Tap Index | Tap Name        | Default Value (10-bit) | Hex     | Description               |
|-----------|-----------------|------------------------|---------|---------------------------|
| 0         | Pre-cursor 3    | 0                      | 0x000   | 3 samples before cursor   |
| 1         | Pre-cursor 2    | 0                      | 0x000   | 2 samples before cursor   |
| 2         | Pre-cursor 1    | 0                      | 0x000   | 1 sample before cursor    |
| 3         | **Cursor**      | **+511**               | 0x1FF   | **Main tap (maximum)**    |
| 4         | Post-cursor 1   | 0                      | 0x000   | 1 sample after cursor     |
| 5         | Post-cursor 2   | 0                      | 0x000   | 2 samples after cursor    |
| 6         | Post-cursor 3   | 0                      | 0x000   | 3 samples after cursor    |

**Rationale**: Default "pass-through" configuration (no equalization).

### 5.3 PCIe-Compliant Coefficient Ranges

For PCIe Gen3/4/5 transmitter FFE:

| Coefficient Type | Min Value      | Max Value     | Notes                           |
|------------------|----------------|---------------|---------------------------------|
| Cursor (C0)      | +0.5 (50%)     | +1.0 (100%)   | Always positive, largest weight |
| Pre-cursor (C-1) | -0.15 (-15%)   | +0.15 (+15%)  | De-emphasis for pre-ISI         |
| Post-cursor (C+1)| -0.25 (-25%)   | +0.05 (+5%)   | De-emphasis for post-ISI        |

**Normalization Constraint**: Σ|C[i]| ≤ 1.0 (total energy conservation)

---

## 6. Test Plan

### 6.1 Unit Test: Impulse Response

**Objective**: Verify tap delay line and basic FIR operation.

**Procedure**:
1. Set all coefficients to 0 except cursor (C[3] = 511)
2. Apply impulse: `data_in = 127` for 1 cycle, then `data_in = 0`
3. **Expected**: `data_out` shows single pulse at cursor tap position (2 cycles latency)

**Pass Criteria**: Output impulse amplitude = (127 × 511) >> 9 ≈ 127 (scaled back to DATA_WIDTH)

### 6.2 Unit Test: Pre-Emphasis

**Objective**: Verify negative coefficient operation.

**Procedure**:
1. Set coefficients:
   - C[2] = -128 (pre-cursor 1)
   - C[3] = +511 (cursor)
   - C[4] = -128 (post-cursor 1)
2. Apply step input: `data_in = 0` → `data_in = 100` (step transition)
3. **Expected**: Output shows overshoot before and after transition (pre-emphasis effect)

**Pass Criteria**:
- First transition: Output > 100 (overshoot)
- Settled value: Output ≈ 100 (after pre/post-cursors exit delay line)

### 6.3 Unit Test: Coefficient Update

**Objective**: Verify dynamic coefficient programming.

**Procedure**:
1. Initialize FFE with default coefficients
2. Assert `coeff_wr_en = 1`, `coeff_addr = 1`, `coeff_data = 256` (update pre-cursor 2)
3. Wait 1 cycle, check `coeff_updated` pulse
4. Apply test pattern and verify updated response

**Pass Criteria**:
- `coeff_updated` pulses high for exactly 1 cycle
- Subsequent output reflects new coefficient value

### 6.4 Integration Test: NRZ Equalization

**Objective**: Verify NRZ data stream equalization.

**Procedure**:
1. Configure FFE with typical NRZ coefficients (cursor = 0.8, post-cursor = -0.2)
2. Apply PRBS7 NRZ pattern: alternating +127/-128 levels
3. Monitor output for reduced ISI

**Pass Criteria**:
- Output eye diagram shows improved vertical eye opening
- No saturation or overflow in output samples

### 6.5 Integration Test: PAM4 Equalization

**Objective**: Verify PAM4 multi-level equalization.

**Procedure**:
1. Configure FFE with PAM4-optimized coefficients
2. Apply PAM4 pattern: 4 levels (-96, -32, +32, +96)
3. Monitor output level separation

**Pass Criteria**:
- All 4 PAM4 levels correctly preserved in output
- Level spacing maintained (no compression)

### 6.6 Stress Test: Maximum Coefficient Values

**Objective**: Verify accumulator overflow protection.

**Procedure**:
1. Set all coefficients to maximum positive value (+511 for 10-bit)
2. Apply maximum input: `data_in = +127`
3. Check `data_out` for saturation or overflow

**Pass Criteria**:
- No arithmetic overflow (output saturates to +127 max)
- No X (unknown) states in simulation

---

## 7. SystemVerilog Implementation Notes

### 7.1 Module Declaration Template

```systemverilog
`timescale 1ns / 1ps

// Feed-Forward Equalizer (FFE) - 7-tap FIR Filter
// Design Under Test (DUT) for Verilator simulation verification

module ffe #(
    parameter int TAP_COUNT    = 7,
    parameter int DATA_WIDTH   = 8,
    parameter int COEFF_WIDTH  = 10,
    parameter int ADDR_WIDTH   = 3,
    parameter int CURSOR_TAP   = 3,
    parameter int ACCUM_WIDTH  = 20
)(
    input  logic                       clk,          // System clock
    input  logic                       rst_n,        // Active-low reset
    input  logic signed [DATA_WIDTH-1:0]   data_in,  // Input samples
    output logic signed [DATA_WIDTH-1:0]   data_out, // Equalized output
    input  logic                       coeff_wr_en,  // Coefficient write enable
    input  logic [ADDR_WIDTH-1:0]      coeff_addr,   // Coefficient address
    input  logic signed [COEFF_WIDTH-1:0] coeff_data,// Coefficient data
    output logic                       coeff_updated // Coefficient update pulse
);

    // Internal signals
    logic signed [DATA_WIDTH-1:0]  tap_delay [0:TAP_COUNT-1];
    logic signed [COEFF_WIDTH-1:0] coeff [0:TAP_COUNT-1];
    logic signed [ACCUM_WIDTH-1:0] accumulator;

    // ... implementation ...

endmodule
```

### 7.2 Key Implementation Guidelines

#### 7.2.1 Tap Delay Line (Shift Register)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 0; i < TAP_COUNT; i++) begin
            tap_delay[i] <= '0;
        end
    end else begin
        tap_delay[0] <= data_in;  // New sample
        for (int i = 1; i < TAP_COUNT; i++) begin
            tap_delay[i] <= tap_delay[i-1];  // Shift
        end
    end
end
```

#### 7.2.2 Coefficient Storage and Update

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        // Initialize to default (cursor = max, others = 0)
        for (int i = 0; i < TAP_COUNT; i++) begin
            if (i == CURSOR_TAP) begin
                coeff[i] <= (2**(COEFF_WIDTH-1)) - 1;  // Max positive
            end else begin
                coeff[i] <= '0;
            end
        end
        coeff_updated <= 1'b0;
    end else begin
        coeff_updated <= 1'b0;  // Default: pulse for 1 cycle
        if (coeff_wr_en && coeff_addr < TAP_COUNT) begin
            coeff[coeff_addr] <= coeff_data;
            coeff_updated <= 1'b1;
        end
    end
end
```

#### 7.2.3 MAC Operation (Combinational)

```systemverilog
always_comb begin
    accumulator = '0;
    for (int i = 0; i < TAP_COUNT; i++) begin
        accumulator += tap_delay[i] * coeff[i];
    end
end
```

#### 7.2.4 Output Scaling and Saturation

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        data_out <= '0;
    end else begin
        // Arithmetic right shift to scale back to DATA_WIDTH
        logic signed [ACCUM_WIDTH-1:0] scaled;
        scaled = accumulator >>> (COEFF_WIDTH - 1);

        // Saturation logic
        if (scaled > $signed((2**(DATA_WIDTH-1))-1)) begin
            data_out <= (2**(DATA_WIDTH-1)) - 1;  // Positive saturation
        end else if (scaled < $signed(-(2**(DATA_WIDTH-1)))) begin
            data_out <= -(2**(DATA_WIDTH-1));      // Negative saturation
        end else begin
            data_out <= scaled[DATA_WIDTH-1:0];
        end
    end
end
```

### 7.3 Synthesis Considerations

- **Timing closure**: MAC operation is critical path (TAP_COUNT multiplications + additions)
  - Consider pipelining MAC for high-speed operation (adds 1 cycle latency)
- **Resource usage**:
  - DSP blocks: TAP_COUNT × multipliers (7 DSP48 for Xilinx)
  - Registers: TAP_COUNT × DATA_WIDTH (tap delays) + TAP_COUNT × COEFF_WIDTH (coefficients)
- **No division**: All operations use shifts and masks (avoid costly division)

### 7.4 Verification Hooks

For testbench visibility, add synthesis-time disabled signals:

```systemverilog
`ifdef SIMULATION
    // Internal state visibility for waveform debugging
    logic signed [DATA_WIDTH-1:0]  debug_tap0, debug_tap1, debug_tap6;
    logic signed [COEFF_WIDTH-1:0] debug_coeff0, debug_coeff3;

    assign debug_tap0 = tap_delay[0];
    assign debug_tap1 = tap_delay[1];
    assign debug_tap6 = tap_delay[6];
    assign debug_coeff0 = coeff[0];
    assign debug_coeff3 = coeff[3];  // Cursor tap
`endif
```

---

## 8. Testbench Requirements

### 8.1 Testbench Module Template

```systemverilog
`timescale 1ns / 1ps

module ffe_tb #(
    parameter SIM_TIMEOUT = 100000  // 100 µs default
);

    // Clock generation (example: 312.5 MHz for 10 Gbps / 32-bit)
    logic clk = 0;
    always #1.6 clk = ~clk;  // 312.5 MHz (3.2 ns period)

    // DUT signals
    logic       rst_n;
    logic signed [7:0]  data_in;
    logic signed [7:0]  data_out;
    logic       coeff_wr_en;
    logic [2:0] coeff_addr;
    logic signed [9:0]  coeff_data;
    logic       coeff_updated;

    // DUT instantiation
    ffe #(
        .TAP_COUNT(7),
        .DATA_WIDTH(8),
        .COEFF_WIDTH(10)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(data_out),
        .coeff_wr_en(coeff_wr_en),
        .coeff_addr(coeff_addr),
        .coeff_data(coeff_data),
        .coeff_updated(coeff_updated)
    );

    // VCD dump
    initial begin
        $dumpfile("sim/waves/ffe.vcd");
        $dumpvars(0, ffe_tb);
    end

    // Test sequence
    int error_count = 0;
    initial begin
        // Test implementation here
        // (See section 6 for test procedures)

        if (error_count == 0) begin
            $display("*** PASSED: All FFE tests passed successfully ***");
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

### 8.2 Test Configuration (test_config.yaml)

```yaml
- name: ffe
  enabled: true
  description: "FFE 7-tap FIR filter equalization test"
  top_module: ffe_tb
  testbench_file: ffe_tb.sv
  rtl_files:
    - ffe.sv
  verilator_extra_flags:
    - --trace-underscore  # For debugging internal signals
  sim_timeout: "100us"
```

---

## 9. References

### 9.1 Standards
- **PCIe Base Specification** (v3.0/4.0/5.0): Transmitter equalization requirements
- **IEEE 802.3**: Ethernet equalization specifications

### 9.2 Application Notes
- Xilinx UG479: 7 Series DSP48E1 Slice User Guide (for FPGA implementation)
- "Understanding Equalization" - Tektronix Application Note

### 9.3 Related Documents
- `spec/dfe_specification.md` - Decision Feedback Equalizer
- `spec/ctle_specification.md` - Continuous-Time Linear Equalizer
- `spec/serdes_architecture.md` - System-level SerDes architecture

---

## 10. Revision History

| Version | Date       | Author | Description                     |
|---------|------------|--------|---------------------------------|
| 1.0     | 2025-01-11 | Claude | Initial specification creation  |

---

## Appendix A: Coefficient Calculation Examples

### Example 1: Simple Pre-Emphasis (NRZ)

**Objective**: Reduce post-cursor ISI by -20%

**Calculation**:
- Cursor (C3) = 1.0 → 511 (10-bit max)
- Post-cursor 1 (C4) = -0.2 → -102 (10-bit)
- All others = 0

**Verification**:
- Apply step input: 0 → 127
- Expected output: Initial overshoot = 127 × (1.0 - 0.2) = ~102, then settle to 127

### Example 2: Symmetric Equalization (PAM4)

**Objective**: Equal pre and post compensation

**Calculation**:
- Pre-cursor 1 (C2) = -0.1 → -51
- Cursor (C3) = 1.0 → 511
- Post-cursor 1 (C4) = -0.1 → -51
- All others = 0

**Verification**:
- Apply PAM4 sequence: [-96, -32, +32, +96]
- Check level separation maintained in output

---

**End of FFE Specification**
