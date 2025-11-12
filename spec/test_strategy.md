# SerDes Test Strategy and Verification Plan

**Document Version**: 1.0
**Last Updated**: 2025-01-11
**Target**: High-Speed SerDes (10-25 Gbps) for PCIe Gen3/4/5
**Verification Approach**: Hierarchical testing with self-checking testbenches

---

## 1. Verification Philosophy

### 1.1 Objectives

The verification strategy ensures that:
1. **Functional Correctness**: All blocks implement specifications accurately
2. **Integration Integrity**: Blocks work together correctly in full system
3. **Standard Compliance**: SerDes meets PCIe Gen3/4/5 requirements
4. **Performance Targets**: BER < 1e-12, eye opening sufficient, jitter within limits
5. **Corner Case Coverage**: Edge cases, saturation, overflow handled properly

### 1.2 Verification Hierarchy

```
┌─────────────────────────────────────────────────────┐
│              VERIFICATION PYRAMID                   │
│                                                     │
│         ┌──────────────────────┐                   │
│         │  System/Compliance   │ (100ms sim)       │
│         │  ├─ PCIe compliance  │ Days to run       │
│         │  ├─ Multi-lane       │ Highest value     │
│         │  └─ BER measurement  │                   │
│         └──────────────────────┘                   │
│                    ▲                                │
│         ┌──────────┴──────────┐                    │
│         │   Integration Tests  │ (1-10ms sim)      │
│         │   ├─ Tx-Rx loopback │ Hours to run      │
│         │   ├─ Tx-only        │ High value        │
│         │   └─ Rx-only        │                   │
│         └─────────────────────┘                    │
│                    ▲                                │
│    ┌───────────────┴───────────────┐               │
│    │        Unit Tests              │ (10-100µs)   │
│    │        ├─ FFE                  │ Minutes      │
│    │        ├─ DFE                  │ Medium value │
│    │        ├─ CTLE                 │ Fast feedback│
│    │        ├─ Serializer           │              │
│    │        └─ Deserializer         │              │
│    └────────────────────────────────┘              │
│                                                     │
│ Width of pyramid = Number of tests                 │
│ Height = Simulation time & complexity              │
└─────────────────────────────────────────────────────┘
```

**Strategy**: Many fast unit tests (quick feedback), fewer slow system tests (comprehensive validation).

---

## 2. Test Levels and Scope

### 2.1 Unit Tests (L1 - Block Level)

**Purpose**: Verify individual RTL modules in isolation.

**Scope**: Single module (`ffe.sv`, `dfe.sv`, `ctle_rnm.sv`, etc.)

**Test Approach**:
- Directed tests (specific input patterns with known expected outputs)
- Self-checking (testbench compares output to expected, counts errors)
- Parametric sweep (vary parameters to test configurability)
- Corner cases (saturation, overflow, reset, coefficient extremes)

**Coverage Goals**:
- **Code coverage**: 100% line, 95%+ branch, 90%+ toggle
- **Functional coverage**: All major features exercised
- **Parameter coverage**: Min, max, typical values tested

**Example Tests**:
| Module       | Test Name              | Description                              | Duration |
|--------------|------------------------|------------------------------------------|----------|
| `ffe.sv`     | `ffe_impulse`          | Impulse response with single tap         | 10 µs    |
| `ffe.sv`     | `ffe_pre_emphasis`     | Pre-emphasis with negative coefficients  | 20 µs    |
| `ffe.sv`     | `ffe_coeff_update`     | Dynamic coefficient programming          | 15 µs    |
| `dfe.sv`     | `dfe_bypass`           | Slicer-only mode (no feedback)           | 10 µs    |
| `dfe.sv`     | `dfe_single_tap`       | Single-tap feedback operation            | 20 µs    |
| `dfe.sv`     | `dfe_pam4_slicer`      | 4-level PAM4 slicing                     | 25 µs    |
| `ctle_rnm.sv`| `ctle_dc_response`     | DC gain verification                     | 5 µs     |
| `ctle_rnm.sv`| `ctle_frequency_sweep` | Bode plot generation                     | 50 µs    |

