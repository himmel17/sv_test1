# SystemVerilog SerDes Test Environment

SystemVerilogによるSerDes伝送路回路の開発と検証環境です。
VerilatorシミュレータとGTKWave波形ビューアを使用したデバッグ環境を提供します。

## クイックスタート

```bash
# 1. リポジトリのクローン
git clone <repository-url>
cd sv_test1

# 2. 依存関係のインストール（Verilator, GTKWaveが必要）
# Ubuntu/Debian:
# 必須パッケージ
sudo apt install git help2man perl python3 make autoconf g++ flex bison ccache
# Ubuntu向けの追加パッケージ（エラーが出ても無視してOK）
sudo apt install libfl2 libfl-dev zlib1g zlib1g-dev
# 性能向上用（オプションだが推奨）
sudo apt install libgoogle-perftools-dev numactl perl-doc

# Verilator clone & build
git clone https://github.com/verilator/verilator
cd verilator
git checkout stable
unset VERILATOR_ROOT
autoconf  # configureスクリプトを生成
./configure
make -j2  # 2 coreでbuild
sudo make install
verilator --version

# GTKWave install
sudo apt install gtkwave

# 3. Python環境のセットアップ（uvを使用）
curl -LsSf https://astral.sh/uv/install.sh | sh  # uvをインストール
uv sync                                            # 仮想環境作成 + 依存関係インストール（開発ツール含む）

# （オプション）本番環境用（開発ツールなし）
uv sync --no-dev

# 4. テストの実行（uv run python3で仮想環境のPythonを自動使用）
uv run python3 scripts/run_test.py --all                  # 全テスト実行
uv run python3 scripts/run_test.py --test counter --view  # 特定テストを実行し波形表示
```

## プロジェクト構造

```
.
├── rtl/                  # RTLソースコード（DUT）
│   ├── counter.sv        # 8ビット同期カウンター
│   ├── demux_4bit.sv     # 4ビット1:4デマルチプレクサ
│   ├── sine_wave_gen.sv  # DPI-C正弦波ジェネレータ（教育用）
│   ├── ideal_amp_with_noise.sv  # DPI-Cフリッカノイズアンプ（PoC）
│   ├── tx/               # 送信側モジュール（SerDes実装用、現状空）
│   ├── rx/               # 受信側モジュール（SerDes実装用、現状空）
│   ├── channel/          # 伝送路モデル（SerDes実装用、現状空）
│   └── modulation/       # 変調エンコーダ/デコーダ（SerDes実装用、現状空）
├── tb/                   # テストベンチ
│   ├── counter_tb.sv     # カウンターテストベンチ
│   ├── demux_4bit_tb.sv  # デマルチプレクサテストベンチ
│   ├── sine_wave_gen_tb.sv  # 正弦波ジェネレータテストベンチ
│   ├── ideal_amp_with_noise_tb.sv        # フリッカノイズテストベンチ（ストリーミング版）
│   ├── ideal_amp_with_noise_batch_tb.sv  # フリッカノイズテストベンチ（バッチ版）
│   └── tb_wrapper.cpp    # C++ラッパー（旧方式の名残。--binaryモード移行後は未使用）
├── dpi/                  # DPI-C実装（SystemVerilog-C統合）
│   ├── dpi_math.c        # 数学関数ラッパー（sin, cos）
│   ├── dpi_flicker_noise.c        # フリッカノイズジェネレータ（ストリーミング版）
│   ├── dpi_flicker_noise_batch.c  # フリッカノイズジェネレータ（バッチ版）
│   ├── flicker_noise_batch.bin    # バイナリデータ（バッチ版用、生成される）
│   ├── shaped_noise.bin           # スペクトル整形ノイズデータ（生成される）
│   ├── README.md         # DPI-Cチュートリアル（英語）
│   ├── README_ja.md      # DPI-Cチュートリアル（日本語）
│   └── batch_implementation_notes.md  # バッチ方式実装ノート
├── spec/                 # SerDes仕様書（FFE/DFE/CTLE/アーキテクチャ/テスト戦略）
│   └── *_specification.md, *_ja.md    # 英語版 + 日本語版
├── tests/                # テスト設定
│   └── test_config.yaml  # テスト定義ファイル（YAML、中央レジストリ）
├── sim/                  # シミュレーション出力（gitignore対象）
│   ├── obj_dir/          # Verilatorコンパイル成果物
│   ├── vcs/              # VCSコンパイル成果物
│   └── waves/            # 波形ファイル（VCD / FST）
├── scripts/              # テスト管理スクリプト
│   ├── run_test.py       # メインテスト実行スクリプト（オーケストレータ）
│   ├── simulators.py     # シミュレータ抽象化レイヤー（Verilator/VCS）
│   ├── run_test_guide.md # テストフレームワーク完全解説
│   ├── TIMESCALE_HANDLING.md      # timescale自動検出の詳細
│   ├── generate_flicker_noise.py  # Pythonリファレンス実装（ストリーミング版）
│   ├── generate_flicker_noise_batch.py  # Pythonリファレンス実装（バッチ版）
│   ├── generate_custom_noise.py   # 任意スペクトル整形ノイズ生成（実験的、テスト未接続）
│   ├── verify_noise_match.py      # 統計検証スクリプト（ストリーミング版）
│   ├── verify_noise_match_batch.py  # 厳密一致検証スクリプト（バッチ版）
│   └── flicker_noise_*.{npy,png,log}  # 生成される検証データ（scripts/内）
├── ref/                  # ローカル参照資料（外部設計データ、git管理外）
├── pyproject.toml        # Python依存関係定義（推奨、Python 3.12+）
├── uv.lock               # 依存関係ロックファイル
├── requirements.txt      # Python依存関係 - 実行環境（後方互換性用）
├── requirements-dev.txt  # Python依存関係 - 開発環境（後方互換性用）
├── .venv/                # Python仮想環境（uv）
├── .gitignore            # Git除外設定
├── README.md             # このファイル
└── CLAUDE.md             # Claude Code用ガイド
```

