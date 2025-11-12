# DFE (Decision Feedback Equalizer) Specification

**Document Version**: 1.0
**Last Updated**: 2025-01-11
**Target**: High-Speed SerDes (10-25 Gbps) for PCIe Gen3/4/5
**Modulation**: NRZ, PAM4

---

## 1. Overview

### 1.1 Purpose

The Decision Feedback Equalizer (DFE) is a nonlinear adaptive equalizer that removes post-cursor inter-symbol interference (ISI) in high-speed serial data receivers. Unlike FFE (feed-forward), DFE uses **past decisions** (already detected symbols) to subtract ISI from the current sample, providing better equalization performance without noise amplification.

### 1.2 Key Features

- **5-tap decision feedback structure** (configurable tap count)
- **Integrated slicer** (decision circuit for NRZ/PAM4 symbol detection)
- **Programmable feedback coefficients** for adaptive operation
- **8-bit data path** (matches ADC and FFE output widths)
- **Look-ahead architecture** (optional) for timing closure at high speeds
- **PAM4-aware decision logic** with 4-level slicing
- **PCIe-compliant** feedback coefficient ranges

### 1.3 Block Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │         DFE (5-tap Feedback)                │
                    │                                             │
data_in [7:0] ──>───┤►─(+)────────►[SLICER]────►[Delay]──►──────►├──> data_out [7:0]
(from FFE/CTLE)     │   ▲              │           │              │    (detected symbols)
                    │   │              │     ┌─────┴────┐         │
                    │   │              └────►│  D1─D2─  │         │
                    │   │                    │  D3─D4─  │         │
                    │   │                    │    D5    │         │
                    │   │                    └────┬─────┘         │
                    │   │                         │               │
                    │   │  ┌──────────────────────┘               │
                    │   │  │   ┌───┬───┬───┬───┬───┐             │
                    │   └──┤─  │×C1│×C2│×C3│×C4│×C5│             │
                    │      │   └───┴───┴───┴───┴───┘             │
                    │      └────────►[Σ Feedback]                │
                    │                                             │
coeff_in ───────────┤►─ Coefficient Update Interface             │
                    │   (coeff_wr_en, coeff_addr, coeff_data)    │
                    └─────────────────────────────────────────────┘
     clk ──>────┐
    rst_n ──>───┘
