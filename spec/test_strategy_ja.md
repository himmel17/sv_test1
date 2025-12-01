# SerDes テスト戦略および検証計画

**ドキュメントバージョン**: 1.0
**最終更新日**: 2025-01-11
**対象**: 高速SerDes (10-25 Gbps) PCIe Gen3/4/5向け
**検証アプローチ**: セルフチェックテストベンチを用いた階層的テスト

---

## 1. 検証哲学

### 1.1 目的

検証戦略は以下を保証する：
1. **機能的正確性**: すべてのブロックが仕様を正確に実装していること
2. **統合完全性**: ブロックが完全なシステムで正しく連携すること
3. **標準準拠**: SerDesがPCIe Gen3/4/5要件を満たすこと
4. **性能目標**: BER < 1e-12、十分なeye opening、制限内のjitter
5. **コーナーケースカバレッジ**: エッジケース、飽和、オーバーフローが適切に処理されること

### 1.2 検証階層

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

**戦略**: 多くの高速ユニットテスト（迅速なフィードバック）、少数の低速システムテスト（包括的検証）。

---

## 2. テストレベルと範囲

### 2.1 ユニットテスト (L1 - ブロックレベル)

**目的**: 個々のRTLモジュールを独立して検証する。

**範囲**: 単一モジュール（`ffe.sv`、`dfe.sv`、`ctle_rnm.sv`等）

**テストアプローチ**:
- Directedテスト（既知の期待出力を持つ特定の入力パターン）
- セルフチェック（テストベンチが出力を期待値と比較し、エラーをカウント）
- パラメトリックスイープ（パラメータを変化させて設定可能性をテスト）
- コーナーケース（飽和、オーバーフロー、リセット、係数の極値）

**カバレッジ目標**:
- **コードカバレッジ**: 100% line、95%+ branch、90%+ toggle
- **機能カバレッジ**: すべての主要機能が実行されること
- **パラメータカバレッジ**: 最小、最大、典型値がテストされること

**テスト例**:
| モジュール   | テスト名               | 説明                                     | 期間     |
|--------------|------------------------|------------------------------------------|----------|
| `ffe.sv`     | `ffe_impulse`          | 単一タップのインパルス応答               | 10 µs    |
| `ffe.sv`     | `ffe_pre_emphasis`     | 負の係数によるpre-emphasis               | 20 µs    |
| `ffe.sv`     | `ffe_coeff_update`     | 動的係数プログラミング                   | 15 µs    |
| `dfe.sv`     | `dfe_bypass`           | スライサーのみモード（フィードバックなし）| 10 µs    |
| `dfe.sv`     | `dfe_single_tap`       | 単一タップフィードバック動作             | 20 µs    |
| `dfe.sv`     | `dfe_pam4_slicer`      | 4レベルPAM4スライシング                  | 25 µs    |
| `ctle_rnm.sv`| `ctle_dc_response`     | DCゲイン検証                             | 5 µs     |
| `ctle_rnm.sv`| `ctle_frequency_sweep` | Bode線図生成                             | 50 µs    |

**総ユニットテスト**: 約30テスト、約30分のシミュレーション時間

### 2.2 統合テスト (L2 - サブシステムレベル)

**目的**: ブロック間の相互作用とデータフローを検証する。

**範囲**: 複数モジュールの統合（例: Txパス: FFE → Serializer → DAC）

**テストアプローチ**:
- 現実的なデータパターン（PRBS7、PRBS15、準拠パターン）
- インターフェースプロトコルチェック（valid信号、クロックドメインクロッシング）
- エンドツーエンドデータ完全性（Tx入力とRx出力を比較）

**カバレッジ目標**:
- **インターフェースカバレッジ**: すべての信号遷移が実行されること
- **シナリオカバレッジ**: NRZおよびPAM4モード、すべてのデータレート
- **エラー注入**: ISI、jitter、ノイズを追加してロバスト性をテスト

