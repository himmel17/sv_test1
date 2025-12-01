# FFE (Feed-Forward Equalizer) 仕様書

**ドキュメントバージョン**: 1.0
**最終更新日**: 2025-01-11
**対象**: 高速SerDes (10-25 Gbps) PCIe Gen3/4/5向け
**変調方式**: NRZ, PAM4

---

## 1. 概要

### 1.1 目的

Feed-Forward Equalizer (FFE) は、高速シリアルリンクにおけるチャネル起因のInter-Symbol Interference (ISI, シンボル間干渉) を補償するデジタルFIR (Finite Impulse Response) フィルタです。送信パス (Tx FFE、プリエンファシス用) または受信パス (Rx FFE、ポスト補償用) で動作します。

### 1.2 主な機能

- **7タップFIRフィルタ** (パラメータによりタップ数変更可能)
- **プログラマブル係数** による適応等化
- **8ビットデータパス** (Rxにおける ADC出力幅に対応)
- **符号付き演算** による負のタップ重み対応
- **同期動作** (シングルクロックドメイン)
- **PCIe準拠** のタップ重み範囲と制約

### 1.3 ブロック図

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

## 2. インターフェース仕様

### 2.1 ポート定義

| ポート名        | 方向   | ビット幅       | 型             | 説明                                             |
|-----------------|--------|----------------|----------------|--------------------------------------------------|
| `clk`           | Input  | 1              | `logic`        | システムクロック (パラレルデータレートクロック)  |
| `rst_n`         | Input  | 1              | `logic`        | Active-low同期リセット                           |
| `data_in`       | Input  | `DATA_WIDTH`   | `logic signed` | 入力データサンプル (デフォルト8ビット、ADC出力)  |
| `data_out`      | Output | `DATA_WIDTH`   | `logic signed` | 等化済み出力データ                               |
| `coeff_wr_en`   | Input  | 1              | `logic`        | 係数書き込みイネーブル (タップ重み更新)          |
| `coeff_addr`    | Input  | `ADDR_WIDTH`   | `logic`        | 係数アドレス (タップインデックス 0-6)            |
| `coeff_data`    | Input  | `COEFF_WIDTH`  | `logic signed` | 書き込む係数値 (符号付きタップ重み)              |
| `coeff_updated` | Output | 1              | `logic`        | 係数更新完了を示すパルス                         |

**注記:**
- 全信号は`clk`に同期
- `data_in`, `data_out`, `coeff_data`は**符号付き**演算を使用
- リセット時は全タップ重みを所定値に初期化 (cursorタップ = 最大値、その他 = 0)

### 2.2 パラメータ定義

| パラメータ     | デフォルト | 範囲       | 説明                                               |
|----------------|------------|------------|----------------------------------------------------|
| `TAP_COUNT`    | 7          | 3-15       | FIRフィルタのタップ数 (奇数が望ましい)            |
| `DATA_WIDTH`   | 8          | 6-12       | データパス幅 (サンプルあたりのビット数)            |
| `COEFF_WIDTH`  | 10         | 8-16       | 係数ビット幅 (精度を決定)                          |
| `ADDR_WIDTH`   | 3          | 2-4        | 係数アドレスビット幅 (log2(TAP_COUNT))             |
| `CURSOR_TAP`   | 3          | 0-6        | メインタップインデックス (通常は中央タップ)        |
| `ACCUM_WIDTH`  | 20         | 16-32      | 内部アキュムレータビット幅 (オーバーフロー防止)    |

**パラメータ選択ガイドライン:**
- `COEFF_WIDTH = DATA_WIDTH + 2` (十分な精度のための最小値)
- `ACCUM_WIDTH ≥ DATA_WIDTH + COEFF_WIDTH + log2(TAP_COUNT)` (オーバーフロー回避)
- PAM4の場合: `DATA_WIDTH ≥ 8` (4シンボルには良好な分解能が必要)
- NRZの場合: `DATA_WIDTH ≥ 6` (2シンボル、よりシンプル)

---

## 3. 機能説明

### 3.1 FIRフィルタアルゴリズム

FFEは離散時間FIRフィルタを実装します：