**Total Unit Tests**: ~30 tests, ~30 minutes simulation time

### 2.2 Integration Tests (L2 - Subsystem Level)

**Purpose**: Verify block interactions and data flow.

**Scope**: Multiple modules integrated (e.g., Tx path: FFE → Serializer → DAC)

**Test Approach**:
- Realistic data patterns (PRBS7, PRBS15, compliance patterns)
- Interface protocol checking (valid signals, clock domain crossing)
- End-to-end data integrity (compare Tx input to Rx output)

**Coverage Goals**:
- **Interface coverage**: All signal transitions exercised
- **Scenario coverage**: NRZ and PAM4 modes, all data rates
- **Error injection**: ISI, jitter, noise added to test robustness

**Example Tests**:
| Subsystem        | Test Name                | Description                            | Duration |
|------------------|--------------------------|----------------------------------------|----------|
| Tx-only          | `tx_nrz_prbs7`           | Tx NRZ PRBS7 pattern generation        | 100 µs   |
| Tx-only          | `tx_pam4_prbs15`         | Tx PAM4 PRBS15 pattern generation      | 200 µs   |
| Rx-only          | `rx_ideal_input`         | Rx with no channel loss (ideal)        | 100 µs   |
| Rx-only          | `rx_lossy_channel`       | Rx with 20 dB channel loss             | 200 µs   |
| Tx-Rx loopback   | `loopback_nrz_10gbps`    | Full link 10 Gbps NRZ                  | 1 ms     |
| Tx-Rx loopback   | `loopback_pam4_32gbps`   | Full link 32 Gbps PAM4                 | 2 ms     |

**Total Integration Tests**: ~20 tests, ~2 hours simulation time

### 2.3 System Tests (L3 - Full SerDes)

**Purpose**: Verify complete system functionality and performance.

**Scope**: Full Tx-Channel-Rx system with realistic impairments

**Test Approach**:
- Long-duration BER tests (millions of bits)
- Eye diagram generation and measurement
- Jitter tolerance testing
- Channel sweep (varying loss profiles)
- Equalization adaptation verification

**Coverage Goals**:
- **BER target**: < 1e-12 for compliant channels
- **Eye opening**: Meet PCIe mask requirements
- **Jitter tolerance**: Pass PCIe jitter tolerance spec

**Example Tests**:
| System Test          | Description                                | Duration |
|----------------------|--------------------------------------------|----------|
| `ber_nrz_10gbps`     | BER measurement at 10 Gbps NRZ (1e9 bits)  | 10 ms    |
| `ber_pam4_32gbps`    | BER measurement at 32 Gbps PAM4 (1e9 bits) | 20 ms    |
| `eye_diagram_nrz`    | Eye diagram capture (NRZ)                  | 5 ms     |
| `eye_diagram_pam4`   | Eye diagram capture (PAM4, 3 eyes)         | 10 ms    |
| `jitter_tolerance`   | Sweep jitter amplitude vs. BER             | 50 ms    |
| `channel_sweep`      | Test 5 different channel profiles          | 50 ms    |

**Total System Tests**: ~15 tests, ~2 days simulation time

### 2.4 Compliance Tests (L4 - Standard Verification)

**Purpose**: Verify compliance with PCIe specifications.

**Scope**: Tests derived directly from PCIe spec requirements

**Test Approach**:
- Tx eye mask testing (PCIe spec Figure X)
- Rx equalization compliance (coefficient ranges)
- Jitter generation and tolerance limits
- Transmit spectrum compliance (PSD limits)

**Example Tests**:
| Compliance Test          | PCIe Spec Section | Pass Criteria                    | Duration |
|--------------------------|-------------------|----------------------------------|----------|
| `tx_eye_mask_gen3`       | 4.2.2.3           | No violations of mask            | 20 ms    |
| `tx_eye_mask_gen4`       | (Gen4 spec)       | No violations of mask            | 20 ms    |
| `rx_jitter_tolerance`    | 4.2.2.6           | BER < 1e-12 at spec jitter       | 100 ms   |
| `tx_deemphasis_range`    | 4.2.2.3.1         | -6 dB and -3.5 dB within ±1 dB   | 10 ms    |
| `rx_ffe_coeff_range`     | (Rx spec)         | Coefficients within spec limits  | 5 ms     |

