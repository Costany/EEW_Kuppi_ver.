"""站点管理和渲染系统"""

import json
import pygame
import math
from typing import List, Tuple, Optional, Dict
from config import *
from intensity import intensity_to_scale

def scale_icon(icon, factor):
    """缩放图标"""
    if icon is None:
        return None
    w, h = icon.get_size()
    new_w = max(1, int(w * factor))
    new_h = max(1, int(h * factor))
    return pygame.transform.smoothscale(icon, (new_w, new_h))

class Station:
    """单个观测站点"""
    def __init__(self, station_id: int, lat: float, lon: float, name: str = ""):
        self.id = station_id
        self.lat = lat
        self.lon = lon
        self.name = name or f"Station_{station_id}"

        # 震度相关
        self.intensity = -3  # 当前震度（-3表示未触发）
        self.target_intensity = -3  # 目标震度
        self.max_intensity = -3  # 最大震度
        self.p_wave_arrived = False
        self.s_wave_arrived = False
        self.time_since_peak = 0  # 达峰后经过时间（秒）

        # P波到达记录（用于实时定位）
        self.p_arrival_time = None  # P波到达时刻（模拟时间）
        self.p_amplitude = 0  # P波振幅（用于震级估算）

    def update(self, earthquake, current_time: float, dt: float):
        """更新站点状态 - 渐进式增长逻辑（Scratch兼容）"""
        # 使用 earthquake 对象的方法计算正确的到达时间（基于震源距离）
        p_arrival_time = earthquake.get_p_arrival_time(self.lat, self.lon)
        s_arrival_time = earthquake.get_s_arrival_time(self.lat, self.lon)

        # 检查波是否到达（记录首次P波到达时刻）
        was_p_arrived = self.p_wave_arrived
        self.p_wave_arrived = current_time >= p_arrival_time
        self.s_wave_arrived = current_time >= s_arrival_time

        # 首次检测到P波时，记录到达时刻（用于实时定位）
        if self.p_wave_arrived and not was_p_arrived:
            self.p_arrival_time = current_time
            # 计算P波振幅（简化：基于震级和距离）
            epicentral_dist = earthquake.get_epicentral_distance(self.lat, self.lon)
            # 振幅公式（简化版）: A = 10^(M-1.5) / D
            if epicentral_dist > 0:
                self.p_amplitude = (10 ** (earthquake.magnitude - 1.5)) / max(1, epicentral_dist)

        # 计算震央距离（用于震度计算）
        epicentral_dist = earthquake.get_epicentral_distance(self.lat, self.lon)

        # 根据波的到达情况计算目标震度
        if self.s_wave_arrived:
            # S波已到达，使用完整震度计算
            from intensity import calc_jma_intensity
            self.target_intensity = calc_jma_intensity(
                earthquake.magnitude,
                earthquake.depth,
                epicentral_dist
            )
        elif self.p_wave_arrived:
            # 只有P波到达，P波震度 = S波震度 / 1.5 - 0.5（Scratch公式）
            from intensity import calc_jma_intensity
            s_intensity = calc_jma_intensity(
                earthquake.magnitude,
                earthquake.depth,
                epicentral_dist
            )
            self.target_intensity = max(-3, s_intensity / 1.5 - 0.5)
        else:
            # 波未到达
            self.target_intensity = -3
            self.intensity = -3
            return

        # 渐进式增长逻辑（Scratch公式，优化版）
        import math
        import random

        # 增量公式：((log(1/I) / log(7) + 1) * Random(...)) * time_scale
        # 震度越低，增量越大（快速上升）
        current_i = max(0.01, self.intensity + 3)  # 避免log(0)
        increment_factor = (math.log(1 / current_i) / math.log(7) + 1)

        # 基础随机因子（确保有最小值）
        base_random = 0.005 + 0.04 / math.log(earthquake.magnitude + 0.2)
        random_factor = random.uniform(base_random * 0.3, base_random)  # 至少30%的基础值

        # P波增量更小（双重随机）
        if self.p_wave_arrived and not self.s_wave_arrived:
            random_factor = random_factor * 0.5  # 减半而非再次随机

        increment = increment_factor * random_factor * dt * 60  # 乘以60加速

        # 保证最小增量（每秒至少增加0.5震度）
        min_increment = 0.5 * dt
        increment = max(increment, min_increment)

        # 应用增量
        if self.intensity + increment < self.target_intensity:
            # 震度未达峰值，逐渐增加
            self.intensity += increment
            self.time_since_peak = 0
        else:
            # 震度已达峰值，停止增长并开始计时
            self.intensity = self.target_intensity
            self.time_since_peak += dt

        # 更新最大震度
        if self.intensity > self.max_intensity:
            self.max_intensity = self.intensity

    def get_intensity_level(self) -> Optional[int]:
        """获取当前震度等级（用于音效触发）
        返回: 0, 1, 2, 3, 4, 5(5弱), 6(6弱), 或 None
        """
        if self.intensity < 0:
            return None
        elif self.intensity < 1:
            return 0
        elif self.intensity < 2:
            return 1
        elif self.intensity < 3:
            return 2
        elif self.intensity < 4:
            return 3
        elif self.intensity < 5:
            return 4
        elif self.intensity < 5.5:
            return 5  # 5弱
        elif self.intensity < 6:
            return None  # 5强不播放
        elif self.intensity < 6.5:
            return 6  # 6弱
        else:
            return None  # 6强和7不播放

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间的距离（km）"""
        R = 6371.0
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def get_color(self) -> Tuple[int, int, int]:
        """获取站点底层圆点颜色（连续渐变色阶）

        使用强震モニタ风格的渐变色阶：
        - 默认（-3）: 深蓝色
        - 随着震度增加，从深蓝→浅蓝→青→绿→黄→橙→红→紫 连续渐变
        """
        intensity = self.intensity

        # 将震度映射到0-1范围（-3到7映射为0到1）
        # -3 -> 0.0, 7 -> 1.0
        t = (intensity + 3) / 10.0
        t = max(0.0, min(1.0, t))  # 钳制到0-1

        # 强震モニタ风格渐变色阶（关键点）
        # t=0.0 (-3): 深蓝 (0, 0, 80)
        # t=0.3 (0):  蓝   (0, 63, 255)
        # t=0.4 (1):  浅蓝 (0, 191, 255)
        # t=0.5 (2):  青   (0, 255, 191)
        # t=0.6 (3):  绿   (0, 255, 0)
        # t=0.7 (4):  黄   (255, 255, 0)
        # t=0.8 (5):  橙   (255, 127, 0)
        # t=0.9 (6):  红   (255, 0, 0)
        # t=1.0 (7):  紫   (200, 0, 200)

        color_stops = [
            (0.0,  (0, 0, 80)),       # 深蓝（默认底色）
            (0.3,  (0, 63, 255)),     # 蓝（震度0）
            (0.4,  (0, 191, 255)),    # 浅蓝（震度1）
            (0.5,  (0, 255, 191)),    # 青（震度2）
            (0.6,  (0, 255, 0)),      # 绿（震度3）
            (0.7,  (255, 255, 0)),    # 黄（震度4）
            (0.8,  (255, 127, 0)),    # 橙（震度5）
            (0.9,  (255, 0, 0)),      # 红（震度6）
            (1.0,  (200, 0, 200)),    # 紫（震度7）
        ]

        # 找到t所在的区间并线性插值
        for i in range(len(color_stops) - 1):
            t0, c0 = color_stops[i]
            t1, c1 = color_stops[i + 1]
            if t0 <= t <= t1:
                # 计算区间内的插值比例
                ratio = (t - t0) / (t1 - t0) if t1 > t0 else 0
                r = int(c0[0] + (c1[0] - c0[0]) * ratio)
                g = int(c0[1] + (c1[1] - c0[1]) * ratio)
                b = int(c0[2] + (c1[2] - c0[2]) * ratio)
                return (r, g, b)

        # 超出范围返回最后一个颜色
        return color_stops[-1][1]

    def get_intensity_text(self) -> str:
        """获取震度文本"""
        intensity = self.intensity
        if intensity < 0:
            return ""
        elif intensity < 1:
            return "0"
        elif intensity < 2:
            return "1"
        elif intensity < 3:
            return "2"
        elif intensity < 4:
            return "3"
        elif intensity < 5:
            return "4"
        elif intensity < 5.5:
            return "5-"
        elif intensity < 6:
            return "5+"
        elif intensity < 6.5:
            return "6-"
        elif intensity < 7:
            return "6+"
        else:
            return "7"


class StationManager:
    """站点管理器"""
    def __init__(self, stations_file: str = "stations_data.json"):
        self.stations: List[Station] = []
        self.load_stations(stations_file)

        # 预渲染字体
        self.font = pygame.font.Font(None, 16)
        self.small_font = pygame.font.Font(None, 14)

    def load_stations(self, filename: str):
        """加载站点数据"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.stations = [
                Station(s['id'], s['lat'], s['lon'], s.get('name', ''))
                for s in data
            ]
            print(f"成功加载 {len(self.stations)} 个站点")
        except FileNotFoundError:
            print(f"警告: 站点文件 {filename} 不存在")
            self.stations = []

    def reset(self):
        """重置所有站点状态"""
        for station in self.stations:
            station.intensity = -3
            station.target_intensity = -3
            station.max_intensity = -3
            station.p_wave_arrived = False
            station.s_wave_arrived = False
            station.time_since_peak = 0
            station.p_arrival_time = None  # 重置P波到达记录
            station.p_amplitude = 0

    def update(self, earthquake, current_time: float, dt: float):
        """更新所有站点"""
        # 收集本次更新检测到的震度等级
        detected_intensity_levels = set()

        for station in self.stations:
            station.update(earthquake, current_time, dt)

            # 收集当前震度等级
            level = station.get_intensity_level()
            if level is not None:
                detected_intensity_levels.add(level)

        return detected_intensity_levels  # 返回检测到的所有震度等级

    def render(self, screen: pygame.Surface, simulator, station_icons: Dict[int, pygame.Surface] = None):
        """渲染所有站点

        两层渲染逻辑：
        1. 底层：站点圆点，使用连续渐变色阶（深蓝→蓝→青→绿→黄→橙→红）
        2. 上层：震度SVG图标（震度>=0时显示，包括震度0）
        """
        # 图标缩放因子：限制在0.02-0.41之间
        icon_scale = min(0.41, max(0.02, 0.1 * simulator.zoom_level))

        rendered = 0

        for station in self.stations:
            # 转换经纬度到屏幕坐标
            screen_x, screen_y = simulator.latlon_to_screen(
                station.lat, station.lon
            )

            # 检查是否在屏幕范围内
            if not (0 <= screen_x <= WINDOW_WIDTH and 0 <= screen_y <= WINDOW_HEIGHT):
                continue

            rendered += 1
            pos = (int(screen_x), int(screen_y))

            # 第一层：始终绘制圆点，颜色随震度连续渐变（稍微放大）
            r = max(3, int(8 * icon_scale))
            color = station.get_color()
            pygame.draw.circle(screen, color, pos, r)
            pygame.draw.circle(screen, (30, 30, 30), pos, r, 1)  # 深色边框

            # 第二层：震度>=0时显示SVG图标（包括震度0）
            if station.intensity >= 0 and station_icons:
                icon_idx = intensity_to_scale(station.intensity)
                idx_map = {'0':0, '1':1, '2':2, '3':3, '4':4, '5-':5, '5+':6, '6-':7, '6+':8, '7':9}
                idx = idx_map.get(icon_idx, 0)

                if idx in station_icons:
                    icon = scale_icon(station_icons[idx], icon_scale)
                    rect = icon.get_rect(center=pos)
                    screen.blit(icon, rect)

    def get_max_intensity_in_region(self, region_bounds: Tuple[float, float, float, float]) -> float:
        """获取区域内的最大震度"""
        min_lat, max_lat, min_lon, max_lon = region_bounds
        max_intensity = -3

        for station in self.stations:
            if (min_lat <= station.lat <= max_lat and
                min_lon <= station.lon <= max_lon):
                max_intensity = max(max_intensity, station.intensity)

        return max_intensity

    def get_stations_needing_sound(self) -> List[Station]:
        """获取需要播放音效的站点"""
        stations_to_sound = []
        for station in self.stations:
            # 只有震度达到1-6弱且未播放过的才播放
            if (1 <= station.intensity < 6.5 and
                station.intensity > station.last_sound_intensity):
                stations_to_sound.append(station)
                station.last_sound_intensity = int(station.intensity)

        return stations_to_sound

    def get_p_wave_arrivals(self) -> List[Tuple[float, float, float]]:
        """
        获取所有已检测到P波的站点数据（用于实时定位）

        Returns:
            [(lat, lon, arrival_time), ...] P波到达数据列表
        """
        arrivals = []
        for station in self.stations:
            if station.p_arrival_time is not None:
                arrivals.append((station.lat, station.lon, station.p_arrival_time))
        return arrivals

    def get_p_wave_arrivals_with_amplitude(self) -> List[Tuple[float, float, float, float]]:
        """
        获取所有已检测到P波的站点数据（含振幅，用于震级估算）

        Returns:
            [(lat, lon, arrival_time, amplitude), ...] P波到达数据列表
        """
        arrivals = []
        for station in self.stations:
            if station.p_arrival_time is not None and station.p_amplitude > 0:
                arrivals.append((
                    station.lat, station.lon,
                    station.p_arrival_time, station.p_amplitude
                ))
        return arrivals

    def get_detected_station_count(self) -> int:
        """获取已检测到P波的站点数量"""
        return sum(1 for s in self.stations if s.p_arrival_time is not None)
