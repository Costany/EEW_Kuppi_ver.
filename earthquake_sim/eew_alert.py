"""EEW（紧急地震速报）警报框"""

import pygame
from typing import Optional

class EEWAlert:
    """EEW警报框 UI"""
    def __init__(self):
        # 字体
        self.large_font = pygame.font.Font(None, 48)
        self.medium_font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 28)
        self.tiny_font = pygame.font.Font(None, 20)

        # 位置和大小
        self.x = 10
        self.y = 10
        self.width = 580
        self.height = 180

        # 状态
        self.visible = False
        self.flash_timer = 0  # 闪烁计时器

    def update(self, earthquake, station_manager, dt: float):
        """更新警报框状态"""
        # 检查是否有站点达到震度1以上
        max_intensity = max([s.intensity for s in station_manager.stations], default=-3)

        if max_intensity >= 1:
            self.visible = True
            self.flash_timer += dt
        else:
            self.visible = False
            self.flash_timer = 0

    def render(self, screen: pygame.Surface, earthquake, epicenter_locator):
        """渲染警报框"""
        if not self.visible:
            return

        # 获取震源地名
        epicenter_name = epicenter_locator.get_location_name(
            earthquake.lon,
            earthquake.lat,
            'zh'
        )

        # 计算预估最大震度
        estimated_intensity = earthquake.magnitude  # 简化计算

        # 背景：红色警报框
        pygame.draw.rect(screen, (200, 0, 0), (self.x, self.y, self.width, self.height))
        pygame.draw.rect(screen, (255, 255, 255), (self.x, self.y, self.width, self.height), 3)

        # 标题文字：緊急地震速報(警報)
        title_text = "緊急地震速報(警報)"
        title_surface = self.small_font.render(title_text, True, (255, 255, 255))
        screen.blit(title_surface, (self.x + 10, self.y + 5))

        # 震度和地名行
        intensity_level = self._get_intensity_level(estimated_intensity)

        # 推定震度
        intensity_label = "推定"
        intensity_label_surface = self.tiny_font.render(intensity_label, True, (200, 200, 200))
        screen.blit(intensity_label_surface, (self.x + 10, self.y + 40))

        intensity_label2 = "震度"
        intensity_label2_surface = self.tiny_font.render(intensity_label2, True, (200, 200, 200))
        screen.blit(intensity_label2_surface, (self.x + 10, self.y + 60))

        # 震度数字（大号）
        intensity_text = self._get_intensity_text(estimated_intensity)
        intensity_color = self._get_intensity_color(estimated_intensity)

        # 震度背景框
        pygame.draw.rect(screen, intensity_color, (self.x + 60, self.y + 35, 60, 70))
        intensity_surface = self.large_font.render(intensity_text, True, (255, 255, 255))
        intensity_rect = intensity_surface.get_rect(center=(self.x + 90, self.y + 70))
        screen.blit(intensity_surface, intensity_rect)

        # 震源地名（橙色背景）
        pygame.draw.rect(screen, (255, 140, 0), (self.x + 130, self.y + 45, 440, 50))
        epicenter_surface = self.medium_font.render(epicenter_name, True, (255, 255, 255))
        screen.blit(epicenter_surface, (self.x + 140, self.y + 55))

        # M和深度行
        mag_depth_y = self.y + 120

        # M8.1  200km
        mag_text = f"M{earthquake.magnitude:.1f}  {int(earthquake.depth)}km"
        mag_surface = self.large_font.render(mag_text, True, (255, 255, 255))
        screen.blit(mag_surface, (self.x + 10, mag_depth_y))

        # 推定长周期（如果有的话）
        if earthquake.magnitude >= 7.0:
            period_label = "推定"
            period_label_surface = self.tiny_font.render(period_label, True, (200, 200, 200))
            screen.blit(period_label_surface, (self.x + 10, mag_depth_y + 50))

            period_label2 = "長周期"
            period_label2_surface = self.tiny_font.render(period_label2, True, (200, 200, 200))
            screen.blit(period_label2_surface, (self.x + 10, mag_depth_y + 68))

            period_level = "4"  # 简化
            period_bg_rect = (self.x + 60, mag_depth_y + 50, 50, 40)
            pygame.draw.rect(screen, (150, 0, 150), period_bg_rect)
            period_surface = self.medium_font.render(period_level, True, (255, 255, 255))
            period_rect = period_surface.get_rect(center=(self.x + 85, mag_depth_y + 70))
            screen.blit(period_surface, period_rect)

    def _get_intensity_level(self, magnitude: float) -> int:
        """根据震级估算震度等级"""
        if magnitude < 4.0:
            return 1
        elif magnitude < 5.0:
            return 3
        elif magnitude < 6.0:
            return 4
        elif magnitude < 7.0:
            return 5
        elif magnitude < 7.5:
            return 6
        else:
            return 7

    def _get_intensity_text(self, magnitude: float) -> str:
        """获取震度文本"""
        level = self._get_intensity_level(magnitude)
        if level >= 7:
            return "7"
        elif level >= 6:
            return "6+"
        elif level >= 5:
            return "5+"
        elif level >= 4:
            return "4"
        else:
            return str(level)

    def _get_intensity_color(self, magnitude: float) -> tuple:
        """获取震度背景颜色"""
        level = self._get_intensity_level(magnitude)
        if level >= 7:
            return (150, 0, 150)  # 紫
        elif level >= 6:
            return (200, 0, 100)  # 紫红
        elif level >= 5:
            return (255, 0, 0)    # 红
        elif level >= 4:
            return (255, 140, 0)  # 橙
        else:
            return (255, 200, 0)  # 黄