## 必要な環境

- **Verilator** 5.0以上（検証済み: 5.042, 5.052）— `--timing`, `--binary` を使用するため 5.0 以上が必須
- **GTKWave** 3.3以上（検証済み: 3.3.104）
- **Python** 3.12以上（`pyproject.toml` の `requires-python = ">=3.12.11"` に準拠）
  - 主な依存: pyyaml, numpy, scipy, matplotlib, vcdvcd, pyqt6（`uv sync` で自動インストール）
- **Synopsys VCS**（オプション）— `--simulator vcs` 指定時のみ必要

## インストール

### Ubuntu/Debian

```bash
sudo apt install gtkwave python3
```

**注**: apt の Verilator は 5.0 未満の場合があります。バージョンが古い場合は「クイックスタート」記載の手順でソースからビルドしてください。

### Python依存関係のインストール

#### 方法1: uv + pyproject.toml（推奨）

`uv sync`は`pyproject.toml`から依存関係を読み込み、仮想環境の作成とパッケージインストールを一度に実行します。

```bash
# uvのインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 仮想環境作成 + 依存関係インストール（一度に実行）
uv sync                       # 実行環境 + 開発ツール（デフォルト）
# または
uv sync --no-dev              # 実行環境のみ（本番用）

# 仮想環境のアクティベート
source .venv/bin/activate     # Linux/macOS
# または
.venv\Scripts\activate        # Windows
```

**利点:**
- `pyproject.toml`で一元管理（PEP 621準拠）
- `uv.lock`による完全な再現性
- 高速なインストール

**注**: `uv sync`はデフォルトで開発依存関係（linter等）も含みます。本番環境では`--no-dev`を使用してください。

#### 方法2: pip + requirements.txt（後方互換性）

```bash
# 実行環境のみ
pip3 install -r requirements.txt

# 開発環境（linter等も含む）
pip3 install -r requirements-dev.txt
```

または

```bash
pip3 install pyyaml
```

