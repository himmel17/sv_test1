# CLAUDE.md

このファイルは Claude Code (claude.ai/code) がこのリポジトリで作業する際のガイドです。
ここには**毎回の作業で必要な規約のみ**を記載し、詳細は末尾の「ドキュメント一覧」の各文書を参照してください。

## プロジェクト概要

SystemVerilog による SerDes 伝送路回路の開発・検証環境。Verilator(デフォルト)/ Synopsys VCS + GTKWave を使用し、YAML 駆動のテストフレームワークでテストを管理する。

**現状**:
- ✅ 仕様策定完了: FFE / DFE / CTLE / システムアーキテクチャ / テスト戦略(`spec/`、英語版 + `_ja` 日本語版)
- ✅ テストフレームワーク整備済み(YAML 設定 + シミュレータ抽象化レイヤー)
- ✅ 動作サンプル: `counter`, `demux_4bit`, `sine_wave_gen`(DPI-C 基礎), `ideal_amp_with_noise` / `ideal_amp_with_noise_batch`(DPI-C フリッカノイズ注入 PoC)
- 🚧 次フェーズ: `spec/` に基づく SerDes モジュールの RTL 実装(`rtl/tx/`, `rtl/rx/`, `rtl/channel/`, `rtl/modulation/`)

## よく使うコマンド

```bash
uv sync                                                    # 初回セットアップ(仮想環境 + 依存関係)
uv run python3 scripts/run_test.py --list                  # テスト一覧
uv run python3 scripts/run_test.py --all                   # 全テスト実行
uv run python3 scripts/run_test.py --test counter          # 個別テスト
uv run python3 scripts/run_test.py --test counter --view   # 波形表示付き(GTKWave)
uv run python3 scripts/run_test.py --clean --test counter  # クリーンビルド
uv run python3 scripts/run_test.py --test counter --simulator vcs  # VCS を使用
```

Python は必ず uv 仮想環境を使用する(`uv run` で実行、パッケージ追加は `uv add`)。グローバル環境は使わない。

## テスト追加手順(必須4ステップ)

1. `rtl/{module}.sv` を作成(`timescale` 必須。`rtl/tx/` 等のサブディレクトリ可)
2. `tb/{module}_tb.sv` を作成(下記「テストベンチ必須要件」を満たすこと)
3. `tests/test_config.yaml` にテスト定義を追加(記述項目は既存エントリとファイル内コメントを参照。`testbench_file: tx/xxx_tb.sv` のようにサブディレクトリパス対応)
4. `uv run python3 scripts/run_test.py --test {test_name}` で確認

### テストベンチ必須要件

雛形は `tb/counter_tb.sv` を参照。

- `module {module}_tb #(parameter SIM_TIMEOUT = <デフォルト値>);` — フレームワークが `-GSIM_TIMEOUT` で上書きする
- 波形ダンプのパスはハードコードせず plusarg で受け取る(フレームワークが `+dumpfile=sim/waves/{test_name}.{vcd|fst}` を渡す)。既定値は単体実行用で、`{test_name}` は YAML の `name` と一致させる:
  ```systemverilog
  string dumpfile;
  if (!$value$plusargs("dumpfile=%s", dumpfile))
      dumpfile = "sim/waves/{test_name}.vcd";
  $dumpfile(dumpfile);
  ```
- セルフチェック: `error_count` を数え、最後に `*** PASSED ... ***` / `*** FAILED: %0d errors ***` を表示
- タイムアウト watchdog:
  ```systemverilog
  initial begin
      #SIM_TIMEOUT;
      $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
      $finish;
  end
  ```

### タイムアウト設定(2種類)

- `sim_timeout`(テスト毎): **シミュレーション時間**。`"50us"` 等の単位付き文字列で指定し、テストベンチの timescale を自動検出して換算のうえ `-GSIM_TIMEOUT` で渡される
- `execution_timeout`(シミュレータ毎): **実時間**(wall-clock)。フリーズ対策として subprocess のタイムアウトに使用

## SystemVerilog スタイル規約