```
y[n] = Σ(i=0 to N-1) c[i] × x[n-i]
```

ここで：
- `y[n]`: 時刻nにおける出力サンプル
- `x[n]`: 時刻nにおける入力サンプル
- `c[i]`: タップiの係数
- `N`: タップ数 (TAP_COUNT = 7)

### 3.2 タップ遅延ライン

入力信号はシフトレジスタを通じて遅延され、複数の時間整列されたタップポイントを生成します：

```
Tap0 = x[n]     (現在のサンプル)
Tap1 = x[n-1]   (1サンプル遅延)
Tap2 = x[n-2]   (2サンプル遅延)
...
Tap6 = x[n-6]   (6サンプル遅延)
```

**実装**: `logic signed [DATA_WIDTH-1:0] tap_delay [0:TAP_COUNT-1]` シフトレジスタを使用。

### 3.3 Multiply-Accumulate (MAC) 演算

各タップ出力に係数を乗じて合算します：

```systemverilog
// MAC演算の疑似コード
accumulator = 0;
for (i = 0; i < TAP_COUNT; i++) {
    product[i] = tap_delay[i] * coefficient[i];  // 符号付き乗算
    accumulator += product[i];                   // 符号付き加算
}
data_out = accumulator >>> (COEFF_WIDTH - 1);    // スケーリングのための算術右シフト
```

**重要ポイント:**
- すべての演算に**符号付き演算**を使用
- アキュムレータはオーバーフローを防ぐために十分な幅が必要 (`ACCUM_WIDTH`)
- 最終出力は`DATA_WIDTH`に合わせて右シフトでスケーリング

### 3.4 係数更新インターフェース

係数は制御インターフェースを介して動的に更新可能：

**書き込み動作シーケンス:**
1. `coeff_wr_en = 1`をアサート
2. `coeff_addr`をターゲットタップインデックス (0 ～ TAP_COUNT-1) に設定
3. `coeff_data`を希望のタップ重み (符号付き値) に設定
4. 次の`posedge clk`で係数がラッチされる
5. `coeff_updated`が1サイクル間Highにパルス

**読み出し動作**: (オプション機能、v1.0では必須でない)
- 将来の拡張: 係数読み戻し用に`coeff_rd_en`と`coeff_q`を追加

---

## 4. タイミング要件

### 4.1 クロックとリセット

- **クロック周波数**: パラレルデータレート (例: 32ビットパラレルで10 Gbpsの場合312.5 MHz)
- **リセットタイミング**: 同期Active-lowリセット
  - `rst_n = 0`を≥ 2クロックサイクルアサート
  - 全タップ遅延を0にクリア
  - 係数をデフォルトにリセット (cursor = 最大値、pre/post = 0)

### 4.2 レイテンシ

- **パイプラインレイテンシ**: 2クロックサイクル (タップ遅延レジスタ + MAC + 出力レジスタ)
- **係数更新レイテンシ**: `coeff_wr_en`アサートから1クロックサイクル

### 4.3 タイミング図

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

## 5. 係数管理

### 5.1 係数表現

係数は**符号付き固定小数点**形式を使用：

```
Sign bit: Bit [COEFF_WIDTH-1]
Integer: Bits [COEFF_WIDTH-2:FRAC_BITS]
Fraction: Bits [FRAC_BITS-1:0]
```

**COEFF_WIDTH = 10の例:**
- フォーマット: S.IIIIIIII.F (符号1ビット + 整数8ビット + 小数1ビット)
- 範囲: -256 ～ +255.5
- 分解能: 0.5 LSB

### 5.2 デフォルト係数値 (リセット状態)

7タップFFE、cursorがタップ3の場合：

| タップインデックス | タップ名        | デフォルト値 (10ビット) | 16進数  | 説明                      |
|--------------------|-----------------|-------------------------|---------|---------------------------|
| 0                  | Pre-cursor 3    | 0                       | 0x000   | cursor の3サンプル前      |
| 1                  | Pre-cursor 2    | 0                       | 0x000   | cursor の2サンプル前      |
| 2                  | Pre-cursor 1    | 0                       | 0x000   | cursor の1サンプル前      |
| 3                  | **Cursor**      | **+511**                | 0x1FF   | **メインタップ (最大値)** |
| 4                  | Post-cursor 1   | 0                       | 0x000   | cursor の1サンプル後      |
| 5                  | Post-cursor 2   | 0                       | 0x000   | cursor の2サンプル後      |
| 6                  | Post-cursor 3   | 0                       | 0x000   | cursor の3サンプル後      |