**注**: `requirements.txt`と`requirements-dev.txt`は後方互換性のために保持されています。新規セットアップでは`uv sync`の使用を推奨します。

## 使用方法（YAML設定ベース）

### uvを使用する場合（推奨）

`uv run`を使うと、仮想環境のアクティベート不要で直接スクリプトを実行できます。

```bash
# テスト一覧表示
uv run python3 scripts/run_test.py --list

# 全テスト実行
uv run python3 scripts/run_test.py --all

# 特定のテスト実行
uv run python3 scripts/run_test.py --test counter

# 波形表示付き実行
uv run python3 scripts/run_test.py --test counter --view

# クリーンビルド
uv run python3 scripts/run_test.py --clean --test counter

# クリーンのみ
uv run python3 scripts/run_test.py --clean-only

# カスタム設定ファイル使用
uv run python3 scripts/run_test.py --config my_tests.yaml --test counter
```

### 仮想環境をアクティベートして使用する場合

```bash
# 仮想環境のアクティベート
source .venv/bin/activate  # Linux/macOS

# テスト実行（以降はpython3で実行可能）
python3 scripts/run_test.py --all
python3 scripts/run_test.py --test counter --view
```

## 動作確認項目

✓ Verilatorのコンパイルが成功すること
✓ シミュレーションが正常に実行されること
✓ VCD波形が正しく生成されること
✓ GTKWaveで波形が表示できること
✓ カウンター動作が正しいこと（0→255→0のループ）
✓ デマルチプレクサの出力分離が正しいこと
✓ 複数テストの並行管理ができること

## DUT仕様

### counter.sv - 8ビット同期カウンター

**入力**
- `clk`: クロック入力
- `rst_n`: アクティブローの同期リセット

**出力**
- `count[7:0]`: 8ビットカウンタ値
- `overflow`: オーバーフローフラグ（カウンタが255の時にHigh）

**動作**
- クロックの立ち上がりエッジで1ずつインクリメント
- 255の次は0にラップアラウンド
- `rst_n`がLowの時、カウンタは0にリセット

### demux_4bit.sv - 4ビット1:4デマルチプレクサ

**入力**
- `data_in[3:0]`: 4ビットデータ入力
- `sel[1:0]`: 2ビット選択信号（0-3）

**出力**
- `out0[3:0]`: 出力0
- `out1[3:0]`: 出力1
- `out2[3:0]`: 出力2
- `out3[3:0]`: 出力3

**動作**
- `sel`で選択された出力に`data_in`を転送
- 選択されていない出力は`4'h0`
- 組み合わせ回路（`always_comb`）

## テストベンチ仕様

### counter_tb.sv

**機能**
- クロック生成（100MHz、10ns周期）
- リセットシーケンス制御
- カウント動作の自動検証
- VCD波形ダンプ
- エラーカウントとレポート

**テスト内容**
1. リセット動作の確認
2. 270クロック分のカウント動作確認
3. オーバーフローフラグの検証
4. 動作中のリセット動作確認

### demux_4bit_tb.sv

**機能**
- 複数データパターンによる動作検証
- 全選択値（sel=0-3）の網羅テスト
- 出力分離の検証
- VCD波形ダンプ
- 自動エラーカウント

**テスト内容**
1. 4つの選択値それぞれで4つのデータパターンをテスト（計16パターン）
2. 選択された出力のみが非ゼロであることを確認
3. 出力分離の検証（1つの出力のみアクティブ）

## DPI-C サンプル

このプロジェクトには、SystemVerilogとC言語の統合を実演する **DPI-C (Direct Programming Interface for C)** サンプルが含まれています。

### sine_wave_gen（基礎DPI-C）

**目的**: C言語の`sin()`関数を使用した基本的なDPI-C統合の教育用サンプル

**ファイル**:
- `dpi/dpi_math.c` - `math.h`の`sin()`, `cos()`ラッパー
- `rtl/sine_wave_gen.sv` - DPI-Cを使用したパラメータ化正弦波ジェネレータ
- `tb/sine_wave_gen_tb.sv` - DPI-C検証付きセルフチェックテストベンチ