```

**Key Difference from FFE**: DFE feedback uses **detected symbols** (hard decisions), not raw samples.

---

## 2. Interface Specification

### 2.1 Port Definitions

| Port Name       | Direction | Width          | Type           | Description                                        |
|-----------------|-----------|----------------|----------------|----------------------------------------------------|
| `clk`           | Input     | 1              | `logic`        | System clock (parallel data rate clock)            |
| `rst_n`         | Input     | 1              | `logic`        | Active-low synchronous reset                       |
| `data_in`       | Input     | `DATA_WIDTH`   | `logic signed` | Input samples (FFE/CTLE output, 8-bit)             |
| `data_out`      | Output    | `DATA_WIDTH`   | `logic signed` | Detected symbols (decision output)                 |
| `decision_valid`| Output    | 1              | `logic`        | Decision output valid flag                         |
| `coeff_wr_en`   | Input     | 1              | `logic`        | Coefficient write enable                           |
| `coeff_addr`    | Input     | `ADDR_WIDTH`   | `logic`        | Coefficient address (tap 1-5)                      |
| `coeff_data`    | Input     | `COEFF_WIDTH`  | `logic signed` | Feedback coefficient value (signed)                |
| `coeff_updated` | Output    | 1              | `logic`        | Coefficient update completion pulse                |
| `threshold`     | Input     | `THRESH_WIDTH` | `logic signed` | Slicer threshold(s) for PAM4 (3 thresholds needed) |
| `modulation`    | Input     | 1              | `logic`        | 0 = NRZ (2-level), 1 = PAM4 (4-level)              |

**Notes:**
- `data_in`: Equalized but noisy samples from FFE/CTLE
- `data_out`: Clean detected symbols (quantized to NRZ/PAM4 levels)
- `decision_valid`: Asserted after initial tap filling (5 cycles)
- PAM4 requires 3 thresholds to distinguish 4 levels

### 2.2 Parameter Definitions

| Parameter      | Default | Range      | Description                                          |
|----------------|---------|------------|------------------------------------------------------|
| `TAP_COUNT`    | 5       | 1-7        | Number of feedback taps                              |
| `DATA_WIDTH`   | 8       | 6-12       | Data path width (bits per sample/symbol)             |
| `COEFF_WIDTH`  | 10      | 8-16       | Coefficient width (determines precision)             |
| `ADDR_WIDTH`   | 3       | 1-4        | Coefficient address width                            |
| `THRESH_WIDTH` | 8       | 6-10       | Slicer threshold width (per threshold)               |
| `ACCUM_WIDTH`  | 18      | 16-24      | Feedback accumulator width                           |
| `LOOKAHEAD`    | 0       | 0-1        | Enable look-ahead architecture (0=disabled, 1=enabled)|

**Parameter Selection Guidelines:**
- `COEFF_WIDTH ≥ DATA_WIDTH` for sufficient precision
- `ACCUM_WIDTH ≥ DATA_WIDTH + COEFF_WIDTH + log2(TAP_COUNT)`
- `LOOKAHEAD = 1` recommended for >10 Gbps operation (solves feedback timing)

---

## 3. Functional Description

### 3.1 DFE Algorithm

The DFE subtracts ISI from past symbols before making current decision:

```
decision[n] = SLICER( data_in[n] - Σ(i=1 to N) C[i] × decision[n-i] )
```

Where:
- `decision[n]`: Detected symbol at time n
- `data_in[n]`: Input sample (noisy, with ISI)
- `C[i]`: Feedback coefficient for tap i
- `decision[n-i]`: Previously detected symbol (i symbols ago)
- `SLICER()`: Decision function (threshold comparison)

**Critical Insight**: Feedback uses **hard decisions** (quantized symbols), not soft values.

### 3.2 Feedback Path

#### 3.2.1 Feedback Calculation (Combinational)

```systemverilog
// Pseudocode for feedback calculation
feedback_sum = 0;
for (i = 1; i <= TAP_COUNT; i++) {
    feedback_sum += coefficient[i] * decision_history[i];
}
compensated_input = data_in - feedback_sum;
```

**Timing Critical**: This must complete within 1 clock cycle for non-lookahead architecture.

#### 3.2.2 Decision History (Shift Register)

```systemverilog
// Store past TAP_COUNT decisions
logic signed [DATA_WIDTH-1:0] decision_history [1:TAP_COUNT];

always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            decision_history[i] <= '0;
        end
    end else begin
        decision_history[1] <= data_out;  // Most recent decision
        for (int i = 2; i <= TAP_COUNT; i++) begin
            decision_history[i] <= decision_history[i-1];
        end
    end
end
```

### 3.3 Slicer (Decision Circuit)

The slicer quantizes the compensated input to the nearest symbol level.

#### 3.3.1 NRZ Slicer (2-level)

For NRZ (modulation = 0):

```
Symbol Levels: -127 (logic 0), +127 (logic 1)
Threshold: 0

if (compensated_input > threshold) then
    decision = +127  (logic 1)
else
    decision = -127  (logic 0)
```

#### 3.3.2 PAM4 Slicer (4-level)

For PAM4 (modulation = 1):

```
Symbol Levels: -96 (00), -32 (01), +32 (10), +96 (11)
Thresholds: T1 = -64, T2 = 0, T3 = +64