**Total Compliance Tests**: ~10 tests, ~1 week simulation time

---

## 3. Test Infrastructure

### 3.1 Testbench Architecture Pattern

All testbenches follow a common structure:

```systemverilog
`timescale 1ns / 1ps

module <module>_tb #(
    parameter SIM_TIMEOUT = <value>  // Simulation timeout
);

    // 1. Clock generation
    logic clk = 0;
    always #<period/2> clk = ~clk;

    // 2. DUT signals and instantiation
    // ... (DUT ports)
    <module> #(...) dut (...);

    // 3. VCD dump
    initial begin
        $dumpfile("sim/waves/<test_name>.vcd");
        $dumpvars(0, <module>_tb);
    end

    // 4. Helper tasks and functions
    task apply_pattern(...);
        // ...
    endtask

    function automatic int check_result(...);
        // ...
    endfunction

    // 5. Test sequence with error counting
    int error_count = 0;
    initial begin
        // Initialization
        reset_dut();

        // Test cases
        test_case_1();
        test_case_2();
        // ...

        // Summary
        if (error_count == 0) begin
            $display("*** PASSED: All tests passed ***");
        end else begin
            $display("*** FAILED: %0d errors ***", error_count);
        end
        $finish;
    end

    // 6. Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
```

### 3.2 Self-Checking Methodology

**Pattern**: Testbenches automatically verify correctness without manual waveform inspection.

#### 3.2.1 Directed Checks

```systemverilog
// Example: Check expected value
if (data_out !== expected_value) begin
    $display("ERROR at time=%0t: data_out=%h, expected=%h",
             $time, data_out, expected_value);
    error_count++;
end
```

#### 3.2.2 Golden Reference Model

```systemverilog
// Example: Compare against software model
logic signed [7:0] expected_ffe_out;
expected_ffe_out = ffe_golden_model(data_in, coefficients);

if (dut.data_out !== expected_ffe_out) begin
    $display("ERROR: DUT mismatch with golden model");
    error_count++;
end
```

#### 3.2.3 Statistical Checks

```systemverilog
// Example: BER measurement
int bit_count = 0;
int error_bits = 0;

for (int i = 0; i < 1000000; i++) begin
    bit_count++;
    if (rx_bit !== expected_bit) error_bits++;
end

real ber = real'(error_bits) / real'(bit_count);
if (ber > 1.0e-6) begin
    $display("ERROR: BER=%e exceeds threshold", ber);
    error_count++;
end
```

### 3.3 Test Vector Management

**Challenge**: Large test vectors (PRBS patterns, channel impulse responses) should not be hardcoded.

**Solution**: Use file I/O for test vector storage.

#### 3.3.1 Directory Structure

```
spec/test_vectors/
├── prbs7_nrz.hex          # PRBS7 NRZ pattern (hex format)
├── prbs15_pam4.hex        # PRBS15 PAM4 pattern
├── channel_short.csv      # Short channel impulse response
├── channel_medium.csv     # Medium channel impulse response
├── channel_long.csv       # Long channel impulse response
├── pcie_compliance_pattern_gen3.hex
└── pcie_compliance_pattern_gen4.hex
```

#### 3.3.2 Test Vector Loading

```systemverilog
// Load test vectors from file
logic [7:0] test_data [0:65535];  // 64K samples
initial begin
    $readmemh("spec/test_vectors/prbs7_nrz.hex", test_data);
end

// Apply test vectors in testbench
for (int i = 0; i < 65536; i++) begin
    @(posedge clk);
    data_in = test_data[i];
end
```

#### 3.3.3 Test Vector Generation

**Tool**: Python script to generate test vectors.

```python
# scripts/generate_test_vectors.py
import numpy as np

def generate_prbs7(length):
    """Generate PRBS7 pattern (2^7 - 1 = 127 bits periodic)"""
    lfsr = 0x7F  # Seed
    pattern = []
    for _ in range(length):
        bit = ((lfsr >> 6) ^ (lfsr >> 5)) & 1
        pattern.append(bit)
        lfsr = ((lfsr << 1) | bit) & 0x7F
    return pattern