**実行方法**:
```bash
uv run python3 scripts/run_test.py --test sine_wave_gen
```

### ideal_amp_with_noise（高度DPI-C + 検証）

**目的**: アナログノイズモデリングのためのステートフルDPI-C実装とPython検証のProof of Concept

**ファイル**:
- `scripts/generate_flicker_noise.py` - Pythonリファレンス実装（Voss-McCartney アルゴリズム）
- `dpi/dpi_flicker_noise.c` - DPI-C用ステートフルC実装
- `rtl/ideal_amp_with_noise.sv` - DPI-Cノイズ注入付き理想アンプ
- `tb/ideal_amp_with_noise_tb.sv` - DC入力セルフチェックテストベンチ
- `scripts/verify_noise_match.py` - 統計検証スクリプト（Python vs SystemVerilog）

**特徴**:
- ✅ **ステートフルDPI-C**: 呼び出し間で内部状態（ノイズソース、サンプルカウンタ）を保持
- ✅ **1/fノイズ**: フリッカノイズ生成のためのVoss-McCARTNEYアルゴリズム実装
- ✅ **Python プロトタイプ → C実装**: アルゴリズム検証ワークフロー
- ✅ **統計的検証**: RMSとスペクトル傾きの比較（サンプル単位ではない）
- ✅ **VCDベース解析**: シミュレーション波形からデータ抽出して検証
- ✅ **スペクトル解析**: FFTベースのパワースペクトル密度検証
- ✅ **リセット処理**: 解析からリセットトランジェントを適切に除外

**検証ワークフロー（ストリーミング版 - Method 1）**:
```bash
# ステップ1: Pythonリファレンス生成（1024サンプル、100MHzサンプリング）
uv run python3 scripts/generate_flicker_noise.py
# 出力: scripts/flicker_noise_reference.npy, scripts/flicker_noise_spectrum.png

# ステップ2: DPI-Cノイズ注入付きSystemVerilogシミュレーション実行
uv run python3 scripts/run_test.py --test ideal_amp_with_noise
# 出力: sim/waves/ideal_amp_with_noise.vcd

# ステップ3: PythonとSystemVerilogの統計的比較
uv run python3 scripts/verify_noise_match.py
# 出力: scripts/flicker_noise_verification.png
# 検証: RMS誤差 < 10%, スペクトル傾き ≈ -1 ± 0.2
```

**検証ワークフロー（バッチ版 - Method 2）**:

厳密なサンプル単位の一致検証が必要な場合は、バッチ版を使用します：

```bash
# ステップ1: Pythonリファレンスとバイナリファイル生成（4096サンプル）
uv run python3 scripts/generate_flicker_noise_batch.py
# 出力: scripts/flicker_noise_batch_reference.npy
#       scripts/flicker_noise_batch_spectrum.png
#       dpi/flicker_noise_batch.bin (32 KB DPI-C用)

# ステップ2: SystemVerilogシミュレーション実行
uv run python3 scripts/run_test.py --test ideal_amp_with_noise_batch
# 出力: sim/waves/ideal_amp_with_noise_batch.vcd

# ステップ3: 厳密一致検証
uv run python3 scripts/verify_noise_match_batch.py
# 出力: scripts/flicker_noise_batch_verification.png
#       scripts/flicker_noise_batch_verification.log (詳細ログ)
# 検証: 100%厳密一致（4096/4096サンプル、最大誤差 ~1e-15 V）
```

**バッチ版の特徴**:
- サンプル数: 4096（ストリーミング版は1024）
- DPI-C: 事前生成されたバイナリファイルをロード（ストリーミング版はリアルタイム生成）
- 検証: サンプル単位で厳密一致（ストリーミング版は統計的比較のみ）
- 許容誤差: 1ナノボルト（ストリーミング版は10% RMS）
- 出力: サンプル詳細ログファイルを含む

