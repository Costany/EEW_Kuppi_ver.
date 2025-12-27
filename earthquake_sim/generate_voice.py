#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成日语地震警报语音文件
使用Google Text-to-Speech (gTTS)
"""
from gtts import gTTS
import os

# 日本地震警报常用语音
earthquake_texts = {
    'eew_warning': '緊急地震速報。強い揺れに警戒してください。',  # EEW警报
    'earthquake_occurred': '地震が発生しました。',  # 地震发生
    'strong_shaking': '強い揺れに注意してください。',  # 强烈摇晃注意
    'tsunami_warning': '津波警報が発表されました。ただちに避難してください。',  # 海啸警报
    'tsunami_advisory': '津波注意報が発表されました。',  # 海啸注意报
    'magnitude': 'マグニチュード',  # 震级
    'intensity_1': '震度1',
    'intensity_2': '震度2',
    'intensity_3': '震度3',
    'intensity_4': '震度4',
    'intensity_5lower': '震度5弱',  # 震度5弱
    'intensity_5upper': '震度5強',  # 震度5强
    'intensity_6lower': '震度6弱',
    'intensity_6upper': '震度6強',
    'intensity_7': '震度7',
    'evacuate': 'ただちに避難してください。',  # 立即避难
    'caution': '警戒してください。',  # 警戒
}

def generate_voices(output_dir='assets/audio'):
    """生成所有日语语音文件"""

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("正在生成日语地震警报语音文件...")
    print("=" * 60)
    print()

    success_count = 0
    failed_count = 0

    for name, text in earthquake_texts.items():
        output_file = os.path.join(output_dir, f'{name}.mp3')

        try:
            # 使用gTTS生成日语语音
            print(f"生成中: {name}.mp3")
            print(f"  文本: {text}")

            tts = gTTS(text=text, lang='ja', slow=False)
            tts.save(output_file)

            # 获取文件大小
            size_kb = os.path.getsize(output_file) / 1024

            print(f"  [OK] 成功! ({size_kb:.1f} KB)")
            print()

            success_count += 1

        except Exception as e:
            print(f"  [FAIL] 失败: {e}")
            print()
            failed_count += 1

    # 生成使用说明
    readme_file = os.path.join(output_dir, 'README.txt')
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("地震警报语音文件\n")
        f.write("=" * 60 + "\n\n")

        f.write("## 使用示例 (在main.py中):\n\n")
        f.write("```python\n")
        f.write("import pygame\n\n")
        f.write("class EarthquakeSimulator:\n")
        f.write("    def __init__(self):\n")
        f.write("        pygame.mixer.init()\n")
        f.write("        self.sounds = {\n")
        f.write("            'eew': pygame.mixer.Sound('assets/audio/eew_warning.mp3'),\n")
        f.write("            'occurred': pygame.mixer.Sound('assets/audio/earthquake_occurred.mp3'),\n")
        f.write("        }\n\n")
        f.write("    def play_eew_warning(self):\n")
        f.write("        self.sounds['eew'].play()\n")
        f.write("```\n\n")

        f.write("## 文件列表:\n\n")
        for name, text in earthquake_texts.items():
            f.write(f"- {name}.mp3: {text}\n")

    # 打印总结
    print("=" * 60)
    print("生成完成!")
    print("=" * 60)
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    print()
    print("使用说明已保存到: README.txt")
    print("=" * 60)

if __name__ == '__main__':
    generate_voices()