def save_hex(filename, data, width=8):
    """Save data to hex file for $readmemh()"""
    with open(filename, 'w') as f:
        for value in data:
            f.write(f"{value:0{width//4}X}\n")

# Generate 64K samples of PRBS7
prbs7 = generate_prbs7(65536)
save_hex("spec/test_vectors/prbs7_nrz.hex", prbs7, width=8)
```

---

## 4. Performance Measurement

### 4.1 BER (Bit Error Rate) Measurement

**Objective**: Measure bit error rate to verify system meets < 1e-12 target.

#### 4.1.1 BER Test Procedure

```systemverilog
module ber_measurement_tb;
    // ... (DUT instantiation)

    // PRBS generator (Tx side)
    logic prbs_bit;
    lfsr_prbs7 tx_prbs (.clk(tx_clk), .out(prbs_bit));

    // PRBS checker (Rx side)
    logic expected_bit;
    lfsr_prbs7 rx_prbs (.clk(rx_clk), .out(expected_bit));

    // BER counter
    longint bit_count = 0;
    longint error_count = 0;

    always @(posedge rx_clk) begin
        if (cdr_locked) begin
            bit_count++;
            if (rx_data !== expected_bit) begin
                error_count++;
                $display("BIT ERROR at bit %0d", bit_count);
            end
        end
    end

    // Report BER after N bits
    initial begin
        wait (bit_count >= 1_000_000_000);  // 1 billion bits
        real ber = real'(error_count) / real'(bit_count);
        $display("BER = %e (%0d errors in %0d bits)",
                 ber, error_count, bit_count);

        if (ber < 1.0e-12) begin
            $display("*** PASSED: BER < 1e-12 ***");
        end else begin
            $display("*** FAILED: BER = %e (target < 1e-12) ***", ber);
        end
        $finish;
    end
endmodule
```

**Simulation Time**: 1 billion bits @ 10 Gbps = 100 ms real time → ~hours in simulation (depends on performance).

#### 4.1.2 Confidence Interval

For BER = 1e-12, need to test **at least 100 billion bits** to see ~100 errors for statistical confidence.

**Practical Approach**: Test at higher BER (1e-6 to 1e-9) with channel stress, then extrapolate.

### 4.2 Eye Diagram Generation

**Objective**: Visualize signal quality by overlaying many UI (unit interval) samples.

#### 4.2.1 Eye Diagram Capture Procedure

```systemverilog
module eye_diagram_capture_tb;
    // ... (DUT instantiation)

    // Eye capture: Sample signal at multiple time offsets within 1 UI
    real eye_samples [0:1000][0:99];  // 1000 UIs × 100 samples per UI
    int ui_count = 0;
    int sample_idx;

    always @(posedge sample_clk) begin  // High-rate sampling clock
        if (ui_count < 1000) begin
            sample_idx = $time % UI_PERIOD * 100 / UI_PERIOD;
            eye_samples[ui_count][sample_idx] = rx_signal;
        end
    end

    always @(posedge ui_clk) begin  // UI boundary clock
        ui_count++;
    end

    // Export eye data to file for plotting
    initial begin
        int fd;
        wait (ui_count >= 1000);
        fd = $fopen("sim/results/eye_diagram.csv", "w");
        for (int ui = 0; ui < 1000; ui++) begin
            for (int sample = 0; sample < 100; sample++) begin
                $fwrite(fd, "%f,%f\n",
                        sample * UI_PERIOD / 100.0,
                        eye_samples[ui][sample]);
            end
        end
        $fclose(fd);
        $finish;
    end
endmodule
```

#### 4.2.2 Eye Diagram Post-Processing (Python)

```python
# scripts/plot_eye_diagram.py
import numpy as np
import matplotlib.pyplot as plt

# Load eye data
data = np.loadtxt("sim/results/eye_diagram.csv", delimiter=',')
time = data[:, 0]
voltage = data[:, 1]