**バッチ版のファイル**:
- `scripts/generate_flicker_noise_batch.py` - Pythonリファレンス + バイナリファイル生成
- `dpi/dpi_flicker_noise_batch.c` - 事前生成データをロードするDPI-C実装
- `tb/ideal_amp_with_noise_batch_tb.sv` - バッチ版テストベンチ（4096サンプル）
- `scripts/verify_noise_match_batch.py` - 厳密一致検証スクリプト
- 設計検討の経緯は `dpi/batch_implementation_notes.md` を参照

**関連（実験的）**: `scripts/generate_custom_noise.py` - 任意のターゲットスペクトル（CSVまたは数式）からスペクトル整形ノイズを生成し `dpi/shaped_noise.bin` に出力するスクリプト。ホワイトノイズをFFT→ゲインアレイでshaping→IFFTする方式。現時点ではテストフレームワークには未接続。

**実装の詳細**:

- **Cのstatic変数によるステートフル設計**:
  - C言語の`static`キーワードで宣言された変数はDPI-C関数呼び出し間で値を保持
  - `static int initialized`: 初回初期化後に1を保持、再初期化を防止
  - `static double noise_sources[10]`: ノイズソース値が呼び出し間で保存される
  - `static unsigned long sample_counter`: 連続的にインクリメント（0→1→2→...）
  - **重要**: `static`なしの場合、毎回の呼び出しで初期値にリセットされる
  - **実行シーケンス例**:
    - 呼び出し1: `initialized=0` → 初期化 → `initialized=1`, `counter=0` → return
    - 呼び出し2: `initialized=1`（保持！） → 初期化スキップ, `counter=1` → return
    - 呼び出し3: `initialized=1`（保持！） → 初期化スキップ, `counter=2` → return
  - 通常のCローカル変数とは根本的に異なる動作
  - static変数はスタックではなくプログラムメモリに一度だけ割り当てられる

- **異なる乱数生成器**: C `rand()` vs Python `random.uniform()` - サンプルは異なるが統計特性は一致

- **Pure関数ではない**: 副作用（static状態変更）があるため、SystemVerilogで`pure`宣言しない

- **スレッドセーフではない**: ロックなしでstatic変数を使用、シングルスレッドシミュレーション想定

- **経験的較正**: RNG差を補償するためにRAW_RMS調整

- **リセットスキップ**: テストベンチは1044サンプル収集（リセットスキップ20 + 有効1024）

- **VCD解析**: 最初の10サンプル（リセット期間）をスキップしてsample_counter値を整列

**用途**: SerDes/RFアプリケーションのデジタルシミュレーションでアナログ効果（ノイズ、ジッタ）をモデル化する方法を実演

詳細は `dpi/README.md`（英語）または `dpi/README_ja.md`（日本語）の包括的なDPI-Cチュートリアルを参照してください。

## テスト設定ファイル（YAML）

`tests/test_config.yaml`でテストを定義します：

```yaml
project:
  rtl_dir: rtl
  tb_dir: tb
  sim_dir: sim
  obj_dir: sim/obj_dir
  vcs_dir: sim/vcs
  waves_dir: sim/waves
  default_simulator: verilator  # グローバルデフォルト: verilator または vcs

# シミュレータ別設定
simulators:
  verilator:
    common_flags:
      - --binary
      - --timing
      - -Wall
      - --trace-fst        # 波形形式: --trace → .vcd / --trace-fst → .fst
      - -Wno-TIMESCALEMOD
    execution_timeout: "30s"  # Verilator実行のフリーズ対策（実時間）

  vcs:
    common_flags:
      - -sverilog
      - -timescale=1ns/1ps
      - -debug_access+all
      - +vcs+lic+wait
      - -full64
    execution_timeout: "30s"

tests:
  - name: counter
    enabled: true
    description: "8-bit synchronous counter with overflow detection"
    top_module: counter_tb
    testbench_file: counter_tb.sv
    rtl_files:
      - counter.sv
    verilator_extra_flags: []
    sim_timeout: "50us"  # シミュレーション時間（-GSIMTIMEOUTで渡される）

  - name: demux_4bit
    enabled: true
    description: "4-bit 1:4 demultiplexer"
    top_module: demux_4bit_tb
    testbench_file: demux_4bit_tb.sv
    rtl_files:
      - demux_4bit.sv
    verilator_extra_flags: []
    sim_timeout: "10us"  # シミュレーション時間

  # サブディレクトリパスの例（SerDesモジュール用）
  - name: tx_ffe
    enabled: true
    description: "Transmit FFE (Feed-Forward Equalizer)"
    top_module: tx_ffe_tb
    testbench_file: tx/tx_ffe_tb.sv      # tb/tx/tx_ffe_tb.sv として解決
    rtl_files:
      - tx/tx_ffe.sv                      # rtl/tx/tx_ffe.sv として解決
      - serdes_common.sv                  # rtl/serdes_common.sv（ルートと混在可能）
    verilator_extra_flags: []
    sim_timeout: "100us"
```

