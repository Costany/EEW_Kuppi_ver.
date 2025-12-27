============================================================
地震警报语音文件
============================================================

## 使用示例 (在main.py中):

```python
import pygame

class EarthquakeSimulator:
    def __init__(self):
        pygame.mixer.init()
        self.sounds = {
            'eew': pygame.mixer.Sound('assets/audio/eew_warning.mp3'),
            'occurred': pygame.mixer.Sound('assets/audio/earthquake_occurred.mp3'),
        }

    def play_eew_warning(self):
        self.sounds['eew'].play()
```

## 文件列表:

- eew_warning.mp3: 緊急地震速報。強い揺れに警戒してください。
- earthquake_occurred.mp3: 地震が発生しました。
- strong_shaking.mp3: 強い揺れに注意してください。
- tsunami_warning.mp3: 津波警報が発表されました。ただちに避難してください。
- tsunami_advisory.mp3: 津波注意報が発表されました。
- magnitude.mp3: マグニチュード
- intensity_1.mp3: 震度1
- intensity_2.mp3: 震度2
- intensity_3.mp3: 震度3
- intensity_4.mp3: 震度4
- intensity_5lower.mp3: 震度5弱
- intensity_5upper.mp3: 震度5強
- intensity_6lower.mp3: 震度6弱
- intensity_6upper.mp3: 震度6強
- intensity_7.mp3: 震度7
- evacuate.mp3: ただちに避難してください。
- caution.mp3: 警戒してください。