**根拠**: デフォルトの「パススルー」構成 (等化なし)。

### 5.3 PCIe準拠の係数範囲

PCIe Gen3/4/5送信機FFE用：

| 係数タイプ       | 最小値         | 最大値        | 注記                                |
|------------------|----------------|---------------|-------------------------------------|
| Cursor (C0)      | +0.5 (50%)     | +1.0 (100%)   | 常に正、最大の重み                  |
| Pre-cursor (C-1) | -0.15 (-15%)   | +0.15 (+15%)  | Pre-ISI用のディエンファシス         |
| Post-cursor (C+1)| -0.25 (-25%)   | +0.05 (+5%)   | Post-ISI用のディエンファシス        |

**正規化制約**: Σ|C[i]| ≤ 1.0 (全エネルギー保存)

---

## 6. テスト計画

### 6.1 単体テスト: インパルス応答

**目的**: タップ遅延ラインと基本FIR動作を検証。

**手順**:
1. cursorを除く全係数を0に設定 (C[3] = 511)
2. インパルスを印加: `data_in = 127`を1サイクル、その後`data_in = 0`
3. **期待結果**: `data_out`がcursorタップ位置に単一パルスを表示 (2サイクルレイテンシ)

**合格基準**: 出力インパルス振幅 = (127 × 511) >> 9 ≈ 127 (DATA_WIDTHにスケールバック)

### 6.2 単体テスト: プリエンファシス

**目的**: 負係数動作を検証。

**手順**:
1. 係数を設定:
   - C[2] = -128 (pre-cursor 1)
   - C[3] = +511 (cursor)
   - C[4] = -128 (post-cursor 1)
2. ステップ入力を印加: `data_in = 0` → `data_in = 100` (ステップ遷移)
3. **期待結果**: 出力が遷移前後でオーバーシュートを表示 (プリエンファシス効果)

**合格基準**:
- 最初の遷移: 出力 > 100 (オーバーシュート)
- 定常値: 出力 ≈ 100 (pre/post-cursorが遅延ラインを抜けた後)

### 6.3 単体テスト: 係数更新

**目的**: 動的係数プログラミングを検証。

**手順**:
1. FFEをデフォルト係数で初期化
2. `coeff_wr_en = 1`, `coeff_addr = 1`, `coeff_data = 256`をアサート (pre-cursor 2を更新)
3. 1サイクル待機、`coeff_updated`パルスを確認
4. テストパターンを印加し、更新された応答を検証

**合格基準**:
- `coeff_updated`がちょうど1サイクルHighにパルス
- 後続の出力が新しい係数値を反映

### 6.4 統合テスト: NRZ等化

**目的**: NRZデータストリーム等化を検証。

**手順**:
1. FFEを典型的なNRZ係数で構成 (cursor = 0.8, post-cursor = -0.2)
2. PRBS7 NRZパターンを印加: +127/-128レベルの交互
3. 出力でISI低減を監視

**合格基準**:
- 出力アイダイアグラムが垂直アイ開口の改善を示す
- 出力サンプルに飽和またはオーバーフローなし

### 6.5 統合テスト: PAM4等化

**目的**: PAM4マルチレベル等化を検証。

**手順**:
1. FFEをPAM4最適化係数で構成
2. PAM4パターンを印加: 4レベル (-96, -32, +32, +96)
3. 出力レベル分離を監視

**合格基準**:
- 全4 PAM4レベルが出力で正しく保持される
- レベル間隔が維持される (圧縮なし)

### 6.6 ストレステスト: 最大係数値

**目的**: アキュムレータオーバーフロー保護を検証。

**手順**:
1. 全係数を最大正値に設定 (+511、10ビットの場合)
2. 最大入力を印加: `data_in = +127`
3. `data_out`を飽和またはオーバーフローについて確認

