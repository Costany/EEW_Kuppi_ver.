#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能语音缓存系统 - 预录+按需生成
从GeoJSON提取震央地名，预先生成语音文件
运行时优先使用缓存，缺失时才调用API
"""
import json
import os
from gtts import gTTS
import pygame
from pathlib import Path

class SmartVoiceCache:
    """
    智能语音缓存系统

    策略：
    1. 预先从GeoJSON提取所有震央地名
    2. 批量生成常用地名的语音文件
    3. 运行时优先使用缓存
    4. 缺失时才调用gTTS API并保存
    5. 最终枚举完所有地名，实现完全离线
    """

    def __init__(self, voice_dir='assets/audio/regions', geojson_path=None):
        """
        初始化智能语音缓存

        Args:
            voice_dir: 语音文件存储目录
            geojson_path: 震央地名GeoJSON文件路径
        """
        self.voice_dir = Path(voice_dir)
        self.voice_dir.mkdir(parents=True, exist_ok=True)

        # 元数据文件：记录已生成的地名
        self.metadata_file = self.voice_dir / 'voice_metadata.json'
        self.metadata = self._load_metadata()

        # 从GeoJSON提取地名
        self.geojson_path = geojson_path or 'JMA_Region-main/震央地名.geojson'
        self.all_region_names = self._extract_region_names()

        pygame.mixer.init()

        print(f"[语音缓存] 初始化完成")
        print(f"[语音缓存] 发现 {len(self.all_region_names)} 个震央地名")
        print(f"[语音缓存] 已缓存 {len(self.metadata)} 个语音文件")

    def _load_metadata(self):
        """加载元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def _extract_region_names(self):
        """从GeoJSON提取所有震央地名"""
        if not os.path.exists(self.geojson_path):
            print(f"[警告] 未找到GeoJSON文件: {self.geojson_path}")
            return set()

        try:
            with open(self.geojson_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)

            region_names = set()
            for feature in geojson.get('features', []):
                name = feature.get('properties', {}).get('Name')
                if name:
                    region_names.add(name)

            return region_names

        except Exception as e:
            print(f"[错误] 解析GeoJSON失败: {e}")
            return set()

    def _sanitize_filename(self, text):
        """将文本转换为安全的文件名"""
        # 移除非法字符
        safe_name = text.replace('/', '_').replace('\\', '_')
        safe_name = safe_name.replace(':', '_').replace('*', '_')
        safe_name = safe_name.replace('?', '_').replace('"', '_')
        safe_name = safe_name.replace('<', '_').replace('>', '_')
        safe_name = safe_name.replace('|', '_')
        return safe_name

    def get_voice_file(self, region_name):
        """
        获取地名的语音文件路径（智能缓存）

        Args:
            region_name: 震央地名，如 "宮城県沖"

        Returns:
            str: 语音文件路径，如果不存在则返回None
        """
        safe_name = self._sanitize_filename(region_name)
        voice_file = self.voice_dir / f"{safe_name}.mp3"

        # 检查缓存
        if voice_file.exists():
            return str(voice_file)

        # 缓存未命中，生成新文件
        print(f"[语音缓存] 缺失: {region_name}，正在生成...")

        try:
            tts = gTTS(text=region_name, lang='ja', slow=False)
            tts.save(str(voice_file))

            # 更新元数据
            self.metadata[region_name] = {
                'filename': f"{safe_name}.mp3",
                'generated': True
            }
            self._save_metadata()

            print(f"[语音缓存] 已生成: {region_name}")
            return str(voice_file)

        except Exception as e:
            print(f"[语音缓存] 生成失败: {e}")
            return None

    def speak_region(self, region_name, wait=True):
        """
        播报震央地名

        Args:
            region_name: 震央地名
            wait: 是否等待播放完成
        """
        voice_file = self.get_voice_file(region_name)

        if voice_file:
            pygame.mixer.music.load(voice_file)
            pygame.mixer.music.play()

            if wait:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

            return True

        return False

    def pregenerate_all_regions(self):
        """
        预先生成所有震央地名的语音
        这个可以在后台慢慢跑，跑完就有完整的离线库了
        """
        print("=" * 70)
        print("开始预生成所有震央地名语音")
        print("=" * 70)
        print(f"总数: {len(self.all_region_names)} 个")
        print()

        already_exists = 0
        newly_generated = 0
        failed = 0

        for idx, region_name in enumerate(sorted(self.all_region_names), 1):
            safe_name = self._sanitize_filename(region_name)
            voice_file = self.voice_dir / f"{safe_name}.mp3"

            # 跳过已存在的
            if voice_file.exists():
                already_exists += 1
                print(f"[{idx}/{len(self.all_region_names)}] 已存在: {region_name}")
                continue

            # 生成新的
            try:
                print(f"[{idx}/{len(self.all_region_names)}] 生成中: {region_name}")
                tts = gTTS(text=region_name, lang='ja', slow=False)
                tts.save(str(voice_file))

                # 更新元数据
                self.metadata[region_name] = {
                    'filename': f"{safe_name}.mp3",
                    'generated': True
                }

                newly_generated += 1

            except Exception as e:
                print(f"[{idx}/{len(self.all_region_names)}] 失败: {region_name} - {e}")
                failed += 1

        # 保存元数据
        self._save_metadata()

        print()
        print("=" * 70)
        print("预生成完成！")
        print("=" * 70)
        print(f"已存在: {already_exists} 个")
        print(f"新生成: {newly_generated} 个")
        print(f"失败: {failed} 个")
        print(f"总计: {already_exists + newly_generated} / {len(self.all_region_names)}")
        print()
        print(f"所有文件保存在: {self.voice_dir.absolute()}")
        print("现在可以完全离线使用了！")
        print("=" * 70)

    def pregenerate_common_regions(self):
        """
        只预生成常用的震央地名
        包括：所有包含"県"、"沖"、"海域"的地名
        """
        common_keywords = ['県', '沖', '海域', '半島', '湾', '灘']

        common_regions = [
            name for name in self.all_region_names
            if any(keyword in name for keyword in common_keywords)
        ]

        print("=" * 70)
        print("预生成常用震央地名")
        print("=" * 70)
        print(f"筛选出 {len(common_regions)} 个常用地名")
        print()

        for idx, region_name in enumerate(sorted(common_regions), 1):
            safe_name = self._sanitize_filename(region_name)
            voice_file = self.voice_dir / f"{safe_name}.mp3"

            if voice_file.exists():
                print(f"[{idx}/{len(common_regions)}] 已存在: {region_name}")
                continue

            try:
                print(f"[{idx}/{len(common_regions)}] 生成: {region_name}")
                tts = gTTS(text=region_name, lang='ja', slow=False)
                tts.save(str(voice_file))

                self.metadata[region_name] = {
                    'filename': f"{safe_name}.mp3",
                    'generated': True
                }

            except Exception as e:
                print(f"失败: {e}")

        self._save_metadata()
        print("\n常用地名生成完成！")

    def generate_composite_announcement(self, region, magnitude, depth):
        """
        生成组合播报（使用预录片段）

        例如：
        - "宮城県沖" (预录)
        - "で地震が発生しました。マグニチュード7.3" (预录)

        Returns:
            list: 音频文件路径列表，按顺序播放
        """
        audio_files = []

        # 1. 震央地名
        region_file = self.get_voice_file(region)
        if region_file:
            audio_files.append(region_file)

        # 2. "で地震が発生しました"
        occurred_file = self.get_voice_file("で地震が発生しました")
        if occurred_file:
            audio_files.append(occurred_file)

        # 3. 震级部分（可以预录M6.0-M8.0的常用值）
        mag_text = f"マグニチュード{magnitude:.1f}"
        mag_file = self.get_voice_file(mag_text)
        if mag_file:
            audio_files.append(mag_file)

        return audio_files

    def get_cache_stats(self):
        """获取缓存统计信息"""
        total = len(self.all_region_names)
        cached = len([f for f in self.voice_dir.glob('*.mp3')])

        coverage = (cached / total * 100) if total > 0 else 0

        return {
            'total_regions': total,
            'cached_files': cached,
            'coverage': coverage,
            'metadata_entries': len(self.metadata)
        }