**テスト例**:
| サブシステム | テスト名                 | 説明                                   | 期間     |
|--------------|--------------------------|----------------------------------------|----------|
| Tx-only      | `tx_nrz_prbs7`           | Tx NRZ PRBS7パターン生成               | 100 µs   |
| Tx-only      | `tx_pam4_prbs15`         | Tx PAM4 PRBS15パターン生成             | 200 µs   |
| Rx-only      | `rx_ideal_input`         | 理想的な入力（チャネル損失なし）       | 100 µs   |
| Rx-only      | `rx_lossy_channel`       | 20 dBチャネル損失                      | 200 µs   |
| Tx-Rx loopback | `loopback_nrz_10gbps`  | フルリンク 10 Gbps NRZ                 | 1 ms     |
| Tx-Rx loopback | `loopback_pam4_32gbps` | フルリンク 32 Gbps PAM4                | 2 ms     |

**総統合テスト**: 約20テスト、約2時間のシミュレーション時間

### 2.3 システムテスト (L3 - フルSerDes)

**目的**: 完全なシステム機能と性能を検証する。

**範囲**: フルTx-Channel-Rxシステムと現実的な劣化

**テストアプローチ**:
- 長期間BERテスト（数百万ビット）
- Eye diagram生成と測定
- Jitter許容度テスト
- チャネルスイープ（損失プロファイルの変化）
- 等化適応検証

**カバレッジ目標**:
- **BER目標**: 準拠チャネルで < 1e-12
- **Eye opening**: PCIeマスク要件を満たすこと
- **Jitter許容度**: PCIe jitter許容度仕様に合格

**テスト例**:
| システムテスト       | 説明                                       | 期間     |
|----------------------|--------------------------------------------|----------|
| `ber_nrz_10gbps`     | 10 Gbps NRZでのBER測定（1e9ビット）        | 10 ms    |
| `ber_pam4_32gbps`    | 32 Gbps PAM4でのBER測定（1e9ビット）       | 20 ms    |
| `eye_diagram_nrz`    | Eye diagramキャプチャ（NRZ）               | 5 ms     |
| `eye_diagram_pam4`   | Eye diagramキャプチャ（PAM4、3つのeye）    | 10 ms    |
| `jitter_tolerance`   | Jitter振幅対BERのスイープ                  | 50 ms    |
| `channel_sweep`      | 5つの異なるチャネルプロファイルをテスト    | 50 ms    |

**総システムテスト**: 約15テスト、約2日のシミュレーション時間

### 2.4 準拠テスト (L4 - 標準検証)

**目的**: PCIe仕様への準拠を検証する。

**範囲**: PCIe仕様要件から直接導出されたテスト

**テストアプローチ**:
- Tx eyeマスクテスト（PCIe仕様 図X）
- Rx等化準拠（係数範囲）
- Jitter生成と許容度限界
- 送信スペクトル準拠（PSD制限）

**テスト例**:
| 準拠テスト               | PCIe仕様セクション | 合格基準                             | 期間     |
|--------------------------|-------------------|--------------------------------------|----------|
| `tx_eye_mask_gen3`       | 4.2.2.3           | マスク違反なし                       | 20 ms    |
| `tx_eye_mask_gen4`       | (Gen4仕様)        | マスク違反なし                       | 20 ms    |
| `rx_jitter_tolerance`    | 4.2.2.6           | 仕様jitterでBER < 1e-12              | 100 ms   |
| `tx_deemphasis_range`    | 4.2.2.3.1         | -6 dBおよび-3.5 dBが±1 dB以内        | 10 ms    |
| `rx_ffe_coeff_range`     | (Rx仕様)          | 係数が仕様制限内                     | 5 ms     |

**総準拠テスト**: 約10テスト、約1週間のシミュレーション時間

---

## 3. テストインフラストラクチャ

### 3.1 テストベンチアーキテクチャパターン