if (compensated_input > T3)         decision = +96  (11)
else if (compensated_input > T2)    decision = +32  (10)
else if (compensated_input > T1)    decision = -32  (01)
else                                decision = -96  (00)
```

**Implementation**: Use comparators + priority encoder for efficient multi-level slicing.

### 3.4 Look-Ahead Architecture (Optional)

**Problem**: At high speeds (>10 Gbps), feedback path timing may not close in 1 clock cycle.

**Solution**: Speculative computation - compute **multiple possible decisions** in parallel, then select correct one.

#### 3.4.1 Look-Ahead Principle

For 1-tap look-ahead DFE:

```
// Precompute two possibilities for next decision
if (current_decision == -127) {
    next_feedback = C[1] × (-127)
} else {  // current_decision == +127
    next_feedback = C[1] × (+127)
}

// Compute compensated input for both cases
compensated_if_low  = data_in - next_feedback_for_low
compensated_if_high = data_in - next_feedback_for_high

// Select correct one based on actual current decision
compensated_input = (current_decision == -127) ? compensated_if_low : compensated_if_high
```

**Trade-off**: Doubles logic for first tap, but enables higher clock frequencies.

---

## 4. Timing Requirements

### 4.1 Critical Timing Path

**Path**: `data_in` → Subtract feedback → Slicer → `data_out` → Feedback shift register → Multiply coefficients → Sum → back to Subtract

**Timing Budget** (Example for 312.5 MHz parallel clock):
- Clock period: 3.2 ns
- Setup/hold: 0.5 ns
- **Available for logic**: 2.7 ns
- Feedback multiply-accumulate (MAC): ~1.5 ns
- Subtraction + Slicer comparators: ~1.0 ns
- Routing: ~0.2 ns
- **Total**: ~2.7 ns ✓ (meets timing)

**For >10 Gbps**: May require look-ahead or pipelining.

### 4.2 Latency

- **Decision Latency**: 1 clock cycle (data_in to data_out)
- **Adaptation Latency**: 1 clock cycle (coefficient update to effect)
- **Initial Tap Fill**: 5 cycles (until `decision_valid` asserted)

### 4.3 Timing Diagram

```
Clock      : ─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─
             : └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘
rst_n      : ─────────┐─────────────────────
             :        └──────────────────>
data_in    : ──<D0><D1><D2><D3><D4><D5><D6>─
             :     │   │   │   │   │
decision   : ──────┴───<S1><S2><S3><S4><S5>─
             :              ▲       ▲
             :              └───┬───┘
             :              Feedback path
decision_valid:─────────────────┐───────────
             :                  └──────────>
```

**Note**: First 5 cycles are initialization (filling decision history).

---

## 5. Coefficient Management

### 5.1 Coefficient Representation

Same as FFE: **signed fixed-point** format (S.IIIIIIII.F for 10-bit).

### 5.2 Default Coefficient Values (Reset State)

For 5-tap DFE, all coefficients initialized to 0 (no feedback):

| Tap Index | Tap Name        | Default Value (10-bit) | Hex     |
|-----------|-----------------|------------------------|---------|
| 1         | Post-cursor 1   | 0                      | 0x000   |
| 2         | Post-cursor 2   | 0                      | 0x000   |
| 3         | Post-cursor 3   | 0                      | 0x000   |
| 4         | Post-cursor 4   | 0                      | 0x000   |
| 5         | Post-cursor 5   | 0                      | 0x000   |

**Rationale**: DFE disabled at startup (bypass mode).

### 5.3 Typical DFE Coefficient Values

For PCIe-compliant receiver DFE (NRZ):

| Tap Index | Typical Value      | Range             | Notes                               |
|-----------|-------------------|-------------------|-------------------------------------|
| 1         | -0.15 to -0.25    | -0.3 to 0.0       | First post-cursor (largest ISI)     |
| 2         | -0.05 to -0.15    | -0.2 to 0.0       | Second post-cursor                  |
| 3         | -0.02 to -0.08    | -0.15 to 0.0      | Third post-cursor                   |
| 4         | -0.01 to -0.05    | -0.1 to 0.0       | Fourth post-cursor (decaying ISI)   |
| 5         | 0.0 to -0.03      | -0.08 to 0.0      | Fifth post-cursor (minimal ISI)     |

**Sign Convention**: Negative coefficients **subtract** the post-cursor ISI contribution.

---

## 6. Adaptation Algorithm (Placeholder)

### 6.1 Overview

DFE coefficients must be **adapted** to track channel variations. Common algorithms:

1. **Least Mean Squares (LMS)**: Gradient descent minimization
2. **Sign-Sign LMS**: Simplified LMS using sign bits only
3. **Look-Up Table (LUT)**: Pre-computed coefficients for known channels

### 6.2 LMS Adaptation (Conceptual)

```
error[n] = data_in[n] - decision[n]  // Error signal