# ============================================================================
# 使用示例
# ============================================================================

def example_usage():
    """演示如何使用智能缓存系统"""

    # 初始化
    voice_cache = SmartVoiceCache(
        voice_dir='earthquake_sim/assets/audio/regions',
        geojson_path='JMA_Region-main/震央地名.geojson'
    )

    # 查看缓存状态
    stats = voice_cache.get_cache_stats()
    print(f"\n缓存覆盖率: {stats['coverage']:.1f}% ({stats['cached_files']}/{stats['total_regions']})")

    # 测试播报几个震央
    test_regions = ["宮城県沖", "千葉県東方沖", "北海道南西沖"]

    print("\n测试播报震央地名:")
    for region in test_regions:
        print(f"  播报: {region}")
        voice_cache.speak_region(region)
        pygame.time.wait(1000)

    # 再次查看缓存状态
    stats = voice_cache.get_cache_stats()
    print(f"\n更新后覆盖率: {stats['coverage']:.1f}%")


def pregenerate_main():
    """预生成所有地名（可以单独运行）"""

    voice_cache = SmartVoiceCache(
        voice_dir='earthquake_sim/assets/audio/regions',
        geojson_path='JMA_Region-main/震央地名.geojson'
    )

    # 选择：
    # 1. 只生成常用的（快速）
    voice_cache.pregenerate_common_regions()

    # 2. 生成全部（慢但完整，可以后台跑）
    # voice_cache.pregenerate_all_regions()


if __name__ == '__main__':
    # 测试使用
    example_usage()

    # 如果想预生成，取消下面的注释
    # pregenerate_main()