すべてのテストベンチは共通の構造に従う：

```systemverilog
`timescale 1ns / 1ps

module <module>_tb #(
    parameter SIM_TIMEOUT = <value>  // シミュレーションタイムアウト
);

    // 1. クロック生成
    logic clk = 0;
    always #<period/2> clk = ~clk;

    // 2. DUT信号とインスタンス化
    // ... (DUTポート)
    <module> #(...) dut (...);

    // 3. VCDダンプ
    initial begin
        $dumpfile("sim/waves/<test_name>.vcd");
        $dumpvars(0, <module>_tb);
    end

    // 4. ヘルパータスクと関数
    task apply_pattern(...);
        // ...
    endtask

    function automatic int check_result(...);
        // ...
    endfunction

    // 5. エラーカウント付きテストシーケンス
    int error_count = 0;
    initial begin
        // 初期化
        reset_dut();

        // テストケース
        test_case_1();
        test_case_2();
        // ...

        // サマリー
        if (error_count == 0) begin
            $display("*** PASSED: All tests passed ***");
        end else begin
            $display("*** FAILED: %0d errors ***", error_count);
        end
        $finish;
    end

    // 6. タイムアウト監視
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
```

### 3.2 セルフチェック手法

**パターン**: テストベンチは手動の波形検査なしで正確性を自動検証する。

#### 3.2.1 Directedチェック

```systemverilog
// 例: 期待値のチェック
if (data_out !== expected_value) begin
    $display("ERROR at time=%0t: data_out=%h, expected=%h",
             $time, data_out, expected_value);
    error_count++;
end
```

#### 3.2.2 ゴールデンリファレンスモデル

```systemverilog
// 例: ソフトウェアモデルと比較
logic signed [7:0] expected_ffe_out;
expected_ffe_out = ffe_golden_model(data_in, coefficients);

if (dut.data_out !== expected_ffe_out) begin
    $display("ERROR: DUT mismatch with golden model");
    error_count++;
end
```

#### 3.2.3 統計的チェック

```systemverilog
// 例: BER測定
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

### 3.3 テストベクタ管理

**課題**: 大規模テストベクタ（PRBSパターン、チャネルインパルス応答）をハードコードすべきではない。

**解決策**: テストベクタ保存にファイルI/Oを使用する。

#### 3.3.1 ディレクトリ構造

```
spec/test_vectors/
├── prbs7_nrz.hex          # PRBS7 NRZパターン（hex形式）
├── prbs15_pam4.hex        # PRBS15 PAM4パターン
├── channel_short.csv      # 短距離チャネルインパルス応答
├── channel_medium.csv     # 中距離チャネルインパルス応答
├── channel_long.csv       # 長距離チャネルインパルス応答
├── pcie_compliance_pattern_gen3.hex
└── pcie_compliance_pattern_gen4.hex
```

#### 3.3.2 テストベクタ読み込み

```systemverilog
// ファイルからテストベクタを読み込み
logic [7:0] test_data [0:65535];  // 64Kサンプル
initial begin
    $readmemh("spec/test_vectors/prbs7_nrz.hex", test_data);
end

// テストベンチでテストベクタを適用
for (int i = 0; i < 65536; i++) begin
    @(posedge clk);
    data_in = test_data[i];
end
```

#### 3.3.3 テストベクタ生成

**ツール**: テストベクタ生成のためのPythonスクリプト。

```python
# scripts/generate_test_vectors.py
import numpy as np

def generate_prbs7(length):
    """PRBS7パターンを生成（2^7 - 1 = 127ビット周期）"""
    lfsr = 0x7F  # シード
    pattern = []
    for _ in range(length):
        bit = ((lfsr >> 6) ^ (lfsr >> 5)) & 1
        pattern.append(bit)
        lfsr = ((lfsr << 1) | bit) & 0x7F
    return pattern

def save_hex(filename, data, width=8):
    """$readmemh()用のhexファイルにデータを保存"""
    with open(filename, 'w') as f:
        for value in data:
            f.write(f"{value:0{width//4}X}\n")

# 64KサンプルのPRBS7を生成
prbs7 = generate_prbs7(65536)
save_hex("spec/test_vectors/prbs7_nrz.hex", prbs7, width=8)
```