**重要な設定項目：**

- `execution_timeout`: Verilator実行の実時間タイムアウト（フリーズ対策）
- `default_simulator`: グローバルデフォルトのシミュレータ（`verilator` または `vcs`。テストごとに `simulator:` で上書き可能、CLI の `--simulator` が最優先）
- `sim_timeout`: シミュレーション時間のタイムアウト（テストベンチの`SIM_TIMEOUT`パラメータに渡される）
  - 単位: `ns`, `us`, `ms`, `s` が使用可能
  - テストベンチの`timescale`を**自動検出**して数値に変換される（詳細: `scripts/TIMESCALE_HANDLING.md`）
- `testbench_file`: サブディレクトリパス対応（例: `tx/tx_ffe_tb.sv` → `tb/tx/` 配下）
- `rtl_files`: サブディレクトリパス対応（例: `tx/tx_ffe.sv` → `rtl/tx/` 配下）
  - ルートディレクトリとサブディレクトリのパスを混在可能

### 新しいテストの追加方法

1. **RTLモジュールを作成**: `rtl/`に新しいモジュールを追加
   - `timescale 1ns / 1ps`を含める
   - サブディレクトリ構造をサポート（例: `rtl/tx/`, `rtl/rx/`）

2. **テストベンチを作成**: `tb/`にテストベンチファイルを追加
   - パラメータ化されたタイムアウトを含める: `module xxx_tb #(parameter SIM_TIMEOUT = xxxx);`
   - `timescale 1ns / 1ps`を含める
   - 波形ダンプパスは plusarg で受け取る（フレームワークが `+dumpfile=sim/waves/{test_name}.{vcd|fst}` を渡す。雛形は `tb/counter_tb.sv`）:
     `if (!$value$plusargs("dumpfile=%s", dumpfile)) dumpfile = "sim/waves/{test_name}.vcd"; $dumpfile(dumpfile);`
   - タイムアウト処理: `initial begin #SIM_TIMEOUT; $display("ERROR: ..."); $finish; end`
   - サブディレクトリ構造をサポート（例: `tb/tx/`, `tb/rx/`）

3. **YAML設定を追加**: `tests/test_config.yaml`に新しいテスト定義を追加

4. **実行確認**: `python3 scripts/run_test.py --test <新テスト名>`

例：SerDes送信モジュールを追加する場合

```yaml
tests:
  # 既存のテスト
  - name: counter
    enabled: true
    ...

  # 新規SerDes TXテスト（サブディレクトリ対応）
  - name: serdes_tx
    enabled: true
    description: "SerDes transmitter module"
    top_module: serdes_tx_tb
    testbench_file: tx/serdes_tx_tb.sv   # サブディレクトリパス対応
    rtl_files:
      - tx/serdes_tx.sv                   # サブディレクトリパス対応
      - tx/serializer.sv                  # 複数のサブディレクトリファイル
      - serdes_common.sv                  # ルートディレクトリのファイルと混在
    verilator_extra_flags:
      - --trace-underscore
    sim_timeout: "100us"  # シミュレーション時間タイムアウト
```

## 次のステップ

このテンプレートをベースに、SerDes伝送路回路の開発を進めることができます：

