# DPI-C チュートリアルとリファレンス

**DPI-C (Direct Programming Interface for C)** - SystemVerilogとC言語の統合のための包括的な教育ガイド

## 目次

1. [DPI-Cとは？](#dpi-cとは)
2. [DPI-Cを使用するタイミング](#dpi-cを使用するタイミング)
3. [基本概念](#基本概念)
4. [データ型のマッピング](#データ型のマッピング)
5. [ImportとExport](#importとexport)
6. [正弦波サンプルの詳細解説](#正弦波サンプルの詳細解説)
7. [Verilator固有の考慮事項](#verilator固有の考慮事項)
8. [よくある落とし穴と解決策](#よくある落とし穴と解決策)
9. [高度なトピック](#高度なトピック)
10. [FAQ](#faq)

---

## DPI-Cとは？

**DPI-C** (Direct Programming Interface for C) はIEEE 1800 SystemVerilog標準規格で、以下を可能にします：

- **SystemVerilogからC関数を呼び出す** - 既存のCライブラリ、アルゴリズム、コードにアクセス
- **CからSystemVerilogを呼び出す** - ハードウェアと対話するカスタムCモデルの作成
- **混合言語シミュレーション** - ハードウェア記述とソフトウェアモデルの組み合わせ

### 主な利点

✅ **既存のCコードの活用** - 数学ライブラリ、ファイルI/O、複雑なアルゴリズムを書き直す必要なし
✅ **パフォーマンス** - C実装は同等のSystemVerilogより高速な場合がある
✅ **シンプルさ** - 一部の操作はCの方が自然（文字列、ポインタ、malloc）
✅ **統合** - ハードウェアシミュレーションとソフトウェアモデルの接続
✅ **テストベンチの強化** - 高度な検証にCライブラリを使用（JSON、正規表現、ネットワーク）

### DPI-Cでできないこと

❌ **合成不可** - DPI-Cはシミュレーション専用で、ハードウェアに変換できない
❌ **RTLの代替ではない** - モデリングと検証に使用し、実装には使用しない
❌ **すべてのシミュレータで移植可能ではない** - 一部の機能はツール間で異なる

---

## DPI-Cを使用するタイミング

### 適切な使用例

| 用途 | 例 | DPI-Cを使う理由 |
|------|-----|----------------|
| **数学関数** | sin, cos, sqrt, log | Cのmath.hは最適化され正確 |
| **ファイルI/O** | 刺激の読み込み、結果の書き込み | Cのファイル操作は強力 |
| **リファレンスモデル** | Cのゴールデンアルゴリズム | 信頼できるCとRTLを比較 |
| **複雑なデータ構造** | リンクリスト、ハッシュテーブル | Cのポインタとmallocが自然 |
| **外部ライブラリ** | 画像処理、暗号化 | 既存の検証済みコードを再利用 |
| **パフォーマンス** | 重い計算 | CはSVのループより高速 |

### 不適切な使用例

| 用途 | 理由 | 代替案 |
|------|------|--------|
| 単純なロジック | オーバーヘッドに見合わない | 純粋なSystemVerilog |
| 合成可能なコード | DPI-Cは合成できない | RTLを直接記述 |
| 移植可能なテストベンチ | ツール固有の動作 | SystemVerilogのみ |
| デバッグ | バグの追跡が困難 | SVの方がデバッグしやすい |

**経験則：** SystemVerilogで簡単にできることは、SystemVerilogで行う。Cが明確な利点を提供する場合にDPI-Cを使用する。

---

## 基本概念

### Import文

**SystemVerilog側：** インポートするC関数を宣言

```systemverilog
// 基本的なインポート
import "DPI-C" function real dpi_sin(input real x);

// Pure関数（副作用なし - 最適化を有効化）
import "DPI-C" pure function real dpi_sin(input real x);

// 複数の引数を持つ関数
import "DPI-C" function int add(input int a, input int b);

// コンテキストインポート（高度 - シミュレーションコンテキストを提供）
import "DPI-C" context function void debug_print(input string msg);
```

**C側：** 関数を実装

```c
#include <math.h>

// 名前マングリングを防ぐために常にextern "C"を使用
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

### Export文

**SystemVerilog側：** Cから呼び出すための関数をエクスポート

```systemverilog
export "DPI-C" function my_sv_function;

function int my_sv_function(int x);
    return x * 2;
endfunction
```

**C側：** SystemVerilog関数を呼び出す

```c
extern int my_sv_function(int x);

int some_c_code() {
    int result = my_sv_function(42);  // SystemVerilogを呼び出す
    return result;
}
```

---

## データ型のマッピング

### 基本型（正確なマッピング）

| SystemVerilog | C型 | サイズ | 備考 |
|---------------|-----|--------|------|
| `byte` | `char` | 8ビット | 符号付き |
| `shortint` | `short` | 16ビット | 符号付き |
| `int` | `int` | 32ビット | 符号付き |
| `longint` | `long long` | 64ビット | 符号付き |
| `real` | `double` | 64ビット | IEEE 754 |
| `shortreal` | `float` | 32ビット | IEEE 754 |
| `string` | `const char*` | - | NULL終端 |
| `chandle` | `void*` | - | 不透明ポインタ |

### パック配列（ビットベクトル）

```systemverilog
// SystemVerilog
import "DPI-C" function void process_bits(input bit [31:0] data);

// C実装
#include <svdpi.h>
void process_bits(svBitVecVal data) {
    // dataは32ビット値
}
```

### 重要なルール

1. **常に`input`方向を使用** - DPI-Cインポートには最も信頼性が高い
2. **`output`と`inout`は避ける** - 代わりに戻り値を使用
3. **文字列は不変** - Cは`const char*`を受け取り、変更不可
4. **配列は扱いが難しい** - オープン配列またはパック型を使用
5. **実数：** 精度のために`real` ↔ `double`を使用

---

## ImportとExport

### Import（SystemVerilogがCを呼び出す）

**最も一般的な使用法** - SystemVerilogテストベンチまたはモデルからCライブラリを呼び出す。

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

### Export（CがSystemVerilogを呼び出す）

**高度な使用法** - CコードがSystemVerilogにコールバックできるようにする。

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
    callback(42);  // SystemVerilogを呼び出す
}
```

### それぞれを使用するタイミング

| パターン | Importを使用 | Exportを使用 |
|---------|-------------|-------------|
| C数学ライブラリを呼び出す | ✅ | ❌ |
| テストベンチでファイルを読む | ✅ | ❌ |
| CモデルがSVの状態を必要とする | ❌ | ✅ |
| 複雑なC-SV相互作用 | ✅ | ✅ 両方 |

**ヒント：** インポートのみから始める（よりシンプル）。CがSVを呼び出す必要がある場合のみエクスポートを追加。

---

## 正弦波サンプルの詳細解説

このプロジェクトには、正弦波生成を実演する完全なDPI-Cサンプルが含まれています。

### ファイル概要

```
dpi/
  dpi_math.c          ← sin/cosラッパーのC実装
rtl/
  sine_wave_gen.sv    ← DPI-Cを使用するRTLモジュール
tb/
  sine_wave_gen_tb.sv ← DPI-Cを使用するテストベンチ
```

### ステップバイステップの説明

#### ステップ1：C実装（`dpi/dpi_math.c`）

```c
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// C標準ライブラリのsin()の単純なラッパー
double dpi_sin(double x) {
    return sin(x);
}

#ifdef __cplusplus
}
#endif
```

**重要ポイント：**
- `math.h`の標準`sin()`をラップ
- 適切なリンケージのために`extern "C"`を使用
- `double`を返す（SVの`real`にマップ）

#### ステップ2：SystemVerilog RTL（`rtl/sine_wave_gen.sv`）

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
    // C関数をインポート
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
        sine_out = AMPLITUDE * dpi_sin(phase);  // C関数を呼び出す！
    end
endmodule
```

**重要ポイント：**
- `import`文で`dpi_sin`を宣言
- ネイティブSV関数のように呼び出す
- `pure`キーワードが最適化を有効化

#### ステップ3：テストベンチ（`tb/sine_wave_gen_tb.sv`）

```systemverilog
module sine_wave_gen_tb;
    // テストベンチもDPI-C関数をインポート可能！
    import "DPI-C" pure function real dpi_sin(input real x);

    // ... テストコード ...

    // 検証にDPI-Cを使用
    real expected = AMPLITUDE * dpi_sin(phase);
    if (sine_out != expected) begin
        $display("ERROR: Mismatch");
    end
endmodule
```

**重要ポイント：**
- テストベンチもDPI-Cを使用可能
- リファレンスモデルに有用
- RTLと同じインポート構文

#### ステップ4：コンパイルとリンク

`tests/test_config.yaml`内：

```yaml
- name: sine_wave_gen
  verilator_extra_flags:
    - ../dpi/dpi_math.c  # Cソースをインクルード
    - -LDFLAGS           # リンカフラグ
    - -lm                # 数学ライブラリをリンク
```

**生成されるVerilatorコマンド：**
```bash
verilator --binary --timing ... \
    ../dpi/dpi_math.c \
    -LDFLAGS -lm \
    rtl/sine_wave_gen.sv tb/sine_wave_gen_tb.sv
```

#### ステップ5：テストの実行

```bash
# シミュレーション実行
uv run python3 scripts/run_test.py --test sine_wave_gen

# 波形表示
uv run python3 scripts/run_test.py --test sine_wave_gen --view
```

期待される出力：
```
*** PASSED: All DPI-C sine wave tests passed successfully ***
  ✓ DPI-C function import works correctly
  ✓ Real number (double) data passing is accurate
  ✓ Math library integration is successful
  ✓ Waveform generation meets specifications
```

---

## フリッカノイズサンプル（高度）

このプロジェクトには、Pythonベースの検証を用いたアナログノイズモデリングのための**ステートフル**DPI-C実装を実演する高度なDPI-Cサンプルが含まれています。

### 目的

以下の方法を示すProof of Concept：
- DPI-Cでステートフルアルゴリズムを実装（呼び出し間で状態を維持）
- デジタルシミュレーションでアナログ効果（1/fフリッカノイズ）をモデル化
- Pythonリファレンスに対してC実装を検証
- VCD波形データを使用した統計的検証を実行

### ファイル概要

```
dpi/
  dpi_flicker_noise.c     ← ステートフルC実装（Voss-McCARTNEYアルゴリズム）
rtl/
  ideal_amp_with_noise.sv ← ノイズ注入付き理想アンプ
tb/
  ideal_amp_with_noise_tb.sv ← セルフチェックテストベンチ（DC入力）
scripts/
  generate_flicker_noise.py  ← Pythonリファレンス実装（ストリーミング版）
  generate_flicker_noise_batch.py ← Pythonリファレンス実装（バッチ版）
  verify_noise_match.py      ← 統計検証（ストリーミング版）
  verify_noise_match_batch.py ← 厳密一致検証（バッチ版）
```

### アルゴリズム：Voss-McCartney 1/fノイズ

Voss-McCARTNEYアルゴリズムは以下によってフリッカ（1/f）ノイズを生成します：
1. N個のノイズソースを維持（この実装ではN=10）
2. 各ソースを異なるレートで更新（ソースiは2^iサンプルごとに更新）
3. すべてのソースを合計して1/fパワースペクトル密度を生成

**特性：**
- 決定論的（再現性のための固定シード）
- ステートフル（ノイズソースとサンプルカウンタを維持）
- ターゲットRMS：経験的較正により0.25V

### 主要な実装：ステートフルDPI-C

**重要**：この関数は**pureではありません** - 呼び出し間で状態を維持します！

```c
// static状態はDPI-C呼び出し間で永続
static double noise_sources[10];
static unsigned long sample_counter = 0;
static int initialized = 0;

double dpi_flicker_noise(void) {
    if (!initialized) {
        srand(42);  // 固定シード
        for (int i = 0; i < 10; i++)
            noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
        initialized = 1;
    }

    // sample_counterに基づいてノイズソースを更新
    for (int i = 0; i < 10; i++) {
        if ((sample_counter & ((1UL << i) - 1)) == 0) {
            noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
        }
    }

    double sum = 0.0;
    for (int i = 0; i < 10; i++)
        sum += noise_sources[i];

    sample_counter++;

    return sum * (0.25 / 1.757);  // ターゲットRMSにスケール
}
```

**重要な注意事項：**

- **Cのstatic変数によるステートフル設計**（重要概念）:
  - すべての状態変数はC言語の`static`キーワードで宣言されている
  - **`static`変数は関数呼び出し間で値を保持する**
  - 通常のCローカル変数とは根本的に異なる動作
  - **実行シーケンス例**:
    ```
    時刻    イベント                            initialized の値
    ------------------------------------------------------------------
    0ns     プログラム起動                      0（一度だけ初期化）
    100ns   1回目のクロック: dpi_flicker_noise()呼び出し
            → if (!initialized) が真            0
            → init_flicker_noise()実行
            → initialized = 1                   0 → 1
            → ノイズ値を返す
    110ns   2回目のクロック: dpi_flicker_noise()呼び出し
            → if (!initialized) が偽            1（保持されている！）
            → 初期化をスキップ
            → ノイズ値を返す
    120ns   3回目のクロック: dpi_flicker_noise()呼び出し
            → if (!initialized) が偽            1（引き続き保持！）
            → 初期化をスキップ
            → ノイズ値を返す
    ```
  - **`static`なしの場合**: 変数は毎回の呼び出しで初期値にリセットされる
  - **`static`ありの場合**: 変数はプログラムメモリに一度だけ割り当てられる（スタックではない）
  - 3つのstatic変数すべてが永続化:
    - `static int initialized`: 最初の初期化後に1を保持
    - `static double noise_sources[10]`: 配列が呼び出し間で保存される
    - `static unsigned long sample_counter`: 0→1→2→3→...と連続的にインクリメント

- **スレッドセーフではない**：同期プリミティブなしでstatic変数を使用

- **pureではない**：SystemVerilogで`pure`として宣言しない（副作用あり - static状態を変更）

- **決定論的**：固定シードでシミュレーション実行間の再現性を確保

### SystemVerilog統合

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
    // 重要：「pure」として宣言しない（副作用あり！）
    import "DPI-C" function real dpi_flicker_noise();

    real noise_sample;

    assign amp_out_ideal = amp_in * GAIN;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            noise_sample <= 0.0;
            amp_out <= 0.0;
        end else begin
            noise_sample <= dpi_flicker_noise();  // 新しいノイズサンプル取得
            amp_out <= amp_out_ideal + (NOISE_AMPLITUDE * noise_sample);
        end
    end
endmodule
```

### 検証ワークフロー（ストリーミング版 - Method 1）

**ステップ1：Pythonリファレンス生成**
```bash
uv run python3 scripts/generate_flicker_noise.py
# 出力: scripts/flicker_noise_reference.npy（1024サンプル）
#       scripts/flicker_noise_spectrum.png（スペクトルプロット）
```

**ステップ2：SystemVerilogシミュレーション実行**
```bash
uv run python3 scripts/run_test.py --test ideal_amp_with_noise
# 出力: sim/waves/ideal_amp_with_noise.vcd
# テストベンチはDC入力を印加し、1044サンプル収集（リセットスキップ20 + 有効1024）
```

**ステップ3：統計的検証**
```bash
uv run python3 scripts/verify_noise_match.py
# VCDからノイズ抽出：amp_out - amp_out_ideal
# Pythonリファレンスと RMS およびスペクトル傾きを比較
# 出力: scripts/flicker_noise_verification.png
```

**期待される結果：**
```
======================================================================
FINAL VERDICT
======================================================================
✓✓✓ ALL TESTS PASSED ✓✓✓
Python and SystemVerilog implementations match statistically
Both exhibit 1/f noise characteristics as expected
======================================================================
RMS Error: 0.05% (0.249876V vs 0.250000V)
Spectral Slopes: Python=-1.155, SystemVerilog=-1.009 (期待値: -1.0 ± 0.2)
```

### 検証ワークフロー（バッチ版 - Method 2）

**厳密なサンプル単位の一致**が必要な場合は、バッチ版実装を使用します：

**ステップ1：Pythonリファレンスとバイナリ生成**
```bash
uv run python3 scripts/generate_flicker_noise_batch.py
# 出力: scripts/flicker_noise_batch_reference.npy（4096サンプル）
#       scripts/flicker_noise_batch_spectrum.png（スペクトルプロット）
#       dpi/flicker_noise_batch.bin（DPI-C用32 KBバイナリ）
```

**ステップ2：SystemVerilogシミュレーション実行（バッチ）**
```bash
uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch
# 出力: sim/waves/ideal_amp_with_noise_batch.vcd
# DPI-Cはバイナリファイルから事前生成されたサンプルをロード
```

**ステップ3：厳密一致検証**
```bash
uv run python3 scripts/verify_noise_match_batch.py
# 1ナノボルト許容誤差でのサンプル単位比較
# 出力: scripts/flicker_noise_batch_verification.png
#       scripts/flicker_noise_batch_verification.log（詳細ログ）
```

**期待される結果：**
```
======================================================================
FINAL VERDICT - BATCH MODE
======================================================================
✓✓✓ ALL TESTS PASSED ✓✓✓
Python and SystemVerilog implementations match EXACTLY
All samples within epsilon tolerance (1 nanovolt)
======================================================================
Sample Match: 100.00% (4096/4096)
Max Error: 1.332e-15 V（浮動小数点精度限界）
Mean Error: 2.997e-16 V
```

**バッチ版の特徴：**
- サンプル数：4096（ストリーミング版は1024）
- 検証：サンプル単位で厳密一致（ストリーミング版は統計的比較のみ）
- 許容誤差：1ナノボルト（ストリーミング版は10% RMS）
- DPI-C：バイナリファイルから事前ロード（ストリーミング版はリアルタイム生成）
- 出力：サンプル単位比較の詳細ログファイル

### 正弦波サンプルとの主な違い

| 側面 | 正弦波 | フリッカノイズ |
|------|--------|----------------|
| **状態** | ステートレス（pure） | ステートフル（pureではない） |
| **Import** | `pure function` | `function`（pureなし） |
| **C変数** | なし | static変数 |
| **副作用** | なし | 内部状態を更新 |
| **検証** | 厳密な比較 | 統計的比較 |
| **乱数生成** | なし | C `rand()`（Pythonと異なる） |
| **スレッド安全性** | 安全 | スレッドセーフではない |

### 異なる乱数生成器が問題にならない理由

C実装は`rand()`を使用し、Pythonは`random.uniform()`を使用します。これらは**異なるサンプル値**を生成しますが、**同一の統計特性**（RMS、スペクトル傾き）を持ちます。

**検証戦略：**
- ❌ サンプル単位での比較はしない（乱数生成器が異なる）
- ✅ RMSを比較（目標：< 10%誤差）
- ✅ スペクトル傾きを比較（目標：1/fノイズで-1.0 ± 0.2）
- ✅ パワースペクトル密度の視覚的検査

### リセット処理

**課題：** リセット後の最初の数サンプルに過渡データが含まれる

**解決策：**
- テストベンチは1044サンプル収集（TOTAL_SAMPLES = 1024 + 20）
- 最初の20サンプルは回路安定化のための「リセットスキップ」期間
- 検証スクリプトは最初の10 VCDサンプル（リセット期間）をスキップ
- 両実装からsample_counter 0-1023を比較

### 用途

このサンプルが実演する技術：
- **SerDesモデリング**：ジッタ、位相ノイズ、チャネルノイズ
- **RFシミュレーション**：発振器やアンプのフリッカノイズ
- **ミックスドシグナル**：デジタルシミュレーションでのアナログ動作モデル
- **アルゴリズム検証**：Pythonプロトタイプ → C実装ワークフロー
- **統計的検証**：VCDベースの後処理

### 教育的価値

学習内容：
- ✅ ステートフルDPI-C設計パターン
- ✅ `pure`キーワードを使用すべきでない場合
- ✅ Python-to-Cアルゴリズム移植ワークフロー
- ✅ 統計的検証技術
- ✅ VCD解析と後処理
- ✅ FFTベースのスペクトル解析
- ✅ 乱数生成器の違いと較正

---

## Verilator固有の考慮事項

Verilatorは優れたDPI-Cサポートを持っていますが、いくつか固有の特性があります。

### うまく機能すること

✅ **Pure関数** - 高度に最適化される
✅ **入力引数** - 完全サポート
✅ **戻り値** - 推奨される方法
✅ **実数** - `real` ↔ `double`は完璧に動作
✅ **標準ライブラリ** - math.h、stdio.hなど

### 制限事項

⚠️ **タスクはサポートされない** - 関数のみを使用
⚠️ **output/inoutは制限付き** - 戻り値を優先
⚠️ **時間遅延なし** - 関数はゼロタイム
⚠️ **コンテキスト関数** - 限定的なサポート

### 生成されるファイル

VerilatorはDPI-C統合のために以下のファイルを生成します：

```
sim/obj_dir/
  Vsine_wave_gen_tb__Dpi.h      ← DPI-C関数プロトタイプ
  Vsine_wave_gen_tb__Dpi.cpp    ← DPI-Cラッパーコード
  （その他のVerilatorファイル...）
```

これらを変更する必要はありません - Verilatorが自動生成します。

### コンパイルのヒント

1. **Cファイルを直接インクルード：**
   ```yaml
   verilator_extra_flags:
     - ../dpi/my_code.c
   ```

2. **-LDFLAGSでライブラリをリンク：**
   ```yaml
   verilator_extra_flags:
     - -LDFLAGS
     - -lm        # 数学ライブラリ
     - -lpthread  # スレッディング
   ```

3. **-CFLAGSでインクルードパスを追加：**
   ```yaml
   verilator_extra_flags:
     - -CFLAGS
     - -I/path/to/includes
   ```

---

## よくある落とし穴と解決策

### 落とし穴1：数学ライブラリの不足

**エラー：**
```
undefined reference to 'sin'
```

**解決策：**
リンカフラグに`-lm`を追加：
```yaml
verilator_extra_flags:
  - -LDFLAGS
  - -lm
```

### 落とし穴2：誤ったデータ型

**問題：**
```systemverilog
import "DPI-C" function int compute(input real x);  // 誤り！
```

```c
double compute(double x) {  // intではなくdoubleを返す
    return x * 2.0;
}
```

**解決策：**
型を正確に一致させる：
```systemverilog
import "DPI-C" function real compute(input real x);  // 正しい
```

### 落とし穴3：名前マングリング（C++）

**エラー：**
```
undefined reference to 'dpi_sin'
```

**原因：** C++ファイルで`extern "C"`を忘れた。

**解決策：**
常に以下を使用：
```c
#ifdef __cplusplus
extern "C" {
#endif

double dpi_sin(double x) { ... }

#ifdef __cplusplus
}
#endif
```

### 落とし穴4："pure"関数での副作用

**問題：**
```c
int counter = 0;

double not_pure(double x) {
    counter++;  // 副作用！
    return x * counter;
}
```

```systemverilog
// pureと宣言されているが、実際はpureではない！
import "DPI-C" pure function real not_pure(input real x);
```

**結果：** Verilatorが結果を誤ってキャッシュする可能性。

**解決策：** `pure`を削除するか、副作用を削除：
```systemverilog
import "DPI-C" function real not_pure(input real x);  // pureではない
```

### 落とし穴5：浮動小数点の比較

**問題：**
```systemverilog
if (sine_out == expected) begin  // 厳密な比較 - 悪い！
    $display("Match");
end
```

**解決策：** 許容誤差を使用：
```systemverilog
real tolerance = 0.001;
if ((sine_out > expected - tolerance) && (sine_out < expected + tolerance)) begin  // 良い
    $display("Match within tolerance");
end
```

---

## 高度なトピック

### オープン配列

SVからCへ可変サイズの配列を渡す。

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
        *elem *= 2.0;  // その場で変更
    }
}
```

### コンテキスト関数

シミュレーションコンテキスト（時間、スコープなど）にアクセス。

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

### 文字列の扱い

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

**警告：** 文字列のライフタイムは扱いが難しい。静的バッファは機能するが、スレッドセーフではない。

---

## FAQ

### Q：DPI-Cコードを合成できますか？

**A：** いいえ。DPI-Cはシミュレーション専用です。ハードウェアの場合、合成可能なRTLで機能を実装する必要があります。

### Q：importとexportのどちらが良いですか？

**A：** import（SVがCを呼び出す）から始めてください。よりシンプルで、90%のユースケースをカバーします。CがSVを呼び出す必要がある場合のみexportを追加してください。

### Q：DPI-CをVCSで使用できますか？

**A：** はい！このプロジェクトはVerilatorとVCSの両方をサポートしています。DPI-Cコードはシミュレータ間で移植可能です（ただし、一部の高度な機能は異なる場合があります）。

### Q：DPI-Cコードをデバッグするには？

**A：**
- SVで`$display`を使用して呼び出しをトレース
- C関数に`printf()`を追加
- Verilatorで`gdb`を使用：`gdb obj_dir/Vtop`
- 生成された`V*__Dpi.h`でインターフェースの問題を確認

### Q：パフォーマンスはどうですか？

**A：** DPI-C呼び出しにはオーバーヘッドがあります（言語境界を越える関数呼び出し）。単純な操作の場合、純粋なSVの方が高速な場合があります。複雑なアルゴリズムの場合、Cが勝ちます。最適化する前にプロファイリングしてください。

### Q：DPI-Cでスレッドを使用できますか？

**A：** 高度なトピックです。一部のシミュレータはサポートしていますが、扱いが難しいです。このプロジェクトでは、シンプルに保つ - シングルスレッドで十分です。

### Q：エラーをどう処理しますか？

**A：** エラーコードを返すか、特殊な値（NaN、負の値）を使用します。DPI-CはSV-C境界を越える例外処理を持っていません。

---

## 次のステップ

### 実験のアイデア

1. **正弦波を変更する：**
   - 周波数を10 MHzに変更
   - 異なる振幅を試す
   - コサイン波を作成（`dpi_cos`を使用）

2. **より多くの数学関数を追加：**
   - `dpi_sqrt`、`dpi_exp`、`dpi_log`を実装
   - ガウスノイズジェネレータを作成

3. **関数を組み合わせる：**
   - AM変調：`carrier * (1 + depth * message)`
   - FM変調：`sin(carrier + deviation * message)`

4. **リファレンスモデルを作成：**
   - Cでフィルタを実装
   - Cの「ゴールデン」モデルとRTL出力を比較

### 学習リソース

- **IEEE 1800標準** - 公式DPI-C仕様
- **Verilatorマニュアル** - DPI-Cに関する章（verilator.org）
- **シミュレータのドキュメント** - VCS、Questaなど
- **このサンプルコード** - コメントを注意深く読んでください！

---

## まとめ

**DPI-Cは強力なSystemVerilog-C統合を実現します：**

✅ SystemVerilogにC関数をインポート（最も一般的）
✅ CがSV関数を呼び出すためのエクスポート（高度）
✅ 既存のCライブラリを使用（math、ファイルI/Oなど）
✅ リファレンスモデルと高度なテストベンチを構築

**成功の鍵：**

1. データ型を正確に一致させる（real ↔ double）
2. Cコードで`extern "C"`を使用
3. `input`引数と戻り値を優先
4. 真にpureな関数を`pure`とマーク
5. 必要なライブラリをリンク（数学には-lm）

**覚えておいてください：** DPI-Cはシミュレーション用であり、合成用ではありません。検証とモデリングを強化するために使用し、RTLを書くことを避けるために使用しないでください！

---

**質問がありますか？** 完全な動作例については、`rtl/sine_wave_gen.sv`と`tb/sine_wave_gen_tb.sv`のサンプルコードを確認してください。