---

## 4. 性能測定

### 4.1 BER (Bit Error Rate) 測定

**目的**: ビットエラーレートを測定してシステムが < 1e-12 目標を満たすことを検証する。

#### 4.1.1 BERテスト手順

```systemverilog
module ber_measurement_tb;
    // ... (DUTインスタンス化)

    // PRBS生成器（Tx側）
    logic prbs_bit;
    lfsr_prbs7 tx_prbs (.clk(tx_clk), .out(prbs_bit));

    // PRBSチェッカー（Rx側）
    logic expected_bit;
    lfsr_prbs7 rx_prbs (.clk(rx_clk), .out(expected_bit));

    // BERカウンタ
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

    // Nビット後にBERを報告
    initial begin
        wait (bit_count >= 1_000_000_000);  // 10億ビット
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

**シミュレーション時間**: 10億ビット @ 10 Gbps = 100 ms実時間 → シミュレーションで約数時間（性能に依存）。

#### 4.1.2 信頼区間

BER = 1e-12の場合、統計的信頼性のために**最低1000億ビット**をテストして約100エラーを確認する必要がある。

**実用的アプローチ**: チャネルストレスを加えたより高いBER（1e-6〜1e-9）でテストし、外挿する。

### 4.2 Eye Diagram生成

**目的**: 多くのUI（unit interval）サンプルをオーバーレイして信号品質を可視化する。

#### 4.2.1 Eye Diagramキャプチャ手順

```systemverilog
module eye_diagram_capture_tb;
    // ... (DUTインスタンス化)

    // Eye capture: 1 UI内の複数時間オフセットで信号をサンプリング
    real eye_samples [0:1000][0:99];  // 1000 UI × UI当たり100サンプル
    int ui_count = 0;
    int sample_idx;

    always @(posedge sample_clk) begin  // 高レートサンプリングクロック
        if (ui_count < 1000) begin
            sample_idx = $time % UI_PERIOD * 100 / UI_PERIOD;
            eye_samples[ui_count][sample_idx] = rx_signal;
        end
    end

    always @(posedge ui_clk) begin  // UI境界クロック
        ui_count++;
    end

    // プロット用にeyeデータをファイルにエクスポート
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

#### 4.2.2 Eye Diagram後処理（Python）

```python
# scripts/plot_eye_diagram.py
import numpy as np
import matplotlib.pyplot as plt

# eyeデータを読み込み
data = np.loadtxt("sim/results/eye_diagram.csv", delimiter=',')
time = data[:, 0]
voltage = data[:, 1]

# プロット
plt.figure(figsize=(10, 6))
plt.plot(time, voltage, 'b.', markersize=0.5, alpha=0.1)
plt.xlabel('Time (ps)')
plt.ylabel('Voltage (V)')
plt.title('Eye Diagram (NRZ 10 Gbps)')
plt.grid(True)
plt.savefig('sim/results/eye_diagram.png')
```

#### 4.2.3 Eye指標抽出

Eye diagramから測定：
- **Eye Height**: 垂直開口（mV）→ SNR指標
- **Eye Width**: 水平開口（ps）→ Jitter指標
- **Eye Area**: Height × Width → 全体的な品質指標

**合格基準**（PCIe Gen3例）:
- Eye height > 100 mV
- Eye width > 0.5 UI（10 Gbpsで50 ps）

### 4.3 Jitter測定と注入

#### 4.3.1 Jitter種類

- **Random Jitter (RJ)**: ガウス分布、ps RMSで測定
- **Deterministic Jitter (DJ)**: 周期的またはデータ依存、peak-to-peakで測定
- **Total Jitter (TJ)**: TJ = RJ + DJ（統計的組み合わせ）

