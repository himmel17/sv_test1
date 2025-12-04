#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom Noise Generator - Batch Mode (Method 2)

- two-sidedでPSDの高さが1 V^2/Hzとなるσを計算して，そのσでWhite Noiseを生成する．
- ターゲット（最終的に生成したい）ノイズのスペクトルを.csvファイルから読み込む．
  または，mockとなるような式からノイズスペクトルを生成する．
  これをshapingするためのゲインアレイとして使用する．
- White NoiseをFFTして，それをターゲットのノイズスペクトルから生成したゲインアレイでshapingする．
- shapingしたスペクトルをIFFTして時間領域データにする．
- param.debugがTrueのとき，Target Noise PSDとshapingしたノイズのPSDを重ね描して，
  意図した通りの特性のノイズデータが得られているか確認する．

FFT, IFFT操作をするので，周波数領域ではtwo-sidedで扱う．
two-sidedのアレイのオブジェクト名の末尾には "_2" をつけて，そのオブジェクトがtwo-sidedであることを明確にする．
FFT, IFFTの際の周波数ベクトルの並びはscipy.fft.fft, ifftの仕様により
  f = [0, 1, ...,   n/2-1,     -n/2, ..., -1] / (d*n)   if n is even
  f = [0, 1, ...,   (n-1)/2,     -(n-1)/2, ..., -1] / (d*n)   if n is odd
である．
負の周波数要素が必要であることに注意．

