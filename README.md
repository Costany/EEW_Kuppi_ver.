# EEW_Kuppi-anesewo_ver.

**地震の到達時間シミュレーション** の Python/Pygame 復刻版

原作 1 Scratch プロジェクト: https://scratch.mit.edu/projects/525151751/
原作 2 Turbowarp 強震モニタ風地震シュミレーション v1.10.1 : https://turbowarp.org/1220818872?fps=250&clones=Infinity&offscreen&hqpen

使用 Geojson： https://github.com/0Quake/JMA_Region/tree/main

## 概要

日本における地震波（P 波・S 波）の伝播をリアルタイムでシミュレーションし、JMA（気象庁）震度階級を可視化するインタラクティブなシミュレーターです。

## 機能

- P 波・S 波の伝播アニメーション
- JMA 震度計算（距離減衰式）
- 震央地名の自動判定
- 站点モード / 区域モード切替
- マウスホイールによる地図ズーム
- 震度に応じた色分け表示

## 操作方法

- **左クリック**: 震央を設置
- **←→**: マグニチュード調整
- **↑↓**: 深度調整
- **Enter**: シミュレーション開始
- **Space**: 一時停止/再開
- **R**: リセット
- **T**: 表示モード切替（站点/区域）
- **+/-**: 再生速度調整
- **マウスホイール**: 地図ズーム

## インストール

```bash
cd earthquake_sim
pip install -r requirements.txt
python main.py
```

## 必要なライブラリ

- pygame
- cairosvg

## ライセンス

MIT License