- **timescale を全 `.sv` ファイルの先頭に必ず記載**。設計ドメイン別の指針:
  - 低速(<1 GHz、一般デジタルロジック): `` `timescale 1ns / 1ps ``
  - 高速 SerDes(10–25 Gbps、FFE/DFE/CTLE/CDR/SerDes 本体): `` `timescale 1ps / 1fs ``
  - 超高速(>25 Gbps でピコ秒分解能が不足する場合のみ): `` `timescale 100fs / 1fs ``
  - 1つのテスト内では全ファイルで timescale を揃える(混在時はテストベンチ側が基準になり、警告が出る)
- リセット: アクティブロー同期リセット(`rst_n`)
- 順序回路: `always_ff @(posedge clk)` / 組み合わせ回路: `always_comb` または `assign`(`always @*` は使わない)
- オーバーフローフラグ等は組み合わせ回路を推奨(例: `assign overflow = (count == 8'hFF);`)
- CTLE 等のアナログ挙動は `real` 型による RNM(Real Number Modeling)。合成不可・シミュレーション専用

## シミュレータ要件

- **Verilator 5.0+**: 全テストで `--timing` と `--binary` を使用。`-Wno-TIMESCALEMOD` 付き
- 波形形式は Verilator フラグで決まる: `--trace`(または `--trace-vcd`)→ `.vcd`、`--trace-fst` → `.fst`。両方あれば FST(警告表示)。`--trace-threads` は形式を選ばない(5.052 では非推奨・無効で、`-Wall` 下ではビルドエラー)。判定対象は `common_flags` + `verilator_extra_flags`
- テスト単位で形式を固定するときは YAML のテストに `wave_format: vcd | fst` を書く(形式を選ぶ trace フラグを差し替える)。`verilator_extra_flags` に `--trace` を足しても、共通フラグに `--trace-fst` があれば FST のままになるため VCD には戻せない
- `scripts/verify_noise_match*.py` は VCD 専用。対象の 2 テストは `wave_format: vcd` で固定している
- FST の生成には lz4 のヘッダ(`liblz4-dev`)が必要(Verilator 5.052 で確認)
- シミュレータ選択の優先順位: CLI `--simulator` > テスト毎の `simulator:` > YAML の `default_simulator` > verilator
- 抽象化レイヤーは `scripts/simulators.py`(`BaseSimulator` / `VerilatorSimulator` / `VCSSimulator` / `SimulatorFactory`)。詳細は `scripts/run_test_guide.md`

## DPI-C(SystemVerilog-C 統合)

シミュレーション専用(合成不可)。C ソースは `dpi/` に置き、YAML で指定する:

```yaml
verilator_extra_flags:
  - ../dpi/your_code.c   # C ソースファイル
  - -LDFLAGS             # 以降はリンカフラグ
  - -lm                  # 数学ライブラリ(必要な場合)
```

- C 側は `extern "C"` 必須、データ型は正確に対応させる(`real` ↔ `double`)
- static 変数等で状態を持つ関数(フリッカノイズ生成器など)は **`pure` 宣言しない**(副作用があるため)。スレッドセーフでもない前提
- チュートリアル: `dpi/README_ja.md`(日本語)/ `dpi/README.md`(英語)
- フリッカノイズ PoC(ストリーミング版・バッチ版)の実行手順と実装詳細: `README.md` の「DPI-C サンプル」節、`dpi/batch_implementation_notes.md`

## ファイル構成

```
rtl/       RTL モジュール(DUT)。tx/ rx/ channel/ modulation/ は SerDes 実装用(現状空)
tb/        テストベンチ(セルフチェック式。tb/tx/ 等サブディレクトリ対応)
dpi/       DPI-C の C ソース、チュートリアル、生成バイナリデータ
spec/      SerDes 仕様書(FFE/DFE/CTLE/アーキテクチャ/テスト戦略。英語 + _ja 日本語版)
tests/test_config.yaml   テスト定義の中央レジストリ(テスト追加時はここを編集)
scripts/   run_test.py(オーケストレータ)、simulators.py(シミュレータ抽象化)、
           ノイズ生成・検証スクリプト、ガイド文書
sim/       シミュレーション出力(obj_dir/, waves/。gitignore 対象)
ref/       ローカル参照資料(外部設計データ。git 管理外)
```

## ドキュメント一覧

| ドキュメント | 内容 |
|---|---|
| `README.md` | セットアップ手順、使い方、DUT/テストベンチ仕様、DPI-C サンプル詳細、トラブルシューティング |
| `scripts/run_test_guide.md` | テストフレームワーク完全解説(アーキテクチャ、クラス構成、タイムアウト、CLI 引数) |
| `scripts/TIMESCALE_HANDLING.md` | timescale 自動検出と sim_timeout 換算の詳細 |
| `dpi/README_ja.md` / `dpi/README.md` | DPI-C チュートリアル(概念、データ型マッピング、落とし穴、FAQ) |
| `dpi/batch_implementation_notes.md` | フリッカノイズのバッチ方式(事前生成データ読み込み)実装ノート |
| `spec/ffe_specification.md` (+`_ja`) | FFE(7タップ FIR、プリ/ポストカーソル ISI 除去)仕様 |
| `spec/dfe_specification.md` (+`_ja`) | DFE(5タップ判定帰還、NRZ/PAM4 スライサ)仕様 |
| `spec/ctle_specification.md` (+`_ja`) | CTLE(RNM によるアナログ等化器)仕様 |
| `spec/serdes_architecture.md` (+`_ja`) | システム全体構成、モジュール階層、インターフェース定義 |
| `spec/test_strategy.md` (+`_ja`) | 検証計画(ユニット→統合→システム→コンプライアンス) |

RTL 実装時はブロック仕様書のインターフェース定義(ポート名・幅・型)に正確に従い、`spec/serdes_architecture.md` のモジュール階層とコンパイル順序を参照すること。
