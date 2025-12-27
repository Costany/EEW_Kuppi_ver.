#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频管理器 - 管理Scratch项目的预录音频
支持EEW警报音、震度播报等预录制的高质量音频
"""
import pygame
import os
from pathlib import Path

class SoundManager:
    """
    音频管理器 - 播放预录制音频
    
    从 強震モニタ風地震シュミレーション v1.10 提取的音频文件
    """
    
    def __init__(self, audio_dir='assets/audio'):
        """
        初始化音频管理器
        
        Args:
            audio_dir: 音频文件目录（相对于earthquake_sim/）
        """
        # 初始化pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        
        # 音频目录路径
        base_dir = Path(__file__).parent
        self.audio_dir = base_dir / audio_dir
        
        # 音频字典
        self.sounds = {}
        
        # 音频文件映射（MD5文件名 -> 功能名）
        self.audio_files = {
            # EEW警报音
            'eew': '697cbc9cfa2c83151f4d7d4ce5ffebe7.wav',
            
            # 播音员语音
            'warning': '5fac8e1afab5aa7f0c4597fef164fd10.mp3',  # 警報
            'emergency_alert': '159244e8557e16cb7a8a88386ac566b6.mp3',  # 緊急地震速報
            'tsunami': 'a9c826ea89ac2745d409a775b8fb8c99.mp3',  # 津波
            'correction': '1e79cf503994fbc4b07e6807d98402e5.mp3',  # 訂正
            'major_wave_warning': '3943b1a91e99f2558a3325ccb39ba22d.mp3',  # 主要動警報
            'forecast_warning': '7c9101278fbdb29bd4898a97e572ddd0.mp3',  # 予報警報
            'strong_shaking': 'd62b399771370726d752255c0a040dd3.mp3',  # 強い揺れ
            'caution': 'ca1a590531afaf99ced3e6fff476fbf8.mp3',  # 注意報
            'arrived': '1dce89e5d43f35a046185486de4faef5.mp3',  # 到達しました
            'tsunami_warning': '20ba4384644a9e9b98f675538863773b.mp3',  # 海啸预警
            'epicenter_info': 'a5aedae453531d5eb52c0b19940f3769.mp3',  # 震源情報
            'chime': 'de4a2891767d3ef4567355631d943700.wav',  # チャイムセンサー
            
            # 震度播报 0-6
            # 注意: 震度0-2虽然有音频文件，但实际播报从震度3开始
            # 震度0时长仅1秒，可能是占位符；震度1-2在真实系统中通常不播报
            'intensity_0': 'efebee98aaeb5710c6c52c0f1bcb318c.wav',  # 1.00秒 (占位)
            'intensity_1': 'ff87f6103b04410f0e35ccad1c86e46f.wav',  # 2.40秒 (不常用)
            'intensity_2': '55d2175d7def4fce369b5d2b3f07dccd.wav',  # 2.40秒 (不常用)
            'intensity_3': 'f821efe2e15d6b7e9258a5a1b2d79bf3.wav',  # 2.40秒 ← 实际播报从这里开始
            'intensity_4': '9d32fb3d8f053f9d38af9b4125d238bf.wav',  # 2.40秒
            'intensity_5': 'f0eccaf0dae87cb74f9bd27d27e3c5f1.wav',  # 2.60秒 (可能是"震度5強")
            'intensity_6': '43c1927b88049e83cb01670fc0dfcfed.wav',  # 2.60秒 (可能是"震度6強")
        }
        
        # 加载音频
        self.load_sounds()
        
        # 播放状态追踪
        self.last_announced_intensity = -1
        self.announcement_cooldown = 0  # 播报冷却时间（秒）
        
        print(f"[音频管理器] 初始化完成，加载了 {len(self.sounds)} 个音频")
    
    def load_sounds(self):
        """加载所有音频文件"""
        loaded_count = 0
        failed_files = []
        
        for name, filename in self.audio_files.items():
            audio_path = self.audio_dir / filename
            
            if audio_path.exists():
                try:
                    self.sounds[name] = pygame.mixer.Sound(str(audio_path))
                    loaded_count += 1
                except Exception as e:
                    failed_files.append(f"{filename} ({e})")
            else:
                failed_files.append(f"{filename} (文件不存在)")
        
        if failed_files:
            print(f"[音频管理器] 加载失败的文件: {', '.join(failed_files[:3])}")
        
        print(f"[音频管理器] 成功加载 {loaded_count}/{len(self.audio_files)} 个音频")
    
    def play(self, sound_name, volume=1.0):
        """
        播放指定音频
        
        Args:
            sound_name: 音频名称（见audio_files字典）
            volume: 音量 (0.0-1.0)
        
        Returns:
            bool: 是否成功播放
        """
        if sound_name in self.sounds:
            try:
                sound = self.sounds[sound_name]
                sound.set_volume(volume)
                sound.play()
                return True
            except Exception as e:
                print(f"[音频管理器] 播放失败 {sound_name}: {e}")
                return False
        else:
            print(f"[音频管理器] 音频不存在: {sound_name}")
            return False
    
    def stop_all(self):
        """停止所有音频"""
        pygame.mixer.stop()
    
    # ========== 快捷播放方法 ==========
    
    def play_eew(self):
        """播放EEW警报音"""
        return self.play('eew', volume=0.8)
    
    def play_emergency_alert(self):
        """播放"緊急地震速報"语音"""
        return self.play('emergency_alert', volume=0.9)
    
    def play_intensity(self, intensity):
        """
        播报震度等级
        
        Args:
            intensity: 震度值 (0-7)
        
        Returns:
            bool: 是否成功播放
        """
        # JMA震度等级转换
        if intensity < 0:
            intensity = 0
        elif intensity > 7:
            intensity = 7
        
        # 震度5+, 6+, 7 映射到 5, 6
        if intensity >= 7:
            sound_name = 'intensity_6'  # 震度7也用震度6的音频
        elif intensity >= 6.5:
            sound_name = 'intensity_6'  # 震度6強
        elif intensity >= 5.5:
            sound_name = 'intensity_5'  # 震度5強
        else:
            intensity_level = int(intensity)
            if intensity_level > 6:
                intensity_level = 6
            sound_name = f'intensity_{intensity_level}'
        
        return self.play(sound_name, volume=0.9)
    
    def play_chime(self):
        """播放警铃音"""
        return self.play('chime', volume=0.7)
    
    def play_strong_shaking_warning(self):
        """播放"強い揺れ"警告"""
        return self.play('strong_shaking', volume=0.9)
    
    def play_tsunami_warning(self):
        """播放海啸警报"""
        return self.play('tsunami_warning', volume=0.9)
    
    def announce_with_cooldown(self, intensity, cooldown_seconds=5.0):
        """
        带冷却时间的震度播报（避免频繁播报）
        
        Args:
            intensity: 当前震度
            cooldown_seconds: 冷却时间（秒）
        
        Returns:
            bool: 是否播报了
        """
        import time
        
        current_time = time.time()
        
        # 检查冷却时间
        if current_time - self.announcement_cooldown < cooldown_seconds:
            return False
        
        # 检查是否需要更新播报（震度增加）
        intensity_int = int(intensity)
        if intensity_int > self.last_announced_intensity:
            success = self.play_intensity(intensity)
            if success:
                self.last_announced_intensity = intensity_int
                self.announcement_cooldown = current_time
            return success
        
        return False
    
    def reset_announcement(self):
        """重置播报状态（用于新地震）"""
        self.last_announced_intensity = -1
        self.announcement_cooldown = 0


# ============================================================================
# 测试代码
# ============================================================================

def test_sound_manager():
    """测试音频管理器"""
    import time
    
    print("=" * 70)
    print("音频管理器测试")
    print("=" * 70)
    
    # 初始化pygame
    pygame.init()
    
    manager = SoundManager()
    
    print("\n[测试1] 播放EEW警报音")
    manager.play_eew()
    time.sleep(2)
    
    print("\n[测试2] 播放緊急地震速報")
    manager.play_emergency_alert()
    time.sleep(4)
    
    print("\n[测试3] 播报震度0-6")
    for i in range(7):
        print(f"  播报震度{i}")
        manager.play_intensity(i)
        time.sleep(3)
    
    print("\n[测试4] 播放警铃")
    manager.play_chime()
    time.sleep(2)
    
    print("\n[测试5] 播放強い揺れ警告")
    manager.play_strong_shaking_warning()
    time.sleep(3)
    
    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)


if __name__ == '__main__':
    test_sound_manager()