# Plot
plt.figure(figsize=(10, 6))
plt.plot(time, voltage, 'b.', markersize=0.5, alpha=0.1)
plt.xlabel('Time (ps)')
plt.ylabel('Voltage (V)')
plt.title('Eye Diagram (NRZ 10 Gbps)')
plt.grid(True)
plt.savefig('sim/results/eye_diagram.png')
```

#### 4.2.3 Eye Metrics Extraction

From eye diagram, measure:
- **Eye Height**: Vertical opening (mV) → SNR indicator
- **Eye Width**: Horizontal opening (ps) → Jitter indicator
- **Eye Area**: Height × Width → Overall quality metric

**Pass Criteria** (PCIe Gen3 example):
- Eye height > 100 mV
- Eye width > 0.5 UI (50 ps at 10 Gbps)

### 4.3 Jitter Measurement and Injection

#### 4.3.1 Jitter Types

- **Random Jitter (RJ)**: Gaussian distribution, measured in ps RMS
- **Deterministic Jitter (DJ)**: Periodic or data-dependent, measured in peak-to-peak
- **Total Jitter (TJ)**: TJ = RJ + DJ (statistical combination)

#### 4.3.2 Jitter Injection (Testbench)

```systemverilog
// Inject random jitter into Tx clock
real jitter_rms_ps = 1.0;  // 1 ps RMS jitter
real jitter_ps;

always @(ideal_clk_edge) begin
    jitter_ps = $dist_normal(0, jitter_rms_ps);  // Gaussian distribution
    #(jitter_ps / 1000.0) tx_clk = ~tx_clk;      // Apply jitter (ps → ns)
end
```

#### 4.3.3 Jitter Tolerance Test

**Objective**: Verify Rx can tolerate specified jitter amplitude.

**Procedure**:
1. Sweep jitter amplitude: 0.1 ps to 10 ps RMS
2. For each jitter level, measure BER
3. Plot BER vs. Jitter (bathtub curve)
4. Find jitter tolerance limit (jitter at BER = 1e-12)

**Pass Criteria**: Jitter tolerance > 0.3 UI RMS (PCIe requirement).

---

## 5. Test Automation and Reporting

### 5.1 Regression Test Suite

**Goal**: Run all tests automatically, generate pass/fail report.

#### 5.1.1 Test List (test_config.yaml)

Already using `test_config.yaml` for test configuration. Add test level classification:

```yaml
tests:
  - name: ffe_impulse
    level: unit
    enabled: true
    timeout: 10us
    expected_result: pass

  - name: loopback_nrz_10gbps
    level: integration
    enabled: true
    timeout: 1ms
    expected_result: pass

  - name: ber_nrz_10gbps
    level: system
    enabled: false  # Disable for quick regression (too slow)
    timeout: 10ms
    expected_result: pass
```

#### 5.1.2 Test Runner Script Enhancement

```python
# scripts/run_test.py (enhancement)

def run_regression(test_level='all'):
    """Run all tests of specified level"""
    config = load_test_config("tests/test_config.yaml")

    results = []
    for test in config['tests']:
        if test['enabled']:
            if test_level == 'all' or test['level'] == test_level:
                result = run_single_test(test)
                results.append(result)

    generate_report(results)

def generate_report(results):
    """Generate HTML test report"""
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')

    with open('sim/results/test_report.html', 'w') as f:
        f.write(f"<h1>Test Report</h1>")
        f.write(f"<p>Passed: {passed}/{len(results)}</p>")
        f.write(f"<p>Failed: {failed}/{len(results)}</p>")
        # ... (detailed table of results)
```

### 5.2 Coverage Collection

**Tool**: Verilator supports code coverage with `--coverage` flag.

#### 5.2.1 Enable Coverage in test_config.yaml

```yaml
verilator:
  extra_flags:
    - --coverage  # Enable line/toggle coverage
    - --coverage-line
    - --coverage-toggle
