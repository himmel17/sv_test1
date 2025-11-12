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
│   ├── tx/               # 送信側モジュール（サブディレクトリ例）
│   └── rx/               # 受信側モジュール（サブディレクトリ例）
├── tb/                   # テストベンチ
│   ├── counter_tb.sv     # カウンターテストベンチ
│   ├── demux_4bit_tb.sv  # デマルチプレクサテストベンチ
│   ├── tx/               # 送信側テストベンチ（サブディレクトリ例）
│   └── rx/               # 受信側テストベンチ（サブディレクトリ例）
├── tests/                # テスト設定
│   └── test_config.yaml  # テスト定義ファイル（YAML）
├── sim/                  # シミュレーション出力
│   ├── obj_dir/          # Verilatorコンパイル成果物
│   └── waves/            # VCD波形ファイル
├── scripts/              # テスト管理スクリプト
│   └── run_test.py       # メインテスト実行スクリプト
├── pyproject.toml        # Python依存関係定義（推奨）
├── uv.lock               # 依存関係ロックファイル
├── requirements.txt      # Python依存関係 - 実行環境（後方互換性用）
├── requirements-dev.txt  # Python依存関係 - 開発環境（後方互換性用）
├── .venv/                # Python仮想環境（uv）
├── .gitignore            # Git除外設定
├── README.md             # このファイル
└── CLAUDE.md             # Claude Code用ガイド
```

## 必要な環境

- **Verilator** 5.0以上（検証済み: 5.042）
- **GTKWave** 3.3以上（検証済み: 3.3.104）
- **Python** 3.6以上

## インストール

### Ubuntu/Debian
```bash
sudo apt install verilator gtkwave python3
```

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

## テスト設定ファイル（YAML）

`tests/test_config.yaml`でテストを定義します：

```yaml
verilator:
  common_flags:
    - --binary
    - --timing
    - -Wall
    - --trace
    - -Wno-TIMESCALEMOD
  execution_timeout: "30s"  # Verilator実行のフリーズ対策

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
- `sim_timeout`: シミュレーション時間のタイムアウト（テストベンチの`SIM_TIMEOUT`パラメータに渡される）
  - 単位: `ns`, `us`, `ms`, `s` が使用可能
  - テストベンチの`timescale`（現在`1ns/1ps`）に基づいて数値に変換される
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
   - VCDダンプパスを正しく設定: `$dumpfile("sim/waves/{test_name}.vcd")`
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

### VCDファイルが生成されない
- `sim/waves/`ディレクトリの存在を確認
- テストベンチの`$dumpfile()`パスを確認

### GTKWaveが起動しない
- `gtkwave --version`でインストールを確認
- 環境変数`DISPLAY`が設定されているか確認（WSL使用時）

### Pythonモジュールが見つからない（ModuleNotFoundError: No module named 'yaml'）
- uv仮想環境を使用している場合は、仮想環境がアクティベートされているか確認:
  ```bash
  source .venv/bin/activate  # Linux/macOS
  ```
- 依存関係が正しくインストールされているか確認:
  ```bash
  uv pip install -r requirements.txt
  # または
  pip3 install pyyaml
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

## ライセンス

このプロジェクトは検証・開発目的で自由に使用できます。