for (i = 1 to TAP_COUNT) {
    C[i] = C[i] - μ × error[n] × decision[n-i]
}
```

Where `μ` is the step size (learning rate).

**Implementation Note**: Adaptation logic is **separate module** (not part of core DFE). See `spec/dfe_adaptation.md` (future document).

### 6.3 Manual Coefficient Programming

For testing and bringup, coefficients can be **manually programmed** via the coefficient interface (same as FFE).

---

## 7. Test Plan

### 7.1 Unit Test: Bypass Mode (No Feedback)

**Objective**: Verify slicer operation with all coefficients = 0.

**Procedure**:
1. Set all DFE coefficients to 0
2. Set modulation = 0 (NRZ), threshold = 0
3. Apply alternating levels: data_in = +100, -100, +100, -100
4. **Expected**: data_out = +127, -127, +127, -127 (slicer quantizes correctly)

**Pass Criteria**: Output matches expected symbol levels exactly.

### 7.2 Unit Test: Single-Tap Feedback (NRZ)

**Objective**: Verify feedback calculation with 1 tap.

**Procedure**:
1. Set C[1] = -128 (approximately -0.25), all others = 0
2. Set modulation = 0 (NRZ), threshold = 0
3. Apply test sequence: data_in = +50, +50, +50 (constant)
4. **Expected**:
   - Cycle 1: decision = +127 (no prior feedback)
   - Cycle 2: feedback = -128 × (+127) ≈ -32, compensated = +50 - (-32) = +82 → decision = +127
   - Cycle 3+: Same as cycle 2 (steady state)

**Pass Criteria**: Feedback correctly modifies input before slicing.

### 7.3 Unit Test: Multi-Tap Feedback

**Objective**: Verify all 5 taps operate correctly.

**Procedure**:
1. Set coefficients: C[1] = -128, C[2] = -64, C[3] = -32, C[4] = -16, C[5] = -8
2. Apply step input: data_in = 0 → +100 (step transition)
3. Monitor decision_history shift register progression
4. **Expected**: Each tap contributes proportionally to total feedback

**Pass Criteria**: Feedback sum = Σ(C[i] × decision[i]) within ±1 LSB.

### 7.4 Unit Test: PAM4 Slicer

**Objective**: Verify 4-level slicing for PAM4.

**Procedure**:
1. Set modulation = 1 (PAM4)
2. Set thresholds: T1 = -64, T2 = 0, T3 = +64
3. Apply test levels: data_in = -80, -40, +40, +80
4. **Expected**: data_out = -96, -32, +32, +96 (correct level mapping)

**Pass Criteria**: All 4 PAM4 levels detected correctly.

### 7.5 Integration Test: ISI Cancellation (NRZ)

**Objective**: Verify DFE removes post-cursor ISI in realistic scenario.

**Procedure**:
1. Generate channel with ISI: Apply post-cursor tail = 20% of main pulse
2. Configure DFE: C[1] = -102 (approximately -0.2)
3. Apply PRBS7 NRZ pattern
4. Measure **BER (Bit Error Rate)** at output

**Pass Criteria**:
- BER without DFE: >1e-4 (high error rate due to ISI)
- BER with DFE: <1e-9 (clean eye, ISI canceled)

### 7.6 Integration Test: Coefficient Update During Operation

**Objective**: Verify dynamic coefficient programming.

**Procedure**:
1. Start DFE with default coefficients (all 0)
2. Run for 100 cycles with test pattern
3. Update C[1] to -128 via coeff_wr_en interface
4. Verify `coeff_updated` pulse
5. Continue for 100 cycles, check behavior change

**Pass Criteria**:
- Coefficient update completes in 1 cycle
- Output behavior reflects new coefficient immediately

### 7.7 Stress Test: Maximum Feedback

**Objective**: Verify saturation protection in extreme case.

**Procedure**:
1. Set all coefficients to maximum negative: C[i] = -512 (10-bit)
2. Apply worst-case input: all previous decisions = +127
3. Check feedback sum and compensated input for overflow

**Pass Criteria**:
- No arithmetic overflow or X states
- Compensated input saturates correctly

---

## 8. SystemVerilog Implementation Notes

### 8.1 Module Declaration Template

```systemverilog
`timescale 1ns / 1ps

// Decision Feedback Equalizer (DFE) - 5-tap Feedback
// Design Under Test (DUT) for Verilator simulation verification

module dfe #(
    parameter int TAP_COUNT    = 5,
    parameter int DATA_WIDTH   = 8,
    parameter int COEFF_WIDTH  = 10,
    parameter int ADDR_WIDTH   = 3,
    parameter int THRESH_WIDTH = 8,
    parameter int ACCUM_WIDTH  = 18,
    parameter int LOOKAHEAD    = 0
)(
    input  logic                           clk,              // System clock
    input  logic                           rst_n,            // Active-low reset
    input  logic signed [DATA_WIDTH-1:0]   data_in,          // Input samples
    output logic signed [DATA_WIDTH-1:0]   data_out,         // Detected symbols
    output logic                           decision_valid,   // Output valid
    input  logic                           coeff_wr_en,      // Coefficient write
    input  logic [ADDR_WIDTH-1:0]          coeff_addr,       // Coefficient address
    input  logic signed [COEFF_WIDTH-1:0]  coeff_data,       // Coefficient data
    output logic                           coeff_updated,    // Update complete
    input  logic signed [THRESH_WIDTH-1:0] threshold[0:2],   // PAM4 thresholds (3)
    input  logic                           modulation        // 0=NRZ, 1=PAM4
);

    // Internal signals
    logic signed [DATA_WIDTH-1:0]  decision_history [1:TAP_COUNT];
    logic signed [COEFF_WIDTH-1:0] coeff [1:TAP_COUNT];
    logic signed [ACCUM_WIDTH-1:0] feedback_sum;
    logic signed [DATA_WIDTH-1:0]  compensated_input;
    logic signed [DATA_WIDTH-1:0]  decision;
    int cycle_count;

    // ... implementation ...

endmodule
```