```

#### 5.2.2 Coverage Report Generation

```bash
# After running tests
verilator_coverage --annotate sim/coverage_report/ sim/obj_dir/coverage.dat
```

#### 5.2.3 Coverage Targets

| Metric          | Target | Description                               |
|-----------------|--------|-------------------------------------------|
| Line Coverage   | 100%   | Every line executed                       |
| Branch Coverage | 95%+   | All if/else branches taken                |
| Toggle Coverage | 90%+   | All signals toggled 0→1 and 1→0           |
| FSM Coverage    | 100%   | All states and transitions visited        |

---

## 6. Simulation Performance Optimization

### 6.1 Challenges

- **Long BER tests**: 1 billion bits @ 10 Gbps = 100 ms real time → hours in simulation
- **Eye diagram capture**: 1000s of UIs with high sample rate = large VCD files
- **System tests**: Full Tx-Channel-Rx with equalization = complex, slow

### 6.2 Optimization Strategies

#### 6.2.1 Verilator Optimization Flags

```yaml
verilator:
  optimization_flags:
    - --x-assign fast       # Fast X propagation
    - --x-initial fast
    - -O3                   # Maximum C++ optimization
    - --inline-mult 1000    # Aggressive inlining
```

#### 6.2.2 Selective VCD Dumping

```systemverilog
// Only dump signals of interest for debug
initial begin
    $dumpfile("sim/waves/test.vcd");
    $dumpvars(1, dut.ffe);  // Only FFE module (depth 1)
    // NOT: $dumpvars(0, dut);  // Would dump everything (slow)
end
```

#### 6.2.3 Parallel Test Execution

Run independent tests in parallel using GNU Parallel or similar:

```bash
# Run all unit tests in parallel (4 jobs at once)
parallel -j 4 'python3 scripts/run_test.py --test {}' ::: ffe_impulse ffe_pre_emphasis dfe_bypass ctle_dc_response
```

#### 6.2.4 Fast Functional Models

For long tests, use simplified channel models:

```systemverilog
// Fast channel model: FIR filter with few taps (not realistic, but fast)
module channel_fast (
    input  real signal_in,
    output real signal_out
);
    // 3-tap FIR (instead of 100-tap for accuracy)
    assign signal_out = 0.8*signal_in + 0.15*prev1 + 0.05*prev2;