データ数はeven前提でコーディングする．
このfアレイは scipy.fft.fftfreq() で生成することができるのでそれを使っているが，
ターゲットNoise Spectrumからtwo-sidedゲインアレイを作る際にはそれが使えないので手動で生成している．
"""

from dataclasses import dataclass
from typing import NamedTuple
import numpy as np
from scipy import fft
from scipy import signal
from scipy import interpolate
import matplotlib.pyplot as plt
from pathlib import Path


def main():
    param = Param(debug=False)
    gsn = GenShapedNoise(param)

    white_noise: np.ndarray = gsn.gen_white_noise_0db()

    # white_noiseの時間データとスペクトルをプロット
    # one-sidedのスペクトルをプロットするので，PSDの高さが平均で3dBなら正しい
    if param.debug:
        # white noise time data
        gsn.plot_time_data(np.arange(len(white_noise)) / param.Fs, white_noise, fig_num=1)

        # white noise spectrum
        freq, psd_white = signal.welch(
            x=white_noise, fs=param.Fs, window='boxcar',
            nperseg=2**13, noverlap=None,  # 50% overlap
            nfft=None, detrend='constant',  # constant,linear
            return_onesided=True
        )
        gsn.plot_spectrum(freq, psd_white, label='White Noise (one-sided)', fig_num=2, verbose=True)

    # Shaping gainのSpline object を作る前準備として，その対象となるデータを用意する (two-sided)
    # .csvファイルを読み込むか，モデル化した式からデータをCubicSplineの引数で扱えるようなデータを取得する
    freq_2, shaping_gain_2, freq_target, psd_target = gsn.get_shaping_gain_mock()  # このmethodを色々対応できるように拡張する！！！

    # shaping_gain_2の正周波数側と負周波数側をプロット
    if param.debug:
        # マイナスの周波数はnp.log10()が計算できないので，正の周波数部分のみスライスしてプロット
        gsn.plot_spectrum(freq_2[freq_2 > 0], (shaping_gain_2[freq_2 > 0]) ** 2,
                          label='Target PSD (two-sided, positive freq.)', fig_num=3)

        # マイナスの周波数側も周波数の符号を反転してプロット確認してみる
        gsn.plot_spectrum(-freq_2[freq_2 < 0], (shaping_gain_2[freq_2 < 0]) ** 2,
                          label='Target PSD (two-sided, negative freq.)', fig_num=4)

    # 意図したノイズスペクトルを得るためのシェイピングゲインデータ(two-sided)からsplineオブジェクト化する．
    # このオブジェクトの引数に任意の周波数を与えると，それに対するゲインが得られるのでシェイピングに使う
    spline_2 = interpolate.CubicSpline(freq_2, shaping_gain_2)

    # FFT (time domain -> frequency domain)
    white_noise_fft_2: np.ndarray = fft.fft(white_noise)
    freq_2: np.ndarray = fft.fftfreq(len(white_noise_fft_2), d=1./param.Fs)

    # Shaping (frequency domain)
    # FFTで得られた複素振幅(white_noise_fft_2)をspline_2でシェイピングする
    shaped_noise_fft_2: np.ndarray = spline_2(freq_2) * white_noise_fft_2

    # IFFT (frequency domain -> time domain)
    shaped_noise: np.ndarray = np.real(fft.ifft(shaped_noise_fft_2))  # 虚部(位相)の情報は現実世界のノイズには載らないので無視

    # 目標としているノイズスペクトルとshaped_noiseのスペクトルが一致するかプロット確認
    if param.debug:
        freq_shaped, psd_shaped = signal.welch(
            x=shaped_noise, fs=param.Fs, window='boxcar',
            nperseg=2**13, noverlap=None,  # 50% overlap
            nfft=None, detrend='constant',  # constant,linear
            return_onesided=True
        )
        # gsn.plot_spectrum(freq_shaped, psd_shaped, fig_num=5)
        gsn.plot_spectrum_compare(freq_shaped, psd_shaped, "Generated Noise PSD",
                                  freq_target, psd_target, "Target Noise PSD",
                                  fig_num=5)

    # Save NumPy array for Python verification (in scripts/ directory)
    np.save(param.npy_path, shaped_noise)
    print(f"      NumPy reference saved: {param.npy_path}\n")

    # Save binary for DPI-C loading (Method 2)
    print(f"      Saving binary for DPI-C (Method 2)...")
    binary_size = gsn.save_binary(shaped_noise, param.bin_path)

    # Verify binary size
    expected_size = param.samples * 8  # 8 bytes per double
    if binary_size == expected_size:
        print(f"      ✓ Binary size correct: {binary_size} == {expected_size}")
    else:
        print(f"      ✗ WARNING: Binary size mismatch: {binary_size} != {expected_size}")


class Param(NamedTuple):
    seed: str = 17        # Fixed seed for deterministic generation
    samples: int = 2**17  # 生成する乱数の数
    Fs: float = 40e9      # アナログ系をサンプリングする周波数．一旦Fbaudの10倍の周波数に設定
    debug: bool = False
    npy_path: str = 'scripts/shaped_noise_reference.npy'
    bin_path: str = 'dpi/shaped_noise.bin'


@dataclass
class GenShapedNoise():
    param: Param

    def __post_init__(self) -> None:
        self.Ts: float = 1 / self.param.Fs

    def gen_white_noise_0db(self) -> np.ndarray:
        """
        PSD (two-sided) の高さが0dB [V**2/Hz]であるWhite Noiseを生成する．

        Returns
        -------
        white_noise : np.ndarray
            White Noiseの時間データ
        """
        noise_sigma: float = np.sqrt(self.param.Fs)
        np.random.seed(self.param.seed)
        white_noise: np.ndarray = np.random.normal(0., noise_sigma, self.param.samples)

        return white_noise

    def plot_time_data(self, time: np.ndarray, data: np.ndarray, fig_num: int = 1) -> None:
        """
        tome vs dataをプロットする

        Parameters
        ----------
        time : np.ndarray
            時間アレイ
        data : np.ndarray
            データアレイ
        fig_num : int
            Matplotlibのfigureオブジェクト番号を指定する
        """
        if plt.fignum_exists(fig_num):
            fig = plt.figure(fig_num)  # num==1のfigureオブジェクトを取得
            fig.canvas.draw_idle()  # 明示的に再描画を強制
            fig.clear()  # これでAxesオブジェクトとプロットのオブジェクトも削除される
            ax = fig.subplots(nrows=1, ncols=1)
        else:
            fig, ax = plt.subplots(nrows=1, ncols=1, num=fig_num, figsize=(8, 6), dpi=100, facecolor='w', edgecolor='k')

        ax.plot(time, data, '-o', lw=2, color='#ff0000', label='noise')
        ax.legend(loc='best', fontsize=12)  # upper right, upper left, lower right, lower left
        ax.set_xlabel('time [s]', fontsize=15)
        ax.set_ylabel('[V]', fontsize=15)

        ax.minorticks_on()
        ax.grid(visible=True, which='major', color='k', linestyle=':')
        ax.grid(visible=True, which='minor', color='k', linestyle=':', alpha=0.3)

        fig.tight_layout()
        # fig.savefig('time_data.png')
        plt.show(block=False)

    def plot_spectrum(
            self,
            freq: np.ndarray,
            psd: np.ndarray,
            label: str,
            fig_num: int = 2,
            verbose: bool = False
    ) -> None:
        """
        freq vs psdをsemilogxでプロットする

        Parameters
        ----------
        freq : np.ndarray
            周波数アレイ
        psd : np.ndarray
            PSDアレイ [V**2/Hz]
        label : str
            プロットに対するラベル
        fig_num : int
            Matplotlibのfigureオブジェクト番号を指定する
        verbose : bool
            Trueの場合，PSDの平均値を標準出力する
        """
        if plt.fignum_exists(fig_num):
            fig = plt.figure(fig_num)  # num==1のfigureオブジェクトを取得
            fig.canvas.draw_idle()  # 明示的に再描画を強制
            fig.clear()  # これでAxesオブジェクトとプロットのオブジェクトも削除される
            ax = fig.subplots(nrows=1, ncols=1)
        else:
            fig, ax = plt.subplots(nrows=1, ncols=1, num=fig_num, figsize=(8, 6), dpi=100, facecolor='w', edgecolor='k')

        ax.semilogx(freq[freq != 0] / 1e9, 10 * np.log10(psd[freq != 0]), '-o', lw=2, color='#00aa00', label=label)
        ax.legend(loc='best', fontsize=12)  # upper right, upper left, lower right, lower left
        ax.set_xlabel('Frequency [GHz]', fontsize=15)
        ax.set_ylabel('PSD [dB]', fontsize=15)
        # ax.set_xlim(1e-3, 2e1)
        # ax.set_ylim(-80, 0)

        ax.minorticks_on()
        ax.grid(visible=True, which='major', color='k', linestyle=':')
        ax.grid(visible=True, which='minor', color='k', linestyle=':', alpha=0.3)

        fig.tight_layout()
        # fig.savefig('freq_psd.png')
        plt.show(block=False)

        # DC (psd[0]) を除いた平均値を標準出力
        if verbose:
            psd_ave: float = 10 * np.log10(np.sum(psd[1:]) / len(psd[1:]))
            print(f"PSD (one-sided) Average of Fig.{fig_num} = {psd_ave: .3f} [dB]")

    def plot_spectrum_compare(
            self,
            freq1: np.ndarray,
            psd1: np.ndarray,
            label1: str,
            freq2: np.ndarray,
            psd2: np.ndarray,
            label2: str,
            fig_num: int = 2
    ) -> None:
        """
        freq vs psdを２つsemilogxで重ね描きする

        Parameters
        ----------
        freq1 : np.ndarray
            周波数アレイ1
        psd1 : np.ndarray
            PSDアレイ1 [V**2/Hz]
        label1 : str
            プロットに対するラベル1
        freq2 : np.ndarray
            周波数アレイ2
        psd2 : np.ndarray
            PSDアレイ2 [V**2/Hz]
        label2 : str
            プロットに対するラベル2
        fig_num : int
            Matplotlibのfigureオブジェクト番号を指定する
        """
        if plt.fignum_exists(fig_num):
            fig = plt.figure(fig_num)  # num==1のfigureオブジェクトを取得
            fig.canvas.draw_idle()  # 明示的に再描画を強制
            fig.clear()  # これでAxesオブジェクトとプロットのオブジェクトも削除される
            ax = fig.subplots(nrows=1, ncols=1)
        else:
            fig, ax = plt.subplots(nrows=1, ncols=1, num=fig_num, figsize=(8, 6), dpi=100, facecolor='w', edgecolor='k')

        ax.semilogx(freq1[freq1 != 0] / 1e9, 10 * np.log10(psd1[freq1 != 0]),
                    '-o', lw=2, label=label1)
        ax.semilogx(freq2[freq2 != 0] / 1e9, 10 * np.log10(psd2[freq2 != 0]),
                    '-', lw=2, label=label2)
        ax.legend(loc='best', fontsize=12)  # upper right, upper left, lower right, lower left
        ax.set_xlabel('Frequency [GHz]', fontsize=15)
        ax.set_ylabel('PSD (one-sided) [dB]', fontsize=15)

        ax.minorticks_on()
        ax.grid(visible=True, which='major', color='k', linestyle=':')
        ax.grid(visible=True, which='minor', color='k', linestyle=':', alpha=0.3)

        fig.tight_layout()
        # fig.savefig('freq_psd_compare.png')
        plt.show(block=False)

    def get_shaping_gain_mock(self) -> tuple:
        """
        目標となるノイズスペクトルはone-sidedの情報であると想定する．
        多分ノイズスペクトルで0Hzのデータはないことが多いはずなので，
        ここで生成するMockのノイズスペクトルもそのように用意する．

        scipy.fft.fft戻り値の複素振幅[V]に対してshapingするから，two-sided ゲインの次元で返す．
        (ゲインの２条ではないことに注意)

        Returns
        -------
        freq_2 : np.ndarray
            ターゲットのノイズスペクトルの周波数アレイ [Hz] (two-sided)
        shaping_gain_2 : np.ndarray
            ターゲットのノイズスペクトルアレイ [V**2/Hz] (two-sided)
        freq_target : np.ndarray
            ターゲットのノイズスペクトルの周波数アレイ [Hz] (one-sided)
        psd_target : np.ndarray
            ターゲットのノイズスペクトルアレイ [V**2/Hz] (one-sided)
        """

        # -freq[-1]からfreq[-1]までのsplineオブジェクトを作ることを目的としてゲインを作る
        # one-sidedのノイズスペクトルが提供される前提として，そのmockの式をたてる
        freq: np.ndarray = np.linspace(1e6, 20e9, 1024 + 1)  # 20e9を含むことに注意
        noise_spectrum: np.ndarray = np.abs(0.1 / (1 + 2j * np.pi * freq / (2 * np.pi * 100e6)))  # one-seide noise spectrum mock

        freq_target: np.ndarray = freq
        psd_target: np.ndarray = noise_spectrum ** 2

        # two-sided化
        # scipy.interpolate.CubicSplineで補完オブジェクトを生成するので，
        # 周波数アレイはscipy.fft.fftfreqの戻り値とは異なった，通常の関数として扱える並びにする．
        freq_2: np.ndarray = np.concatenate([-freq[::-1], freq])

        # 最終的に欲しいノイズスペクトルの絶対値が，White Noiseに対するシェイピングゲインに相当する．
        # ゲインはfreq_2アレイに合わせた並びにする．
        # ゲインの２乗ではなくゲインの次元に対してtwo-sided化なので，0.5倍ではなくnp.sqrt(0.5)倍する．
        shaping_gain_2: np.ndarray = np.sqrt(0.5) * np.concatenate([noise_spectrum[::-1], noise_spectrum])  # two-sided

        return freq_2, shaping_gain_2, freq_target, psd_target

    def save_binary(self, noise, filepath='dpi/shaped_noise.bin'):
        """
        Save noise samples to binary file for DPI-C loading (Method 2).

        Binary Format:
        - Data type: IEEE 754 double precision (float64)
        - Byte order: Native (little-endian on x86/ARM)
        - Size: N samples × 8 bytes/sample
        - No header, just raw double array

        Args:
            noise: Noise samples (numpy array)
            filepath: Output binary file path

        Returns:
            int: Number of bytes written
        """
        # Convert to Path object for easier file size retrieval
        filepath = Path(filepath)

        # Save as binary (IEEE 754 double precision)
        noise.astype(np.float64).tofile(str(filepath))

        # Get file size
        file_size = filepath.stat().st_size

        print(f"      Binary saved: {filepath}")
        print(f"      File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"      Format: IEEE 754 double precision (8 bytes/sample)")

        return file_size


if __name__ == "__main__":
    main()