### 8.2 Key Implementation Guidelines

#### 8.2.1 Feedback Calculation (Combinational - Critical Path)

```systemverilog
always_comb begin
    feedback_sum = '0;
    for (int i = 1; i <= TAP_COUNT; i++) begin
        feedback_sum += decision_history[i] * coeff[i];
    end
end

// Compensated input (subtract feedback from input)
always_comb begin
    logic signed [ACCUM_WIDTH-1:0] temp;
    temp = data_in - (feedback_sum >>> (COEFF_WIDTH - 1));

    // Saturation to DATA_WIDTH
    if (temp > $signed((2**(DATA_WIDTH-1))-1)) begin
        compensated_input = (2**(DATA_WIDTH-1)) - 1;
    end else if (temp < $signed(-(2**(DATA_WIDTH-1)))) begin
        compensated_input = -(2**(DATA_WIDTH-1));
    end else begin
        compensated_input = temp[DATA_WIDTH-1:0];
    end
end
```

#### 8.2.2 Slicer (Combinational)

```systemverilog
always_comb begin
    if (modulation == 1'b0) begin
        // NRZ slicer (2-level)
        if (compensated_input > threshold[1]) begin
            decision = $signed(8'd127);  // Logic 1
        end else begin
            decision = $signed(-8'd128); // Logic 0
        end
    end else begin
        // PAM4 slicer (4-level)
        if (compensated_input > threshold[2]) begin
            decision = $signed(8'd96);   // Symbol 11
        end else if (compensated_input > threshold[1]) begin
            decision = $signed(8'd32);   // Symbol 10
        end else if (compensated_input > threshold[0]) begin
            decision = $signed(-8'd32);  // Symbol 01
        end else begin
            decision = $signed(-8'd96);  // Symbol 00
        end
    end
end
```