**合格基準**:
- 算術オーバーフローなし (出力は最大+127に飽和)
- シミュレーションでX (不定) 状態なし

---

## 7. SystemVerilog実装ノート

### 7.1 モジュール宣言テンプレート

```systemverilog
`timescale 1ns / 1ps

// Feed-Forward Equalizer (FFE) - 7タップFIRフィルタ
// Verilatorシミュレーション検証用のDesign Under Test (DUT)

module ffe #(
    parameter int TAP_COUNT    = 7,
    parameter int DATA_WIDTH   = 8,
    parameter int COEFF_WIDTH  = 10,
    parameter int ADDR_WIDTH   = 3,
    parameter int CURSOR_TAP   = 3,
    parameter int ACCUM_WIDTH  = 20
)(
    input  logic                       clk,          // システムクロック
    input  logic                       rst_n,        // Active-lowリセット
    input  logic signed [DATA_WIDTH-1:0]   data_in,  // 入力サンプル
    output logic signed [DATA_WIDTH-1:0]   data_out, // 等化済み出力
    input  logic                       coeff_wr_en,  // 係数書き込みイネーブル
    input  logic [ADDR_WIDTH-1:0]      coeff_addr,   // 係数アドレス
    input  logic signed [COEFF_WIDTH-1:0] coeff_data,// 係数データ
    output logic                       coeff_updated // 係数更新パルス
);

    // 内部信号
    logic signed [DATA_WIDTH-1:0]  tap_delay [0:TAP_COUNT-1];
    logic signed [COEFF_WIDTH-1:0] coeff [0:TAP_COUNT-1];
    logic signed [ACCUM_WIDTH-1:0] accumulator;

    // ... 実装 ...

endmodule
```

### 7.2 主要実装ガイドライン

#### 7.2.1 タップ遅延ライン (シフトレジスタ)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 0; i < TAP_COUNT; i++) begin
            tap_delay[i] <= '0;
        end
    end else begin
        tap_delay[0] <= data_in;  // 新しいサンプル
        for (int i = 1; i < TAP_COUNT; i++) begin
            tap_delay[i] <= tap_delay[i-1];  // シフト
        end
    end
end
```

#### 7.2.2 係数ストレージと更新

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        // デフォルトに初期化 (cursor = 最大値、その他 = 0)
        for (int i = 0; i < TAP_COUNT; i++) begin
            if (i == CURSOR_TAP) begin
                coeff[i] <= (2**(COEFF_WIDTH-1)) - 1;  // 最大正値
            end else begin
                coeff[i] <= '0;
            end
        end
        coeff_updated <= 1'b0;
    end else begin
        coeff_updated <= 1'b0;  // デフォルト: 1サイクルパルス
        if (coeff_wr_en && coeff_addr < TAP_COUNT) begin
            coeff[coeff_addr] <= coeff_data;
            coeff_updated <= 1'b1;
        end
    end
end
```

#### 7.2.3 MAC演算 (組み合わせ回路)

```systemverilog
always_comb begin
    accumulator = '0;
    for (int i = 0; i < TAP_COUNT; i++) begin
        accumulator += tap_delay[i] * coeff[i];
    end
end
```

#### 7.2.4 出力スケーリングと飽和

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        data_out <= '0;
    end else begin
        // DATA_WIDTHにスケールバックするための算術右シフト
        logic signed [ACCUM_WIDTH-1:0] scaled;
        scaled = accumulator >>> (COEFF_WIDTH - 1);

        // 飽和ロジック
        if (scaled > $signed((2**(DATA_WIDTH-1))-1)) begin
            data_out <= (2**(DATA_WIDTH-1)) - 1;  // 正の飽和
        end else if (scaled < $signed(-(2**(DATA_WIDTH-1)))) begin
            data_out <= -(2**(DATA_WIDTH-1));      // 負の飽和
        end else begin
            data_out <= scaled[DATA_WIDTH-1:0];
        end
    end
end
```

### 7.3 合成考慮事項

- **タイミングクロージャ**: MAC演算がクリティカルパス (TAP_COUNT個の乗算 + 加算)
  - 高速動作のためMACのパイプライン化を検討 (1サイクルレイテンシ追加)