1. `rtl/`にSerDesモジュールを追加
2. `tb/`に対応するテストベンチを作成
3. `tests/test_config.yaml`に新しいテスト定義を追加
4. 複数のテストを並行して管理・実行可能

## トラブルシューティング

### Verilatorコンパイルエラー
- SystemVerilog構文を確認
- `--timing`オプションが必要（Verilator 5.0以上）

### 波形ファイル（VCD / FST）が生成されない・形式が違う
- `sim/waves/`ディレクトリの存在を確認
- テストベンチが `$value$plusargs("dumpfile=%s", ...)` で受け取ったパスを `$dumpfile()` に渡しているか確認
- 形式は Verilator フラグで決まる: `--trace`（`--trace-vcd`）→ `.vcd`、`--trace-fst` → `.fst`
  - `common_flags` と `verilator_extra_flags` の両方に VCD/FST フラグがあると FST になる（警告表示）
  - `--trace-threads` は形式を選ばない（Verilator 5.052 では非推奨・無効で、`-Wall` 下では警告によりビルドが止まる）
- テスト単位で形式を固定するには、テスト定義に `wave_format: vcd`（または `fst`）を書く
  - 共通フラグの `--trace` / `--trace-vcd` / `--trace-fst` が、指定した形式のフラグに差し替わる
  - 共通フラグが `--trace-fst` のとき、`verilator_extra_flags` に `--trace` を足しても VCD にはならない（FST が優先されるため）
- `scripts/verify_noise_match*.py` は VCD 専用。`ideal_amp_with_noise` / `ideal_amp_with_noise_batch` は `wave_format: vcd` で固定している
- FST のビルドで `fatal error: lz4.h: No such file or directory` が出る場合は lz4 の開発ヘッダを入れる（Verilator 5.052 で確認）:
  `sudo apt install -y liblz4-dev`

### GTKWaveが起動しない
- `gtkwave --version`でインストールを確認
- 環境変数`DISPLAY`が設定されているか確認（WSL使用時）

### Pythonモジュールが見つからない（ModuleNotFoundError: No module named 'yaml'）
- `uv run python3 ...` で実行しているか確認（仮想環境が自動的に使われる）
- 依存関係が正しくインストールされているか確認:
  ```bash
  uv sync
  ```
- 仮想環境をアクティベートして使う場合:
  ```bash
  source .venv/bin/activate  # Linux/macOS
  ```

### uvコマンドが見つからない
- uvがインストールされているか確認:
  ```bash
  uv --version
  ```
- インストールされていない場合:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # シェルを再起動するか、PATHをリロード
  source ~/.bashrc  # または ~/.zshrc
  ```

## ドキュメント一覧

| ドキュメント | 内容 |
|---|---|
| `README.md` | このファイル（セットアップ、使い方、サンプル詳細、トラブルシューティング） |
| `CLAUDE.md` | Claude Code用の開発規約（テスト追加手順、コーディングスタイル） |
| `scripts/run_test_guide.md` | テストフレームワーク完全解説（アーキテクチャ、クラス構成、タイムアウト、CLI引数） |
| `scripts/TIMESCALE_HANDLING.md` | timescale自動検出とsim_timeout換算の詳細 |
| `dpi/README_ja.md` / `dpi/README.md` | DPI-Cチュートリアル（日本語 / 英語） |
| `dpi/batch_implementation_notes.md` | フリッカノイズのバッチ方式実装ノート |
| `spec/ffe_specification.md` (+`_ja`) | FFE（Feed-Forward Equalizer）仕様 |
| `spec/dfe_specification.md` (+`_ja`) | DFE（Decision Feedback Equalizer）仕様 |
| `spec/ctle_specification.md` (+`_ja`) | CTLE（Continuous-Time Linear Equalizer）仕様 |
| `spec/serdes_architecture.md` (+`_ja`) | SerDesシステムアーキテクチャ仕様 |
| `spec/test_strategy.md` (+`_ja`) | 検証戦略・テスト計画 |

## ライセンス

このプロジェクトは検証・開発目的で自由に使用できます。