#### 8.2.3 Decision History Update (Sequential)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            decision_history[i] <= '0;
        end
        data_out <= '0;
        cycle_count <= 0;
        decision_valid <= 1'b0;
    end else begin
        // Register decision output
        data_out <= decision;

        // Shift decision history
        decision_history[1] <= decision;
        for (int i = 2; i <= TAP_COUNT; i++) begin
            decision_history[i] <= decision_history[i-1];
        end

        // Decision valid after TAP_COUNT cycles
        if (cycle_count < TAP_COUNT) begin
            cycle_count <= cycle_count + 1;
            decision_valid <= 1'b0;
        end else begin
            decision_valid <= 1'b1;
        end
    end
end
```

#### 8.2.4 Coefficient Management (Sequential)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            coeff[i] <= '0;  // Initialize to 0 (DFE disabled)
        end
        coeff_updated <= 1'b0;
    end else begin
        coeff_updated <= 1'b0;
        if (coeff_wr_en && coeff_addr > 0 && coeff_addr <= TAP_COUNT) begin
            coeff[coeff_addr] <= coeff_data;
            coeff_updated <= 1'b1;
        end
    end
end
```

### 8.3 Look-Ahead Implementation (Advanced - Optional)

```systemverilog
generate
    if (LOOKAHEAD == 1) begin : gen_lookahead
        // Speculative computation for first tap
        logic signed [DATA_WIDTH-1:0] feedback_if_prev_low;
        logic signed [DATA_WIDTH-1:0] feedback_if_prev_high;

        always_comb begin
            // Precompute feedback for both possibilities
            feedback_if_prev_low  = coeff[1] * $signed(-8'd128);  // If prev = -128
            feedback_if_prev_high = coeff[1] * $signed(8'd127);   // If prev = +127

            // Select based on actual previous decision
            // (This breaks critical path)
        end
        // ... (Implementation details omitted for brevity) ...
    end
endgenerate
```

### 8.4 Synthesis Considerations

- **Critical Path Optimization**:
  - Pipeline feedback MAC if timing doesn't close (adds 1 cycle latency)
  - Use look-ahead for first tap at >10 Gbps
  - Floorplan feedback logic close to slicer
- **Resource Usage**:
  - Multipliers: TAP_COUNT × DSP blocks
  - Comparators: 1 (NRZ) or 3 (PAM4)
- **Metastability**: Not applicable (fully synchronous design)

### 8.5 Verification Hooks

```systemverilog
`ifdef SIMULATION
    // Debug signals for waveform analysis
    logic signed [ACCUM_WIDTH-1:0] debug_feedback_sum;
    logic signed [DATA_WIDTH-1:0]  debug_compensated;
    logic signed [DATA_WIDTH-1:0]  debug_decision;

    assign debug_feedback_sum = feedback_sum;
    assign debug_compensated  = compensated_input;
    assign debug_decision     = decision;
`endif
```

---

## 9. Testbench Requirements

### 9.1 Testbench Module Template

```systemverilog
`timescale 1ns / 1ps