- **リソース使用量**:
  - DSPブロック: TAP_COUNT × 乗算器 (Xilinxの場合7個のDSP48)
  - レジスタ: TAP_COUNT × DATA_WIDTH (タップ遅延) + TAP_COUNT × COEFF_WIDTH (係数)
- **除算なし**: すべての演算はシフトとマスクを使用 (高コストな除算を回避)

### 7.4 検証フック

テストベンチの可視性のため、合成時に無効化される信号を追加：

```systemverilog
`ifdef SIMULATION
    // 波形デバッグのための内部状態可視性
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

## 8. テストベンチ要件

### 8.1 テストベンチモジュールテンプレート

```systemverilog
`timescale 1ns / 1ps

module ffe_tb #(
    parameter SIM_TIMEOUT = 100000  // デフォルト100 µs
);

    // クロック生成 (例: 10 Gbps / 32ビットで312.5 MHz)
    logic clk = 0;
    always #1.6 clk = ~clk;  // 312.5 MHz (3.2 ns周期)

    // DUT信号
    logic       rst_n;
    logic signed [7:0]  data_in;
    logic signed [7:0]  data_out;
    logic       coeff_wr_en;
    logic [2:0] coeff_addr;
    logic signed [9:0]  coeff_data;
    logic       coeff_updated;

    // DUTインスタンス化
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

    // VCDダンプ
    initial begin
        $dumpfile("sim/waves/ffe.vcd");
        $dumpvars(0, ffe_tb);
    end

    // テストシーケンス
    int error_count = 0;
    initial begin
        // テスト実装をここに記述
        // (テスト手順については セクション6を参照)

        if (error_count == 0) begin
            $display("*** PASSED: All FFE tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end
        $finish;
    end

    // タイムアウトウォッチドッグ
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $finish;
    end

endmodule
```

### 8.2 テスト構成 (test_config.yaml)

```yaml
- name: ffe
  enabled: true
  description: "FFE 7タップFIRフィルタ等化テスト"
  top_module: ffe_tb
  testbench_file: ffe_tb.sv
  rtl_files:
    - ffe.sv
  verilator_extra_flags:
    - --trace-underscore  # 内部信号デバッグ用
  sim_timeout: "100us"
```

---

## 9. 参考文献

### 9.1 標準規格
- **PCIe Base Specification** (v3.0/4.0/5.0): 送信機等化要件
- **IEEE 802.3**: Ethernet等化仕様

### 9.2 アプリケーションノート
- Xilinx UG479: 7 Series DSP48E1 Slice User Guide (FPGA実装用)
- "Understanding Equalization" - Tektronix Application Note

### 9.3 関連ドキュメント
- `spec/dfe_specification.md` - Decision Feedback Equalizer
- `spec/ctle_specification.md` - Continuous-Time Linear Equalizer
- `spec/serdes_architecture.md` - システムレベルSerDesアーキテクチャ

---

## 10. 改訂履歴

| バージョン | 日付       | 作成者 | 説明                     |
|------------|------------|--------|--------------------------|
| 1.0        | 2025-01-11 | Claude | 初版仕様書作成           |

---

## 付録A: 係数計算例

### 例1: シンプルなプリエンファシス (NRZ)

**目的**: Post-cursor ISIを-20%削減

**計算**:
- Cursor (C3) = 1.0 → 511 (10ビット最大値)
- Post-cursor 1 (C4) = -0.2 → -102 (10ビット)
- その他全て = 0

**検証**:
- ステップ入力を印加: 0 → 127
- 期待される出力: 初期オーバーシュート = 127 × (1.0 - 0.2) = ~102、その後127に落ち着く

### 例2: 対称等化 (PAM4)

**目的**: 等しいpreとpost補償

**計算**:
- Pre-cursor 1 (C2) = -0.1 → -51
- Cursor (C3) = 1.0 → 511
- Post-cursor 1 (C4) = -0.1 → -51
- その他全て = 0

**検証**:
- PAM4シーケンスを印加: [-96, -32, +32, +96]
- 出力でレベル分離が維持されることを確認

---

**FFE仕様書 終わり**