#### 4.3.2 Jitter注入（テストベンチ）

```systemverilog
// Txクロックにランダムjitterを注入
real jitter_rms_ps = 1.0;  // 1 ps RMS jitter
real jitter_ps;

always @(ideal_clk_edge) begin
    jitter_ps = $dist_normal(0, jitter_rms_ps);  // ガウス分布
    #(jitter_ps / 1000.0) tx_clk = ~tx_clk;      // jitter適用（ps → ns）
end
```

#### 4.3.3 Jitter許容度テスト

**目的**: Rxが指定されたjitter振幅に耐えられることを検証する。

**手順**:
1. Jitter振幅をスイープ: 0.1 ps〜10 ps RMS
2. 各jitterレベルでBERを測定
3. BER対Jitterをプロット（bathtub曲線）
4. Jitter許容度限界を見つける（BER = 1e-12でのjitter）

**合格基準**: Jitter許容度 > 0.3 UI RMS（PCIe要件）。

---

## 5. テスト自動化とレポート

### 5.1 リグレッションテストスイート

**目標**: すべてのテストを自動実行し、合格/不合格レポートを生成する。

#### 5.1.1 テストリスト（test_config.yaml）

すでにテスト設定に`test_config.yaml`を使用している。テストレベル分類を追加：

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
    enabled: false  # 高速リグレッション用に無効化（遅すぎる）
    timeout: 10ms
    expected_result: pass
```

#### 5.1.2 テストランナースクリプト拡張

```python
# scripts/run_test.py（拡張）

def run_regression(test_level='all'):
    """指定レベルのすべてのテストを実行"""
    config = load_test_config("tests/test_config.yaml")

    results = []
    for test in config['tests']:
        if test['enabled']:
            if test_level == 'all' or test['level'] == test_level:
                result = run_single_test(test)
                results.append(result)

    generate_report(results)

def generate_report(results):
    """HTMLテストレポートを生成"""
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')

    with open('sim/results/test_report.html', 'w') as f:
        f.write(f"<h1>Test Report</h1>")
        f.write(f"<p>Passed: {passed}/{len(results)}</p>")
        f.write(f"<p>Failed: {failed}/{len(results)}</p>")
        # ... (結果の詳細テーブル)
```

### 5.2 カバレッジ収集

**ツール**: Verilatorは`--coverage`フラグでコードカバレッジをサポート。

#### 5.2.1 test_config.yamlでカバレッジを有効化

```yaml
verilator:
  extra_flags:
    - --coverage  # line/toggleカバレッジを有効化
    - --coverage-line
    - --coverage-toggle
```

#### 5.2.2 カバレッジレポート生成

```bash
# テスト実行後
verilator_coverage --annotate sim/coverage_report/ sim/obj_dir/coverage.dat
```

#### 5.2.3 カバレッジ目標

| 指標             | 目標   | 説明                                     |
|------------------|--------|------------------------------------------|
| Line Coverage    | 100%   | すべての行が実行される                   |
| Branch Coverage  | 95%+   | すべてのif/else分岐が取られる            |
| Toggle Coverage  | 90%+   | すべての信号が0→1および1→0にトグルする   |
| FSM Coverage     | 100%   | すべての状態と遷移が訪問される           |

---

## 6. シミュレーション性能最適化

### 6.1 課題

- **長期間BERテスト**: 10億ビット @ 10 Gbps = 100 ms実時間 → シミュレーションで数時間
- **Eye diagramキャプチャ**: 高サンプルレートで1000s UI = 大規模VCDファイル
- **システムテスト**: 等化を含むフルTx-Channel-Rx = 複雑で低速

### 6.2 最適化戦略

#### 6.2.1 Verilator最適化フラグ

```yaml
verilator:
  optimization_flags:
    - --x-assign fast       # 高速X伝播
    - --x-initial fast
    - -O3                   # 最大C++最適化
    - --inline-mult 1000    # 積極的インライン化
