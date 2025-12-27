#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态语音播报系统 - 模仿Scratch text2speech
支持拼接震央、县名、震级等动态信息
"""
from gtts import gTTS
import pygame
import tempfile
import os
import time

class DynamicVoiceAnnouncer:
    """
    动态语音播报系统
    模仿Scratch的text2speech扩展，可以实时合成任意文本
    """

    def __init__(self, cache_dir='assets/audio/cache'):
        """
        初始化语音播报器

        Args:
            cache_dir: 缓存目录，用于存储生成的临时音频
        """
        pygame.mixer.init()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # 缓存：避免重复生成相同内容
        self.speech_cache = {}

        print("[语音系统] 初始化完成")

    def speak(self, text, lang='ja', wait=True):
        """
        动态合成并播放语音

        Args:
            text: 要播报的文本（支持动态拼接）
            lang: 语言 ('ja'=日语, 'zh-cn'=中文)
            wait: 是否等待播放完成

        Returns:
            bool: 是否成功播放
        """
        if not text or len(text.strip()) == 0:
            return False

        try:
            # 检查缓存
            cache_key = f"{lang}_{text}"

            if cache_key in self.speech_cache:
                audio_file = self.speech_cache[cache_key]
                print(f"[语音] 使用缓存: {text[:30]}...")
            else:
                # 生成新的语音
                print(f"[语音] 生成中: {text}")

                # 创建临时文件
                temp_file = os.path.join(
                    self.cache_dir,
                    f"speech_{int(time.time() * 1000)}.mp3"
                )

                # 使用gTTS生成
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(temp_file)

                # 添加到缓存
                self.speech_cache[cache_key] = temp_file
                audio_file = temp_file

            # 播放
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            # 等待播放完成
            if wait:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

            return True

        except Exception as e:
            print(f"[语音] 错误: {e}")
            return False

    def announce_earthquake(self, magnitude, region, depth, intensity=None):
        """
        播报地震信息（完整版）

        Example:
            announce_earthquake(7.2, "宮城県沖", 10, intensity=6)
            -> "緊急地震速報。宮城県沖で地震が発生しました。
                マグニチュード7.2、深さ10キロメートル。震度6強。"
        """
        # 第一部分：警报
        self.speak("緊急地震速報。")
        pygame.time.wait(500)  # 短暂停顿

        # 第二部分：震央和基本信息
        text = f"{region}で地震が発生しました。"
        text += f"マグニチュード{magnitude:.1f}、"
        text += f"深さ{depth}キロメートル。"

        if intensity:
            intensity_text = self._format_intensity(intensity)
            text += f"{intensity_text}。"

        self.speak(text)

    def announce_eew_simple(self, region):
        """
        简短EEW播报

        Example:
            announce_eew_simple("千葉県東方沖")
            -> "緊急地震速報。千葉県東方沖。強い揺れに警戒してください。"
        """
        text = f"緊急地震速報。{region}。強い揺れに警戒してください。"
        self.speak(text)

    def announce_region_intensity(self, region, intensity):
        """
        播报特定地区的震度

        Example:
            announce_region_intensity("東京都", 5)
            -> "東京都、震度5強。"
        """
        intensity_text = self._format_intensity(intensity)
        text = f"{region}、{intensity_text}。"
        self.speak(text, wait=False)  # 不等待，可以连续播报多个地区

    def announce_tsunami_warning(self, regions, height_category):
        """
        播报海啸警报

        Args:
            regions: 警报地区列表，如 ["岩手県", "宮城県", "福島県"]
            height_category: 高度类别 'major'/'warning'/'advisory'
        """
        if height_category == 'major':
            warning_type = "大津波警報"
            action = "ただちに高台に避難してください"
        elif height_category == 'warning':
            warning_type = "津波警報"
            action = "海岸から離れてください"
        else:
            warning_type = "津波注意報"
            action = "海に入らないでください"

        # 拼接地区
        region_text = "、".join(regions)

        text = f"{warning_type}が発表されました。{region_text}。{action}。"
        self.speak(text)

    def _format_intensity(self, intensity):
        """
        格式化震度

        Args:
            intensity: 震度值 (1-7, 支持小数如5.5)

        Returns:
            str: 格式化的震度文本
        """
        intensity_map = {
            1: "震度1",
            2: "震度2",
            3: "震度3",
            4: "震度4",
            5.0: "震度5弱",  # 5-
            5.5: "震度5強",  # 5+
            6.0: "震度6弱",  # 6-
            6.5: "震度6強",  # 6+
            7: "震度7",
        }

        # 查找最接近的震度
        if intensity in intensity_map:
            return intensity_map[intensity]
        elif intensity >= 5 and intensity < 5.5:
            return "震度5弱"
        elif intensity >= 5.5 and intensity < 6:
            return "震度5強"
        elif intensity >= 6 and intensity < 6.5:
            return "震度6弱"
        elif intensity >= 6.5 and intensity < 7:
            return "震度6強"
        elif intensity >= 7:
            return "震度7"
        else:
            return f"震度{int(intensity)}"

    def clear_cache(self):
        """清理缓存的音频文件"""
        count = 0
        for filename in os.listdir(self.cache_dir):
            if filename.startswith('speech_') and filename.endswith('.mp3'):
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                    count += 1
                except:
                    pass

        self.speech_cache.clear()
        print(f"[语音] 已清理 {count} 个缓存文件")


# ============================================================================
# 测试示例
# ============================================================================

def test_dynamic_voice():
    """测试动态语音播报"""

    print("=" * 70)
    print("动态语音播报测试")
    print("=" * 70)

    voice = DynamicVoiceAnnouncer()

    # 测试1: 完整地震播报
    print("\n[测试1] 完整地震播报")
    voice.announce_earthquake(
        magnitude=7.3,
        region="宮城県沖",
        depth=10,
        intensity=6.5  # 震度6強
    )

    pygame.time.wait(2000)

    # 测试2: 简短EEW
    print("\n[测试2] 简短EEW警报")
    voice.announce_eew_simple("千葉県東方沖")

    pygame.time.wait(2000)

    # 测试3: 多地区震度播报
    print("\n[测试3] 多地区震度播报")
    regions_intensities = [
        ("東京都", 5.5),
        ("埼玉県", 5.0),
        ("神奈川県", 5.5),
    ]

    for region, intensity in regions_intensities:
        voice.announce_region_intensity(region, intensity)
        pygame.time.wait(1500)

    # 测试4: 海啸警报
    print("\n[测试4] 海啸警报")
    voice.announce_tsunami_warning(
        regions=["岩手県", "宮城県", "福島県"],
        height_category='major'
    )

    pygame.time.wait(2000)

    # 测试5: 动态拼接任意文本
    print("\n[测试5] 自定义文本")
    custom_text = "北海道で震度7を観測しました。余震に注意してください。"
    voice.speak(custom_text)

    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)


# ============================================================================
# 在main.py中的集成示例
# ============================================================================

def integration_example():
    """
    展示如何在earthquake_sim/main.py中集成
    """

    print("""
# ========== 在 earthquake_sim/main.py 中集成 ==========

from dynamic_voice import DynamicVoiceAnnouncer

class EarthquakeSimulator:
    def __init__(self):
        # ... 现有初始化代码 ...

        # 添加动态语音
        self.voice = DynamicVoiceAnnouncer()

    def handle_enter_key(self):
        \"\"\"按Enter开始模拟\"\"\"
        # 获取震央地名
        epicenter_region = self.epicenter_locator.get_region_name(
            self.earthquake.epicenter_lat,
            self.earthquake.epicenter_lon
        )

        # 动态播报
        self.voice.announce_earthquake(
            magnitude=self.earthquake.magnitude,
            region=epicenter_region,  # 这里是动态的！
            depth=self.earthquake.depth
        )

        self.running = True

    def update(self, dt):
        # ... 现有更新代码 ...

        # 当某地区达到震度5以上时播报
        if station.intensity >= 5 and not station.announced:
            self.voice.announce_region_intensity(
                region=station.prefecture,  # 动态县名
                intensity=station.intensity
            )
            station.announced = True

# ========================================================
    """)


if __name__ == '__main__':
    # 运行测试
    test_dynamic_voice()

    # 显示集成示例
    # integration_example()