module dfe_tb #(
    parameter SIM_TIMEOUT = 200000  // 200 µs (longer for BER tests)
);

    // Clock generation
    logic clk = 0;
    always #1.6 clk = ~clk;  // 312.5 MHz

    // DUT signals
    logic       rst_n;
    logic signed [7:0]  data_in;
    logic signed [7:0]  data_out;
    logic       decision_valid;
    logic       coeff_wr_en;
    logic [2:0] coeff_addr;
    logic signed [9:0]  coeff_data;
    logic       coeff_updated;
    logic signed [7:0]  threshold [0:2];
    logic       modulation;

    // DUT instantiation
    dfe #(
        .TAP_COUNT(5),
        .DATA_WIDTH(8),
        .COEFF_WIDTH(10)
    ) dut (.*);

    // VCD dump
    initial begin
        $dumpfile("sim/waves/dfe.vcd");
        $dumpvars(0, dfe_tb);
    end

    // Helper task: Program coefficient
    task program_coeff(input int addr, input int value);
        begin
            @(posedge clk);
            coeff_wr_en = 1'b1;
            coeff_addr = addr;
            coeff_data = value;
            @(posedge clk);
            coeff_wr_en = 1'b0;
            @(posedge clk);  // Wait for coeff_updated pulse
        end
    endtask

    // Test sequence
    int error_count = 0;
    initial begin
        // (See section 7 for test procedures)

        if (error_count == 0) begin
            $display("*** PASSED: All DFE tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end
        $finish;
    end

    // Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
```

### 9.2 Test Configuration (test_config.yaml)

```yaml
- name: dfe
  enabled: true
  description: "DFE 5-tap decision feedback equalizer test"
  top_module: dfe_tb
  testbench_file: dfe_tb.sv
  rtl_files:
    - dfe.sv
  verilator_extra_flags:
    - --trace-underscore
  sim_timeout: "200us"  # Longer for BER measurements
```

---

## 10. References

### 10.1 Standards
- **PCIe Base Specification** (v3.0/4.0/5.0): Receiver equalization requirements
- **OIF-CEI-03.0**: Common Electrical I/O Implementation Agreement

### 10.2 Papers
- J. Winters, R. Gitlin, "Electrical Signal Processing Techniques in Long-Haul Fiber-Optic Systems"
- J. Cioffi, "A Multicarrier Primer" (DFE fundamentals)

### 10.3 Related Documents
- `spec/ffe_specification.md` - Feed-Forward Equalizer
- `spec/ctle_specification.md` - Continuous-Time Linear Equalizer
- `spec/serdes_architecture.md` - System-level SerDes architecture

---

## 11. Revision History

| Version | Date       | Author | Description                     |
|---------|------------|--------|---------------------------------|
| 1.0     | 2025-01-11 | Claude | Initial specification creation  |

---

## Appendix A: DFE vs. FFE Comparison

| Aspect              | FFE (Feed-Forward)                 | DFE (Decision Feedback)           |
|---------------------|------------------------------------|------------------------------------|
| **Input**           | Raw noisy samples                  | Equalized samples (after FFE/CTLE) |
| **Feedback**        | None (purely feedforward)          | Past detected symbols              |
| **Noise**           | Amplifies high-frequency noise     | No noise amplification             |
| **ISI**             | Cancels pre and post-cursor ISI    | Only post-cursor ISI               |
| **Linearity**       | Linear filter (FIR)                | Nonlinear (uses hard decisions)    |
| **Timing**          | Easy to meet timing                | Critical feedback path timing      |
| **Performance**     | Good for mild ISI                  | Better for severe ISI              |
| **Typical Placement** | Tx (pre-emphasis) or early Rx    | Late Rx (after FFE/CTLE)           |

**Best Practice**: Use **FFE + DFE in cascade** for optimal equalization (FFE removes pre-cursor, DFE removes post-cursor).

---

**End of DFE Specification**