```

#### 6.2.2 選択的VCDダンプ

```systemverilog
// デバッグ用に関心のある信号のみをダンプ
initial begin
    $dumpfile("sim/waves/test.vcd");
    $dumpvars(1, dut.ffe);  // FFEモジュールのみ（深さ1）
    // NOT: $dumpvars(0, dut);  // すべてをダンプ（低速）
end
```

#### 6.2.3 並列テスト実行

GNU Parallelなどを使用して独立したテストを並列実行：

```bash
# すべてのユニットテストを並列実行（一度に4ジョブ）
parallel -j 4 'python3 scripts/run_test.py --test {}' ::: ffe_impulse ffe_pre_emphasis dfe_bypass ctle_dc_response
```

#### 6.2.4 高速機能モデル

長期間テストには簡略化チャネルモデルを使用：

```systemverilog
// 高速チャネルモデル: 少数タップのFIRフィルタ（現実的ではないが高速）
module channel_fast (
    input  real signal_in,
    output real signal_out
);
    // 3タップFIR（精度のための100タップの代わり）
    assign signal_out = 0.8*signal_in + 0.15*prev1 + 0.05*prev2;
endmodule
```

### 6.3 シミュレーション時間予算

| テストレベル | テスト数 | 平均期間 | 総時間   | 頻度         |
|--------------|----------|----------|----------|--------------|
| Unit         | 30       | 30 µs    | 約1分    | 毎コミット   |
| Integration  | 20       | 500 µs   | 約30分   | 毎日         |
| System       | 15       | 10 ms    | 約8時間  | 毎週         |
| Compliance   | 10       | 50 ms    | 約2日    | リリースのみ |

---

## 7. PCIe準拠テスト詳細

### 7.1 PCIe Gen3/4/5要件サマリー

| パラメータ               | Gen3 (8 Gbps)    | Gen4 (16 Gbps)   | Gen5 (32 Gbps PAM4) |
|--------------------------|------------------|------------------|---------------------|
| **変調方式**             | NRZ              | NRZ              | PAM4                |
| **Tx Eye Height**        | > 100 mV         | > 100 mV         | > 15 mV (eye毎)     |
| **Tx Eye Width**         | > 0.4 UI         | > 0.3 UI         | > 0.25 UI           |
| **Tx Jitter (RJ)**       | < 2 ps RMS       | < 1.5 ps RMS     | < 1.0 ps RMS        |
| **Tx De-emphasis**       | -6 dB / -3.5 dB  | -6 dB / -3.5 dB  | N/A (PAM4)          |
| **Rx Jitter許容度**      | 0.55 UI          | 0.4 UI           | 0.3 UI              |
| **BER目標**              | < 1e-12          | < 1e-12          | < 1e-12             |

### 7.2 準拠テストチェックリスト

#### 7.2.1 送信機テスト

- [ ] **TX.1**: 差動出力電圧（800-1200 mV pp）
- [ ] **TX.2**: Eyeマスク準拠（違反なし）
- [ ] **TX.3**: 立ち上がり/立ち下がり時間（< 60 ps 20%-80%）
- [ ] **TX.4**: De-emphasisレベル（-6 dB ±1 dB、-3.5 dB ±1 dB）
- [ ] **TX.5**: Tx等化係数範囲
- [ ] **TX.6**: 送信jitter（RJ < 2 ps、TJ < 0.25 UI）
- [ ] **TX.7**: スペクトラム拡散クロッキング（SSC）準拠

#### 7.2.2 受信機テスト

- [ ] **RX.1**: 最小入力感度（-100 mV差動）
- [ ] **RX.2**: Jitter許容度（BER 1e-12で0.55 UI RJに耐える）
- [ ] **RX.3**: 周波数オフセット許容度（±300 ppm）
- [ ] **RX.4**: Rx等化範囲（CTLE、FFE、DFEが仕様内）
- [ ] **RX.5**: CDRロック時間（< 1000 UI）

---

## 8. 合格/不合格基準サマリー

### 8.1 ユニットテスト基準

| モジュール   | 合格基準                                                    |
|--------------|-------------------------------------------------------------|
| FFE          | すべてのテストパターンで出力が期待値±1 LSBと一致           |
| DFE          | スライサーレベルが正しい±2 LSB、フィードバックが±1 LSB以内 |
| CTLE         | 周波数応答が理論値の±1 dB以内                              |
| Serializer   | シリアルストリームにビットエラーなし（パラレルと比較）      |
| Deserializer | パラレル出力にビットエラーなし（シリアルと比較）            |

### 8.2 統合テスト基準

| テスト         | 合格基準                                              |
|----------------|-------------------------------------------------------|
| Tx-only        | 信号スイングが目標の10%以内、飽和なし                |
| Rx-only        | 20 dBチャネルで90%以上のビットを正しく回復            |
| Tx-Rx loopback | 10Mビットに対してBER < 1e-9（クイックチェック）       |

### 8.3 システムテスト基準

| テスト          | 合格基準                                           |
|-----------------|----------------------------------------------------|
| BER測定         | 100M以上のビットに対してBER < 1e-12                |
| Eye diagram     | Eye height > 100 mV、Eye width > 0.4 UI            |
| Jitter許容度    | 0.55 UI RJ注入でBER < 1e-12                        |

### 8.4 準拠テスト基準

**全体**: ターゲット世代（Gen3/4/5）のすべてのPCIe仕様要件に合格。

---

## 9. 推奨テスト実行順序

### 9.1 開発フェーズ（機能立ち上げ）

**ステージ1**: 基本機能
1. FFEのユニットテスト（フィルタが機能することを確認）
2. DFEのユニットテスト（スライサー+フィードバックが機能することを確認）
3. CTLEのユニットテスト（周波数応答が正しいことを確認）

**ステージ2**: 統合
4. Tx-onlyテスト（Txチェーンがクリーンな信号を生成することを検証）
5. Rx-onlyテスト（Rxチェーンが既知入力を回復することを検証）
6. Loopbackテスト（フルリンクがエンドツーエンドで機能することを検証）

**ステージ3**: 性能
7. BER測定（< 1e-12目標を検証）
8. Eye diagram（eye openingが十分であることを検証）

### 9.2 リグレッションテスト（継続的）

**毎日リグレッション**（高速テストのみ）:
- すべてのユニットテスト（約1分）
- 短期間の統合テスト（約10分）

**毎週リグレッション**（低速テストを含む）:
- システムテストを含む完全なテストスイート（約8時間）

**リリースリグレッション**（包括的）:
- 完全なテストスイート + 準拠テスト（約3日）

---

## 10. 参考文献

### 10.1 標準

- **PCI Express Base Specification** Rev 3.0/4.0/5.0/6.0
- **IEEE 802.3**: Ethernet準拠テスト方法論

### 10.2 ツール

- **Verilator**: オープンソースSystemVerilogシミュレータ
- **GTKWave**: 波形ビューア
- **Python**: テスト自動化と後処理

### 10.3 関連ドキュメント

- `spec/ffe_specification.md` - FFEユニットテスト詳細
- `spec/dfe_specification.md` - DFEユニットテスト詳細
- `spec/ctle_specification.md` - CTLEユニットテスト詳細
- `spec/serdes_architecture.md` - システム統合詳細
- `README.md` - プロジェクトセットアップと実行手順

---

## 11. 改訂履歴

| バージョン | 日付       | 作成者 | 説明                                   |
|-----------|------------|--------|----------------------------------------|
| 1.0       | 2025-01-11 | Claude | 初版テスト戦略と検証計画               |

---

**SerDesテスト戦略仕様書 終わり**