endmodule
```

### 6.3 Simulation Time Budgets

| Test Level  | Tests | Avg Duration | Total Time | Frequency     |
|-------------|-------|--------------|------------|---------------|
| Unit        | 30    | 30 µs        | ~1 min     | Every commit  |
| Integration | 20    | 500 µs       | ~30 min    | Daily         |
| System      | 15    | 10 ms        | ~8 hours   | Weekly        |
| Compliance  | 10    | 50 ms        | ~2 days    | Release only  |

---

## 7. PCIe Compliance Test Details

### 7.1 PCIe Gen3/4/5 Requirements Summary

| Parameter                | Gen3 (8 Gbps)    | Gen4 (16 Gbps)   | Gen5 (32 Gbps PAM4) |
|--------------------------|------------------|------------------|---------------------|
| **Modulation**           | NRZ              | NRZ              | PAM4                |
| **Tx Eye Height**        | > 100 mV         | > 100 mV         | > 15 mV (per eye)   |
| **Tx Eye Width**         | > 0.4 UI         | > 0.3 UI         | > 0.25 UI           |
| **Tx Jitter (RJ)**       | < 2 ps RMS       | < 1.5 ps RMS     | < 1.0 ps RMS        |
| **Tx De-emphasis**       | -6 dB / -3.5 dB  | -6 dB / -3.5 dB  | N/A (PAM4)          |
| **Rx Jitter Tolerance**  | 0.55 UI          | 0.4 UI           | 0.3 UI              |
| **BER Target**           | < 1e-12          | < 1e-12          | < 1e-12             |

### 7.2 Compliance Test Checklist

#### 7.2.1 Transmitter Tests

- [ ] **TX.1**: Differential output voltage (800-1200 mV pp)
- [ ] **TX.2**: Eye mask compliance (no violations)
- [ ] **TX.3**: Rise/fall time (< 60 ps 20%-80%)
- [ ] **TX.4**: De-emphasis levels (-6 dB ±1 dB, -3.5 dB ±1 dB)
- [ ] **TX.5**: Tx equalization coefficient range
- [ ] **TX.6**: Transmit jitter (RJ < 2 ps, TJ < 0.25 UI)
- [ ] **TX.7**: Spread spectrum clocking (SSC) compliance

#### 7.2.2 Receiver Tests

- [ ] **RX.1**: Minimum input sensitivity (-100 mV differential)
- [ ] **RX.2**: Jitter tolerance (survive 0.55 UI RJ at BER 1e-12)
- [ ] **RX.3**: Frequency offset tolerance (±300 ppm)
- [ ] **RX.4**: Rx equalization range (CTLE, FFE, DFE within spec)
- [ ] **RX.5**: CDR lock time (< 1000 UI)

---

## 8. Pass/Fail Criteria Summary

### 8.1 Unit Test Criteria

| Module       | Pass Criteria                                           |
|--------------|---------------------------------------------------------|
| FFE          | Output matches expected ±1 LSB for all test patterns   |
| DFE          | Slicer levels correct ±2 LSB, feedback within ±1 LSB    |
| CTLE         | Frequency response within ±1 dB of theoretical          |
| Serializer   | No bit errors in serial stream (compare to parallel)    |
| Deserializer | No bit errors in parallel output (compare to serial)    |

### 8.2 Integration Test Criteria

| Test              | Pass Criteria                                        |
|-------------------|------------------------------------------------------|
| Tx-only           | Signal swing within 10% of target, no saturation     |
| Rx-only           | Recover 90%+ of bits correctly with 20 dB channel    |
| Tx-Rx loopback    | BER < 1e-9 for 10M bits (quick check)                |

### 8.3 System Test Criteria

| Test                | Pass Criteria                                     |
|---------------------|---------------------------------------------------|
| BER measurement     | BER < 1e-12 for ≥ 100M bits                       |
| Eye diagram         | Eye height > 100 mV, Eye width > 0.4 UI           |
| Jitter tolerance    | BER < 1e-12 with 0.55 UI RJ injected              |

### 8.4 Compliance Test Criteria

**Overall**: Pass ALL PCIe spec requirements for target generation (Gen3/4/5).

---

## 9. Recommended Test Execution Order

### 9.1 Development Phase (Feature Bring-Up)

**Stage 1**: Basic Functionality
1. Unit tests for FFE (ensure filter works)
2. Unit tests for DFE (ensure slicer + feedback works)
3. Unit tests for CTLE (ensure frequency response correct)

**Stage 2**: Integration
4. Tx-only test (verify Tx chain produces clean signal)
5. Rx-only test (verify Rx chain recovers known input)
6. Loopback test (verify full link works end-to-end)

**Stage 3**: Performance
7. BER measurement (verify < 1e-12 target)
8. Eye diagram (verify eye opening sufficient)

### 9.2 Regression Testing (Ongoing)

**Daily Regression** (fast tests only):
- All unit tests (~1 min)
- Integration tests with short duration (~10 min)

**Weekly Regression** (includes slow tests):
- Full test suite including system tests (~8 hours)

**Release Regression** (comprehensive):
- Full test suite + compliance tests (~3 days)

---

## 10. References

### 10.1 Standards
- **PCI Express Base Specification** Rev 3.0/4.0/5.0/6.0
- **IEEE 802.3**: Ethernet compliance testing methodologies

### 10.2 Tools
- **Verilator**: Open-source SystemVerilog simulator
- **GTKWave**: Waveform viewer
- **Python**: Test automation and post-processing

### 10.3 Related Documents
- `spec/ffe_specification.md` - FFE unit test details
- `spec/dfe_specification.md` - DFE unit test details
- `spec/ctle_specification.md` - CTLE unit test details
- `spec/serdes_architecture.md` - System integration details
- `README.md` - Project setup and execution instructions

---

## 11. Revision History

| Version | Date       | Author | Description                            |
|---------|------------|--------|----------------------------------------|
| 1.0     | 2025-01-11 | Claude | Initial test strategy and verification plan |

---

**End of SerDes Test Strategy Specification**
