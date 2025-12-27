"""地震模拟器主程序 - pygame可视化"""
import pygame
import json
import math
import os
import sys
import io

try:
    import cairosvg
    CAIRO_AVAILABLE = True
except (ImportError, OSError):
    CAIRO_AVAILABLE = False
    print("Warning: cairosvg/Cairo not available. SVG icons will not be loaded.")

from config import *
from earthquake import Earthquake
from intensity import calc_jma_intensity, intensity_to_scale, get_intensity_color
from epicenter import EpicenterLocator
from map_renderer import MapRenderer
from multisource import MultiSourceManager, RuptureSource
from projection import latlon_to_xy_km, xy_km_to_latlon
from sound_manager import SoundManager
from eew_tracker import EEWTracker
from station_manager import StationManager
from eew_alert import EEWAlert
from earthquake_history import EarthquakeHistory

# 显示模式
MODE_STATION = 0  # 站点模式
MODE_REGION = 1   # 区域模式

def load_svg(path, scale=1.0):
    """加载SVG文件并转换为pygame surface"""
    if not CAIRO_AVAILABLE:
        return None
    try:
        png_data = cairosvg.svg2png(url=path, scale=scale)
        return pygame.image.load(io.BytesIO(png_data))
    except Exception as e:
        print(f"Warning: Failed to load SVG {path}: {e}")
        return None

def scale_icon(icon, factor):
    """缩放图标"""
    if icon is None:
        return None
    w, h = icon.get_size()
    new_w = max(1, int(w * factor))
    new_h = max(1, int(h * factor))
    return pygame.transform.smoothscale(icon, (new_w, new_h))

# 震度颜色映射（与intensity.py的get_intensity_color()保持一致）
SHINDO_COLORS = {
    1: (100, 150, 200),   # 震度1 - 浅蓝色
    2: (50, 180, 50),     # 震度2 - 绿色
    3: (200, 200, 0),     # 震度3 - 黄色
    4: (255, 150, 0),     # 震度4 - 橙色
    5: (255, 80, 0),      # 震度5- - 橙红色
    6: (255, 0, 0),       # 震度5+ - 纯红色
    7: (180, 0, 50),      # 震度6- - 深红色
    8: (150, 0, 100),     # 震度6+ - 紫红色
    9: (100, 0, 100),     # 震度7 - 紫色
}

def get_shindo_color(intensity):
    """根据震度值获取颜色"""
    scale = intensity_to_scale(intensity)
    idx_map = {'1':1, '2':2, '3':3, '4':4, '5-':5, '5+':6, '6-':7, '6+':8, '7':9}
    idx = idx_map.get(scale, 3)
    return SHINDO_COLORS.get(idx, (0xED, 0xAA, 0x00))

class EarthquakeSimulator:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(200, 50)  # 长按支持
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("地震波到达时间模拟器")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        # 尝试加载中文字体
        try:
            font_paths = [
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "/System/Library/Fonts/PingFang.ttc",
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    self.font_cn = pygame.font.Font(fp, 20)
                    self.font_cn_large = pygame.font.Font(fp, 36)
                    self.font_cn_small = pygame.font.Font(fp, 16)
                    break
            else:
                self.font_cn = self.font
                self.font_cn_large = pygame.font.Font(None, 40)
                self.font_cn_small = pygame.font.Font(None, 18)
        except:
            self.font_cn = self.font
            self.font_cn_large = pygame.font.Font(None, 40)
            self.font_cn_small = pygame.font.Font(None, 18)

        # 加载震央地名数据（用于定位）
        geojson_path = os.path.join(os.path.dirname(__file__),
                                     "../JMA_Region-main/震央地名.geojson")
        self.locator = EpicenterLocator(geojson_path if os.path.exists(geojson_path) else None)

        # 加载都道府县地图（用于显示日本轮廓）
        pref_path = os.path.join(os.path.dirname(__file__),
                                  "../JMA_Region-main/prefectures.geojson")
        self.prefectures = []
        if os.path.exists(pref_path):
            with open(pref_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.prefectures = data.get('features', [])

        # 地图参数
        self.map_bounds = MAP_BOUNDS.copy()
        self.default_bounds = MAP_BOUNDS.copy()  # 保存默认边界用于缩放限制
        self.zoom_level = 1.0
        self.earthquake = None
        self.running = True
        self.paused = False
        self.time_scale = 1.0
        self.sim_mode = "single"  # single / multi
        self.multi_state = "draw_fault"  # draw_fault -> place_sources -> choose_start -> ready
        self.fault_line = []  # [(lat, lon), ...]
        self.multi_sources = []  # [RuptureSource]
        self.multi_manager: MultiSourceManager | None = None
        self.multi_direction = "forward"
        self.multi_start_source = None
        self.rupture_velocity = 2.5

        # 设置模式
        self.setting_mode = True
        self.temp_lat = 35.7
        self.temp_lon = 139.7
        self.temp_depth = 10
        self.temp_mag = 6.0

        # 自动缩放设置（动态追踪模式）
        self.auto_zoom_enabled = True  # 是否启用自动缩放
        self.auto_zoom_mode = "off"  # 追踪模式: "off", "waiting", "following_station", "following_p", "following_s", "return_to_epicenter"
        self.tracked_station = None  # 当前追踪的站点 (lat, lon)
        self.max_detected_intensity = 0.0  # 已检测到的最大震度
        self.tracking_start_time = 0  # 追踪开始时间
        self.zoom_locked = False  # 是否已锁定缩放（不再继续放大）
        self.last_intensity_update_time = 0  # 最后一次震度更新时间
        self.last_zoom_time = 0  # 最后一次缩放时间（用于间隔式缩放）
        self.zoom_interval = 2.0  # 缩放间隔（秒）- 停一下再缩
        self.is_zooming = False  # 是否正在缩放中（缩放动画）
        self.max_view_radius_km = 700  # 最大视野半径（km）- 缩到这个范围就停止
        self.waiting_for_return = False  # 是否正在等待回到震央（避免重复设置时间）

        # 波形显示控制
        self.show_true_waves = True  # 是否显示真实波形
        self.show_tracking_waves = True  # 是否显示追标波形

        # EEW追标模式
        self.eew_tracking_enabled = True  # 是否启用EEW追标
        self.eew_tracker = None  # EEW追标器实例
        self.tracking_wave_visible = False  # 追标波形是否可见（站点检测到后才显示）
        self.first_detection_time = None  # 首次检测到站点的时间（用于追波时间计算）

        # 真实波形的初始震央位置（不随EEW修正而改变）
        self.true_epicenter_lat = None
        self.true_epicenter_lon = None

        # 区域震度数据
        self.region_intensities = {}
        self.max_intensity = 0
        self.detected_regions = []

        # 显示模式
        self.display_mode = MODE_REGION

        # 加载图标
        self.load_icons()

        # 加载站点和区域数据
        self.stations = []
        self.regions_data = []  # 细分区域（用于填色）
        self.load_station_region_data()

        # 加载音频
        pygame.mixer.init()

        # 初始化音频管理器（使用Scratch项目的高质量音频）
        try:
            self.sound_manager = SoundManager()
            print("[主程序] 音频管理器已加载")
        except Exception as e:
            print(f"[主程序] 音频管理器加载失败: {e}")
            self.sound_manager = None

        # 旧的简单音频（已弃用 - 现在使用SoundManager统一管理）
        # 保留变量以兼容旧代码，但不再加载文件
        self.intensity4_sound = None
        self.intensity4_played = False
        self.intensity7_sound = None
        self.intensity7_played = False

        # 白色圆圈闪烁动画
        self.max_triggered_intensity = 0.0  # 已触发的最大震度值
        self.alert_animations = []  # 动画队列: [(lat, lon, start_time, scale), ...]

        # EEW警报音播放控制
        self.eew_alert_played = False  # 是否已播放EEW警报音（等到站点检测到地震波才播放）

        # 全局震度音效触发记录
        self.triggered_intensity_sounds = set()  # 已触发的震度等级 {0, 1, 2, 3, 4, 5, 6}

        # 音频增长逻辑（Scratch兼容）
        self.last_intensity_snapshot = ""  # 上次震度快照（用于检测稳定性）
        self.intensity_stable_time = 0  # 震度稳定时间（秒）
        self.final_report_played = False  # 最终报是否已播放

        # 新增：站点管理器（1748个观测站）
        try:
            self.station_manager = StationManager("stations_data.json")
            print(f"[主程序] 站点管理器已加载: {len(self.station_manager.stations)} 个站点")
        except Exception as e:
            print(f"[主程序] 站点管理器加载失败: {e}")
            self.station_manager = None

        # 新增：EEW警报框UI
        self.eew_alert_box = EEWAlert()

        # 新增：地震履歴记录系统
        self.history = EarthquakeHistory()
        print("[主程序] 地震履歴记录器已初始化")

    def load_icons(self):
        """加载SVG图标"""
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        # 站点图标 s0-s9 (圆形) - s0是震度0，s1-s9是震度1-7
        self.station_icons = {}
        for i in range(0, 10):  # 从0开始，包含震度0
            path = os.path.join(assets_dir, f"s{i}.svg")
            if os.path.exists(path):
                self.station_icons[i] = load_svg(path, scale=0.5)

        # 区域图标 t1-t9 (方形)
        self.region_icons = {}
        for i in range(1, 10):
            path = os.path.join(assets_dir, f"t{i}.svg")
            if os.path.exists(path):
                self.region_icons[i] = load_svg(path, scale=0.5)

        # 震度图标 (左上角最大震度显示)
        self.shindo_icons = {}
        shindo_files = {
            0: "震度0.svg", 1: "震度1.svg", 2: "震度2.svg", 3: "震度3.svg",
            4: "震度4.svg", 5: "震度5弱.svg", 6: "震度5強.svg",
            7: "震度6弱.svg", 8: "震度6強.svg", 9: "震度7.svg"
        }
        for idx, fname in shindo_files.items():
            path = os.path.join(assets_dir, fname)
            if os.path.exists(path):
                self.shindo_icons[idx] = load_svg(path, scale=1.0)

        # 震央图标
        path = os.path.join(assets_dir, "po央.svg")
        self.epicenter_icon = load_svg(path, scale=0.8) if os.path.exists(path) else None

        # 位置图标 (设置模式鼠标跟随)
        path = os.path.join(assets_dir, "位置.svg")
        self.position_icon = load_svg(path, scale=0.8) if os.path.exists(path) else None

        # S波圆圈图标
        path = os.path.join(assets_dir, "円.svg")
        self.s_wave_icon = load_svg(path, scale=1.0) if os.path.exists(path) else None

    def load_station_region_data(self):
        """加载站点和区域数据"""
        data_dir = os.path.join(os.path.dirname(__file__), "data")

        # 加载站点
        stations_path = os.path.join(data_dir, "stations.json")
        if os.path.exists(stations_path):
            with open(stations_path, 'r', encoding='utf-8') as f:
                self.stations = json.load(f)

        # 加载细分区域多边形（地震情報／細分区域）
        regions_path = os.path.join(data_dir, "area_forecast.geojson")
        if os.path.exists(regions_path):
            with open(regions_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.regions_data = data.get('features', [])

    def _view_km_params(self) -> tuple[float, float, float, float, float, float, float]:
        """把当前 map_bounds 转成 km 平面范围与屏幕映射参数（统一比例）。

        返回：x_min_km, x_max_km, y_min_km, y_max_km, pixels_per_km, x_offset_px, y_offset_px
        """
        cache_key = (
            self.map_bounds["min_lon"],
            self.map_bounds["max_lon"],
            self.map_bounds["min_lat"],
            self.map_bounds["max_lat"],
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
        )
        if getattr(self, "_view_cache_key", None) == cache_key:
            return self._view_cache_params

        # km 平面边界
        x_min_km, _ = latlon_to_xy_km(0.0, self.map_bounds["min_lon"])
        x_max_km, _ = latlon_to_xy_km(0.0, self.map_bounds["max_lon"])
        _, y_min_km = latlon_to_xy_km(self.map_bounds["min_lat"], 0.0)
        _, y_max_km = latlon_to_xy_km(self.map_bounds["max_lat"], 0.0)

        x_span = max(1e-6, x_max_km - x_min_km)
        y_span = max(1e-6, y_max_km - y_min_km)
        pixels_per_km = min(WINDOW_WIDTH / x_span, WINDOW_HEIGHT / y_span)

        # 为了保持 x/y 同比例，可能会产生留白；这里居中显示
        x_offset = (WINDOW_WIDTH - x_span * pixels_per_km) / 2
        y_offset = (WINDOW_HEIGHT - y_span * pixels_per_km) / 2
        params = (x_min_km, x_max_km, y_min_km, y_max_km, pixels_per_km, x_offset, y_offset)
        self._view_cache_key = cache_key
        self._view_cache_params = params
        return params

    def latlon_to_screen(self, lat: float, lon: float) -> tuple:
        """经纬度转屏幕坐标（Scratch 兼容投影，波前为正圆）。"""
        x_min_km, x_max_km, y_min_km, y_max_km, ppk, x_off, y_off = self._view_km_params()
        x_km, y_km = latlon_to_xy_km(lat, lon)
        sx = x_off + (x_km - x_min_km) * ppk
        sy = y_off + (y_max_km - y_km) * ppk
        return int(sx), int(sy)

    def screen_to_latlon(self, x: int, y: int) -> tuple:
        """屏幕坐标转经纬度（Scratch 兼容投影）。"""
        x_min_km, x_max_km, y_min_km, y_max_km, ppk, x_off, y_off = self._view_km_params()
        x_km = x_min_km + (x - x_off) / ppk
        y_km = y_max_km - (y - y_off) / ppk
        return xy_km_to_latlon(x_km, y_km)

    # --- 多震源辅助方法 --------------------------------------------------
    def _current_time_value(self) -> float:
        """返回当前模拟时间（单/多模式兼容）。"""
        if self.sim_mode == "multi" and self.multi_manager:
            return self.multi_manager.time
        if self.earthquake:
            return self.earthquake.time
        return 0.0

    def reset_multi_setup(self):
        """清空多震源设置状态。"""
        self.fault_line = []
        self.multi_sources = []
        self.multi_state = "draw_fault"
        self.multi_start_source = None
        self.multi_direction = "forward"
        self.multi_manager = None
        self.region_intensities = {}
        self.station_intensities = {}
        self.region_max_intensities = {}
        self.max_intensity = 0
        self.max_intensity_location = ""
        self.intensity4_played = False
        self.intensity7_played = False
        self.max_triggered_intensity = 0.0
        self.alert_animations.clear()
        self.triggered_intensity_sounds = set()  # 重置音效触发记录

        # 重置站点管理器
        if hasattr(self, 'station_manager') and self.station_manager:
            self.station_manager.reset()

        # 重置地图缩放
        self.map_bounds = MAP_BOUNDS.copy()
        self.zoom_level = 1.0
        self.reset_auto_tracking()  # 重置追踪状态

    def project_to_fault(self, lat: float, lon: float) -> tuple:
        """将点投影到当前断层折线，返回投影点（若无折线则原样返回）。"""
        if len(self.fault_line) < 2:
            return lat, lon
        km_points = [latlon_to_xy_km(p[0], p[1]) for p in self.fault_line]
        px, py = latlon_to_xy_km(lat, lon)
        best = None
        best_d2 = float("inf")
        cumulative = [0.0]
        for i in range(1, len(km_points)):
            x0, y0 = km_points[i - 1]
            x1, y1 = km_points[i]
            cumulative.append(cumulative[-1] + math.hypot(x1 - x0, y1 - y0))
        for i in range(len(km_points) - 1):
            (x0, y0), (x1, y1) = km_points[i], km_points[i + 1]
            vx, vy = x1 - x0, y1 - y0
            seg_len2 = vx * vx + vy * vy
            if seg_len2 <= 1e-9:
                continue
            t = ((px - x0) * vx + (py - y0) * vy) / seg_len2
            t = max(0.0, min(1.0, t))
            proj_x = x0 + t * vx
            proj_y = y0 + t * vy
            d2 = (proj_x - px) ** 2 + (proj_y - py) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = (proj_x, proj_y, i, t)
        if best is None:
            return lat, lon
        proj_x, proj_y, idx, t = best
        lat_proj, lon_proj = xy_km_to_latlon(proj_x, proj_y)
        return lat_proj, lon_proj

    def start_multi_simulation(self):
        """根据当前多震源设置启动模拟。"""
        if not self.multi_sources:
            return
        manager = MultiSourceManager(polyline=self.fault_line, rupture_velocity=self.rupture_velocity)
        manager.set_direction(self.multi_direction)
        manager.set_sources(self.multi_sources)
        manager.set_start_source(self.multi_start_source)
        manager.recompute_activation_times()
        self.multi_manager = manager

        # 多震源模式不启用自动追踪（太复杂）
        self.reset_auto_tracking()

        # 播放EEW警报音
        if self.sound_manager:
            self.sound_manager.play_eew()
            self.sound_manager.reset_announcement()

        self.setting_mode = False
        self.paused = False
        self.intensity4_played = False
        self.intensity7_played = False
        self.max_triggered_intensity = 0.0
        self.alert_animations.clear()

    def calculate_station_intensities(self):
        """派发单/多震源计算。"""
        if self.sim_mode == "multi":
            return self.calculate_station_intensities_multi()
        return self.calculate_station_intensities_single()

    def calculate_station_intensities_single(self):
        """计算各站点震度（旧系统，仅用于追波驱动和站点检测）

        注意：区域填色数据由 update_region_intensities_from_new_stations() 独立管理
        本函数不再修改 region_max_intensities / max_intensity / max_intensity_location
        """
        if not self.earthquake:
            return

        # 获取当前波的震央距离半径
        p_radius = self.earthquake.get_p_wave_radius()
        s_radius = self.earthquake.get_s_wave_radius()
        self.station_intensities = {}  # (lat,lon) -> (intensity, is_s_wave)
        # region_max_intensities 由 update_region_intensities_from_new_stations() 独立管理

        for station in self.stations:
            lat = float(station['lat'])
            lon = float(station['lon'])
            amp = float(station.get('amp', 1.0))  # 站点放大系数

            # 使用震央距离判断波是否到达
            epicentral_dist = self.earthquake.get_epicentral_distance(lat, lon)

            # 计算S波实际震度（Scratch 兼容：场地系数 amp 先变换成 bai 再参与计算）
            bai = (amp * 4 + amp * amp) / 5.0
            s_intensity = calc_jma_intensity(
                self.earthquake.magnitude,
                self.earthquake.depth,
                epicentral_dist,
                bai=bai,
            )
            # P波震度计算 (Scratch公式: S波震度 / 1.5 - 0.5)
            p_intensity = s_intensity / 1.5 - 0.5

            if epicentral_dist <= s_radius and s_intensity >= 0.5:
                self.station_intensities[(lat, lon)] = (s_intensity, True)
            elif epicentral_dist <= p_radius and p_intensity >= 0.5:
                self.station_intensities[(lat, lon)] = (p_intensity, False)

    def calculate_station_intensities_multi(self):
        """多震源震度聚合：取最大值。"""
        if not self.multi_manager:
            return
        self.station_intensities = {}
        self.region_max_intensities = {}
        self.max_intensity = 0
        self.max_intensity_location = ""

        for station in self.stations:
            lat = float(station['lat'])
            lon = float(station['lon'])
            area_code = station['area']['code']
            area_name = station['area']['name']
            amp = float(station.get('amp', 1.0))

            intensity, is_s_wave = self.multi_manager.calc_intensity(lat, lon, amp=amp)
            if intensity < 0.5:
                continue

            self.station_intensities[(lat, lon)] = (intensity, is_s_wave)
            if area_code not in self.region_max_intensities or intensity > self.region_max_intensities[area_code]:
                self.region_max_intensities[area_code] = intensity
            if intensity > self.max_intensity:
                self.max_intensity = intensity
                self.max_intensity_location = area_name

        # 使用新的音频管理器播报震度（带冷却机制，避免频繁播报）
        # 新版本统一处理震度3-7的播报，替换了旧的震度4和震度7单独播放逻辑
        if self.sound_manager and self.max_intensity >= 3.0:
            self.sound_manager.announce_with_cooldown(self.max_intensity, cooldown_seconds=3.0)

        for (lat, lon), (intensity, is_s_wave) in self.station_intensities.items():
            if intensity >= 3.0 and intensity > self.max_triggered_intensity:
                scale = intensity_to_scale(intensity)
                self.max_triggered_intensity = intensity
                self.alert_animations.append((lat, lon, self._current_time_value(), scale))
                break

    def draw_stations(self):
        """绘制站点模式 - 使用s1-s9图标"""
        # 图标缩放因子：限制在0.02-0.41之间
        icon_scale = min(0.41, max(0.02, 0.1 * self.zoom_level))

        for station in self.stations:
            lat = float(station['lat'])
            lon = float(station['lon'])
            data = self.station_intensities.get((lat, lon))
            if not data:
                continue

            intensity, is_s_wave = data
            x, y = self.latlon_to_screen(lat, lon)

            # 震度转图标索引
            icon_idx = intensity_to_scale(intensity)
            idx_map = {'1':1, '2':2, '3':3, '4':4, '5-':5, '5+':6, '6-':7, '6+':8, '7':9}
            idx = idx_map.get(icon_idx, 1)

            if idx in self.station_icons:
                icon = scale_icon(self.station_icons[idx], icon_scale)
                rect = icon.get_rect(center=(x, y))
                self.screen.blit(icon, rect)
            else:
                r = max(3, int(10 * icon_scale))
                color = get_intensity_color(intensity)
                pygame.draw.circle(self.screen, color, (x, y), r)
                pygame.draw.circle(self.screen, (0, 0, 0), (x, y), r, 1)

    def draw_regions_with_intensity(self, fill_only=False, icons_only=False):
        """绘制带震度的区域 - 使用t1-t9图标 + 区域填色

        Args:
            fill_only: 仅绘制填色（站点模式背景）
            icons_only: 仅绘制图标（区域模式）
        """
        region_labels = []
        # 图标缩放因子：限制在0.15-0.6之间
        icon_scale = min(0.6, max(0.15, 0.1 * self.zoom_level))

        for region in self.regions_data:
            props = region.get('properties', {})
            code = props.get('code', '')
            geom = region.get('geometry', {})
            coords = geom.get('coordinates', [])
            geom_type = geom.get('type', '')

            intensity = self.region_max_intensities.get(code, 0)

            if geom_type == 'Polygon':
                polys = [coords[0]]
            elif geom_type == 'MultiPolygon':
                polys = [c[0] for c in coords]
            else:
                continue

            # 绘制区域填充（根据震度）
            if not icons_only and intensity >= 1:
                fill_color = self._get_region_fill_color(intensity)
                if fill_color:
                    for poly in polys:
                        points = []
                        for lon, lat in poly:
                            x, y = self.latlon_to_screen(lat, lon)
                            points.append((int(x), int(y)))
                        if len(points) >= 3:
                            # 创建临时surface用于半透明填充
                            temp_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                            pygame.draw.polygon(temp_surface, fill_color, points)
                            self.screen.blit(temp_surface, (0, 0))

                # 收集区域中心用于绘制图标
                if not fill_only:
                    all_lons = []
                    all_lats = []
                    for poly in polys:
                        for lon, lat in poly:
                            all_lons.append(lon)
                            all_lats.append(lat)
                    if all_lons:
                        cx, cy = self.latlon_to_screen(sum(all_lats)/len(all_lats), sum(all_lons)/len(all_lons))
                        region_labels.append((cx, cy, intensity))

        # 绘制区域震度标签
        if not fill_only:
            for cx, cy, intensity in region_labels:
                icon_idx = intensity_to_scale(intensity)
                idx_map = {'1':1, '2':2, '3':3, '4':4, '5-':5, '5+':6, '6-':7, '6+':8, '7':9}
                idx = idx_map.get(icon_idx, 1)

                if idx in self.region_icons:
                    icon = scale_icon(self.region_icons[idx], icon_scale)
                    rect = icon.get_rect(center=(cx, cy))
                    self.screen.blit(icon, rect)
                else:
                    s = max(6, int(20 * icon_scale))
                    color = get_intensity_color(intensity)
                    pygame.draw.rect(self.screen, color, (cx-s//2, cy-s//2, s, s))
                    pygame.draw.rect(self.screen, (0, 0, 0), (cx-s//2, cy-s//2, s, s), 1)

    def _get_region_fill_color(self, intensity: float):
        """根据震度获取区域填充颜色（RGBA）"""
        if intensity < 1:
            return None
        elif intensity < 2:
            return (100, 150, 255, 60)   # 震度1 浅蓝
        elif intensity < 3:
            return (50, 100, 200, 80)    # 震度2 蓝
        elif intensity < 4:
            return (50, 255, 50, 100)    # 震度3 绿/黄
        elif intensity < 5:
            return (255, 200, 0, 120)    # 震度4 橙黄
        elif intensity < 5.5:
            return (255, 150, 0, 140)    # 震度5弱 橙
        elif intensity < 6:
            return (255, 50, 0, 160)     # 震度5强 红橙
        elif intensity < 6.5:
            return (255, 0, 0, 180)      # 震度6弱 红
        elif intensity < 7:
            return (200, 0, 100, 200)    # 震度6强 紫红
        else:
            return (150, 0, 150, 220)    # 震度7 紫

    def update_region_intensities_from_new_stations(self):
        """从新站点系统更新区域震度（用于区域填色）"""
        if not self.station_manager:
            return

        # 首次调用时预计算站点-区域映射（只计算一次）
        if not hasattr(self, '_station_region_cache'):
            self._station_region_cache = {}
            print("[性能优化] 预计算站点-区域映射...")
            for station in self.station_manager.stations:
                region_code = self._find_region_for_point(station.lat, station.lon)
                self._station_region_cache[station.id] = region_code
            print(f"[性能优化] 完成，缓存了 {len(self._station_region_cache)} 个站点")

        # 清空并重建区域震度
        self.region_max_intensities = {}
        self.max_intensity = 0
        self.max_intensity_location = ""

        # 遍历所有站点，使用缓存的区域代码
        for station in self.station_manager.stations:
            if station.intensity < 0.5:
                continue

            # 使用缓存的区域代码（O(1) 查找）
            region_code = self._station_region_cache.get(station.id, "")
            if not region_code:
                continue

            # 更新区域最大震度
            if region_code not in self.region_max_intensities or station.intensity > self.region_max_intensities[region_code]:
                self.region_max_intensities[region_code] = station.intensity

            # 更新全局最大震度
            if station.intensity > self.max_intensity:
                self.max_intensity = station.intensity
                # 查找区域名称（也可以缓存，但这个不频繁）
                for region in self.regions_data:
                    if region.get('properties', {}).get('code', '') == region_code:
                        self.max_intensity_location = region.get('properties', {}).get('name', '')
                        break

    def _find_region_for_point(self, lat: float, lon: float) -> str:
        """查找点所在的区域代码（使用point-in-polygon算法）"""
        for region in self.regions_data:
            props = region.get('properties', {})
            code = props.get('code', '')
            geom = region.get('geometry', {})
            coords = geom.get('coordinates', [])
            geom_type = geom.get('type', '')

            if geom_type == 'Polygon':
                polys = [coords[0]]
            elif geom_type == 'MultiPolygon':
                polys = [c[0] for c in coords]
            else:
                continue

            # 检查点是否在任一多边形内
            for poly in polys:
                if self._point_in_polygon(lat, lon, poly):
                    return code

        return ""

    def _point_in_polygon(self, lat: float, lon: float, polygon: list) -> bool:
        """射线法判断点是否在多边形内"""
        n = len(polygon)
        inside = False

        p1_lon, p1_lat = polygon[0]
        for i in range(1, n + 1):
            p2_lon, p2_lat = polygon[i % n]

            if lat > min(p1_lat, p2_lat):
                if lat <= max(p1_lat, p2_lat):
                    if lon <= max(p1_lon, p2_lon):
                        if p1_lat != p2_lat:
                            xinters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                        if p1_lon == p2_lon or lon <= xinters:
                            inside = not inside

            p1_lon, p1_lat = p2_lon, p2_lat

        return inside

    def draw_wave_circles(self):
        """绘制地震波圆和震央标记（支持双重显示）"""
        if self.sim_mode == "multi":
            if not self.multi_manager:
                return
            _, _, _, _, pixels_per_km, _, _ = self._view_km_params()
            s_color = get_shindo_color(self.max_intensity) if self.max_intensity >= 0.5 else (128, 128, 128)

            # 绘制波前（不使用円.svg，只用pygame.draw.circle）
            for circle in self.multi_manager.get_wave_circles():
                cx, cy = self.latlon_to_screen(circle["lat"], circle["lon"])
                p_px = int(circle["p_radius"] * pixels_per_km)
                s_px = int(circle["s_radius"] * pixels_per_km)
                if p_px > 0 and p_px < WINDOW_WIDTH * 3:
                    pygame.draw.circle(self.screen, (0, 150, 255), (cx, cy), p_px, 2)
                if s_px > 0 and s_px < WINDOW_WIDTH * 3:
                    pygame.draw.circle(self.screen, s_color, (cx, cy), s_px, 3)

            # 绘制已激活的震源点（使用震央图标）
            icon_scale = min(0.8, max(0.2, 0.15 * self.zoom_level))
            for src in self.multi_manager.sources:
                if src.active:  # 只显示已激活的震源
                    ex, ey = self.latlon_to_screen(src.lat, src.lon)
                    if self.epicenter_icon:
                        icon = scale_icon(self.epicenter_icon, icon_scale)
                        rect = icon.get_rect(center=(ex, ey))
                        self.screen.blit(icon, rect)
                    else:
                        s = max(8, int(15 * icon_scale))
                        pygame.draw.line(self.screen, (255, 0, 0), (ex-s, ey), (ex+s, ey), 3)
                        pygame.draw.line(self.screen, (255, 0, 0), (ex, ey-s), (ex, ey+s), 3)
            return

        if not self.earthquake:
            return

        # 单震源模式：支持双重波形显示
        _, _, _, _, pixels_per_km, _, _ = self._view_km_params()

        # 绘制真实波形（使用初始震央位置，不随EEW修正而移动）
        if self.show_true_waves and self.true_epicenter_lat is not None:
            self._draw_single_wave(self.true_epicenter_lat, self.true_epicenter_lon,
                                  self.earthquake, suffix="真实")

        # 绘制追标波形（只有在站点检测到地震波后才显示）
        if (self.show_tracking_waves and self.tracking_wave_visible and
            self.eew_tracker and self.eew_tracker.enabled):
            tracking_lat, tracking_lon, tracking_depth, tracking_mag = self.eew_tracker.get_current_values()

            # 创建临时地震对象用于绘制追标波形
            from earthquake import Earthquake
            temp_eq = Earthquake(tracking_lat, tracking_lon, tracking_depth, tracking_mag)
            # 追标波形时间 = 当前时间 - 首次检测时间（追波从站点检测到时才开始）
            if self.first_detection_time is not None:
                temp_eq.time = self.earthquake.time - self.first_detection_time
            else:
                temp_eq.time = 0  # 尚未检测到，不显示波形

            self._draw_single_wave(tracking_lat, tracking_lon, temp_eq, suffix="追标")

    def _draw_single_wave(self, lat, lon, earthquake_obj, suffix=""):
        """
        绘制单个地震的波形

        Args:
            lat: 震央纬度
            lon: 震央经度
            earthquake_obj: 地震对象
            suffix: 标签后缀（"真实"或"追标"）
        """
        ex, ey = self.latlon_to_screen(lat, lon)
        _, _, _, _, pixels_per_km, _, _ = self._view_km_params()

        # 追标波形使用与真实波形相同的颜色（只有位置不同）
        # P波颜色统一为蓝色
        p_color = (0, 150, 255)

        # S波颜色根据震度
        s_color_base = get_shindo_color(self.max_intensity) if self.max_intensity >= 0.5 else (128, 128, 128)

        # 震央颜色统一为红色（追标不改变震央SVG颜色）
        epicenter_color = (255, 0, 0)

        # P波 (蓝色) - 正圆
        p_radius_km = earthquake_obj.get_p_wave_radius()
        p_radius_px = int(p_radius_km * pixels_per_km)
        if p_radius_px > 0 and p_radius_px < WINDOW_WIDTH * 3:
            pygame.draw.circle(self.screen, p_color, (ex, ey), p_radius_px, 2)

        # S波
        s_radius_km = earthquake_obj.get_s_wave_radius()
        s_radius_px = int(s_radius_km * pixels_per_km)

        # S波准备圆圈（从地震开始到S波到达地表时完成）
        SCRATCH_P = 6.5
        SCRATCH_S = 4.0
        depth = earthquake_obj.depth
        s_arrival_time = depth * (1 - SCRATCH_S / SCRATCH_P) / SCRATCH_S
        current_time = earthquake_obj.time

        if 0 < current_time < s_arrival_time:
            progress = current_time / s_arrival_time
            angle_deg = min(360, progress * 360)
            base_radius = 100
            arc_radius = max(15, int(base_radius * 0.15 * self.zoom_level))
            arc_rect = pygame.Rect(ex - arc_radius, ey - arc_radius, arc_radius * 2, arc_radius * 2)
            start_angle = math.pi / 2
            end_angle = start_angle + math.radians(angle_deg)
            if angle_deg > 1:
                pygame.draw.arc(self.screen, s_color_base, arc_rect, start_angle, end_angle, 3)

        # S波圆圈（追标波形不显示円.svg图标）
        if current_time >= s_arrival_time and s_radius_px > 0 and s_radius_px < WINDOW_WIDTH * 3:
            pygame.draw.circle(self.screen, s_color_base, (ex, ey), s_radius_px, 3)
            # 只有真实波形才显示円.svg图标
            if suffix == "真实" and self.s_wave_icon and s_radius_px > 10:
                icon_size = s_radius_px * 2
                icon = pygame.transform.smoothscale(self.s_wave_icon, (icon_size, icon_size))
                tinted = icon.copy()
                tinted.fill(s_color_base + (0,), special_flags=pygame.BLEND_RGB_MULT)
                tinted.set_alpha(80)
                rect = tinted.get_rect(center=(ex, ey))
                self.screen.blit(tinted, rect)

        # 绘制震央标记（追标波形使用相同的红色震央图标，不改变颜色）
        icon_scale = min(0.8, max(0.2, 0.15 * self.zoom_level))
        if self.epicenter_icon:
            icon = scale_icon(self.epicenter_icon, icon_scale)
            rect = icon.get_rect(center=(ex, ey))
            self.screen.blit(icon, rect)
        else:
            s = max(8, int(15 * icon_scale))
            pygame.draw.line(self.screen, epicenter_color, (ex-s, ey), (ex+s, ey), 3)
            pygame.draw.line(self.screen, epicenter_color, (ex, ey-s), (ex, ey+s), 3)

    def draw_alert_circles(self):
        """绘制站点首次检测震度时的白色圆圈闪烁动画"""
        if self.display_mode != MODE_STATION:
            return
        if self.sim_mode == "single" and not self.earthquake:
            return
        if self.sim_mode == "multi" and not self.multi_manager:
            return

        current_time = self._current_time_value()
        duration = 0.8  # 动画持续时间（秒）
        to_remove = []

        for i, (lat, lon, start_time, scale) in enumerate(self.alert_animations):
            elapsed = current_time - start_time
            if elapsed > duration:
                to_remove.append(i)
                continue

            # 计算动画进度（0到1）
            progress = elapsed / duration

            # 半径扩散：10px -> 60px
            radius = int(10 + 50 * progress)

            # 透明度衰减：255 -> 0
            alpha = int(255 * (1 - progress))

            # 转换为屏幕坐标
            x, y = self.latlon_to_screen(lat, lon)

            # 绘制白色圆圈（使用临时surface实现透明度）
            temp_surface = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(temp_surface, (255, 255, 255, alpha), (radius + 2, radius + 2), radius, 3)
            self.screen.blit(temp_surface, (x - radius - 2, y - radius - 2))

        # 清理已完成的动画
        for i in reversed(to_remove):
            self.alert_animations.pop(i)

    def draw_earthquake_info(self):
        """绘制地震速报风格信息（左上角）- 使用震度图标"""
        ref_lat = None
        ref_lon = None
        ref_mag = None
        ref_depth = None
        elapsed_time = None
        if self.sim_mode == "single":
            if not self.earthquake:
                return
            ref_lat = self.earthquake.lat
            ref_lon = self.earthquake.lon
            ref_mag = self.earthquake.magnitude
            ref_depth = self.earthquake.depth
            elapsed_time = self.earthquake.time
        else:
            if not self.multi_sources or not self.multi_manager:
                return
            ref = self.multi_start_source if self.multi_start_source else self.multi_sources[0]
            ref_lat = ref.lat
            ref_lon = ref.lon
            ref_mag = ref.magnitude
            ref_depth = ref.depth
            elapsed_time = self.multi_manager.time

        if self.max_intensity < 0.5:
            return

        scale = intensity_to_scale(self.max_intensity)
        color = get_intensity_color(self.max_intensity)

        # 震度转图标索引
        idx_map = {'0':0, '1':1, '2':2, '3':3, '4':4, '5-':5, '5+':6, '6-':7, '6+':8, '7':9}
        idx = idx_map.get(scale, 0)

        # 背景框
        pygame.draw.rect(self.screen, (0, 0, 0), (10, 10, 360, 180))
        pygame.draw.rect(self.screen, color, (10, 10, 360, 180), 3)

        y = 20
        surf = self.font_cn.render(f"最大震度", True, (255, 255, 255))
        self.screen.blit(surf, (20, y))

        # 使用震度图标 - 放在文字右边，缩小显示
        if idx in self.shindo_icons:
            icon = scale_icon(self.shindo_icons[idx], 0.6)
            self.screen.blit(icon, (260, y - 5))
        else:
            surf = self.font_cn_large.render(f"{scale}", True, color)
            self.screen.blit(surf, (260, y - 5))
        y += 50

        # 最大震度所在地
        if hasattr(self, 'max_intensity_location') and self.max_intensity_location:
            surf = self.font_cn_small.render(f"({self.max_intensity_location})", True, (200, 200, 200))
            self.screen.blit(surf, (20, y))
            y += 20

        # 震央
        location = self.locator.get_location_name(ref_lon, ref_lat, 'ja')
        surf = self.font_cn.render(f" {location}", True, (255, 255, 255))
        self.screen.blit(surf, (20, y))
        y += 25

        surf = self.font_cn.render(f"M{ref_mag:.1f} {int(ref_depth)}km", True, (255, 255, 255))
        self.screen.blit(surf, (20, y))
        y += 25

        # 多震源模式：显示已激活震源数量
        if self.sim_mode == "multi" and self.multi_manager:
            active_count = sum(1 for src in self.multi_manager.sources if src.active)
            total_count = len(self.multi_manager.sources)
            surf = self.font_cn_small.render(f"已激活: {active_count}/{total_count} 震源", True, (200, 200, 200))
            self.screen.blit(surf, (20, y))
            y += 20

        surf = self.font_cn_small.render(f"経過: {elapsed_time:.1f}秒", True, (200, 200, 200))
        self.screen.blit(surf, (20, y))

        # 显示EEW追标状态
        if self.sim_mode == "single" and self.eew_tracker and self.eew_tracker.enabled:
            y += 20
            if self.eew_tracker.is_tracking_complete():
                status_text = f"訂正完了 ({self.eew_tracker.revision_count}回)"
                status_color = (100, 200, 100)  # 绿色
            else:
                status_text = f"追標中... ({self.eew_tracker.revision_count}回訂正)"
                status_color = (255, 200, 0)  # 黄色
            surf = self.font_cn_small.render(status_text, True, status_color)
            self.screen.blit(surf, (20, y))

    def draw_setting_info(self):
        """绘制设置信息（无背景框）"""
        if not self.setting_mode:
            return

        if self.sim_mode == "multi":
            # 绘制断层折线与震源
            if len(self.fault_line) >= 2:
                points = [self.latlon_to_screen(lat, lon) for lat, lon in self.fault_line]
                pygame.draw.lines(self.screen, (180, 180, 220), False, points, 2)
            for idx, src in enumerate(self.multi_sources):
                x, y = self.latlon_to_screen(src.lat, src.lon)
                color = (255, 64, 64) if src == self.multi_start_source else (255, 200, 120)
                pygame.draw.circle(self.screen, color, (x, y), 6)
                pygame.draw.circle(self.screen, (0, 0, 0), (x, y), 6, 1)

            y = WINDOW_HEIGHT - 120
            if self.multi_state == "draw_fault":
                step_hint = "步骤1 画断层线: 左键添加点, 右键撤销, Enter完成"
            elif self.multi_state == "place_sources":
                step_hint = "步骤2 放置震源: 左键添加, 右键撤销, Enter完成"
            elif self.multi_state == "choose_start":
                step_hint = f"步骤3 选起点/方向: 左键起点, D切换方向({self.multi_direction}), Enter开始"
            else:
                step_hint = "按 Enter 开始模拟"

            texts = [
                (f"模式: 多震源 (Tab 切换)", (255, 255, 255)),
                (step_hint, (200, 220, 255)),
                (f"M{self.temp_mag:.1f} (←→) 深度{self.temp_depth}km (↑↓)", (255, 255, 0)),
                (f"破裂速度 {self.rupture_velocity:.1f} km/s (C/V 调整)", (200, 200, 200)),
            ]
            for text, color in texts:
                surf = self.font_cn.render(text, True, color)
                self.screen.blit(surf, (15, y))
                y += 25
            return

        # 单震源设置
        ex, ey = self.latlon_to_screen(self.temp_lat, self.temp_lon)
        depth = self.temp_depth
        depth_ratio = min(1.0, depth / 300)
        icon_scale = min(0.8, max(0.2, 0.15 * self.zoom_level))

        if self.position_icon:
            icon = scale_icon(self.position_icon, icon_scale)
            tinted = icon.copy()
            tint_color = (int(255 * (1 - depth_ratio)), 0, int(255 * depth_ratio))
            tinted.fill(tint_color, special_flags=pygame.BLEND_MULT)
            rect = tinted.get_rect(center=(ex, ey))
            self.screen.blit(tinted, rect)
        else:
            s = max(8, int(15 * icon_scale))
            cross_color = (int(255 * (1 - depth_ratio)), 0, int(255 * depth_ratio))
            pygame.draw.line(self.screen, cross_color, (ex-s, ey), (ex+s, ey), 2)
            pygame.draw.line(self.screen, cross_color, (ex, ey-s), (ex, ey+s), 2)

        y = WINDOW_HEIGHT - 80
        location = self.locator.get_location_name(self.temp_lon, self.temp_lat, 'ja')

        texts = [
            (f"震央: {location}", (255, 255, 255)),
            (f"M{self.temp_mag:.1f} (←→) 深度{self.temp_depth}km (↑↓)", (255, 255, 0)),
            ("左键放置 / Enter开始  |  Tab: 多震源", (180, 180, 180)),
        ]
        for text, color in texts:
            surf = self.font_cn.render(text, True, color)
            self.screen.blit(surf, (15, y))
            y += 25

    def draw_help(self):
        """绘制帮助信息"""
        if self.setting_mode:
            return
        helps = ["Space:暂停", "R:重置", "+/-:速度", "T:切换显示", "S:导出履歴"]
        y = WINDOW_HEIGHT - 30
        text = "  ".join(helps)
        surf = self.font_cn_small.render(text, True, (150, 150, 150))
        self.screen.blit(surf, (15, y))

    def draw_mode_button(self):
        """绘制右上角模式切换按钮"""
        btn_w, btn_h = 80, 30
        btn_x = WINDOW_WIDTH - btn_w - 10
        btn_y = 10
        self.mode_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        # 按钮背景
        pygame.draw.rect(self.screen, (40, 40, 60), self.mode_btn_rect)
        pygame.draw.rect(self.screen, (100, 100, 120), self.mode_btn_rect, 2)

        # 按钮文字
        text = "站点" if self.display_mode == MODE_STATION else "区域"
        surf = self.font_cn.render(text, True, (255, 255, 255))
        text_rect = surf.get_rect(center=self.mode_btn_rect.center)
        self.screen.blit(surf, text_rect)

    def draw_auto_zoom_button(self):
        """绘制右上角自动缩放按钮"""
        btn_w, btn_h = 100, 30
        btn_x = WINDOW_WIDTH - btn_w - 10
        btn_y = 50  # 在模式按钮下方
        self.auto_zoom_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        # 按钮颜色（根据状态）
        if self.auto_zoom_mode != "off":
            bg_color = (50, 100, 50)  # 绿色 - 启用
            border_color = (100, 200, 100)
        else:
            bg_color = (60, 60, 60)  # 灰色 - 禁用
            border_color = (120, 120, 120)

        # 按钮背景
        pygame.draw.rect(self.screen, bg_color, self.auto_zoom_btn_rect)
        pygame.draw.rect(self.screen, border_color, self.auto_zoom_btn_rect, 2)

        # 按钮文字
        if self.auto_zoom_mode == "waiting":
            text = "等待检测"
        elif self.auto_zoom_mode == "following_station":
            text = "追踪站点"
        elif self.auto_zoom_mode == "following_p":
            text = "追踪P波"
        elif self.auto_zoom_mode == "following_s":
            text = "追踪S波"
        elif self.auto_zoom_mode == "return_to_epicenter":
            text = "回到震央"
        else:
            text = "自动追踪"

        surf = self.font_cn_small.render(text, True, (255, 255, 255))
        text_rect = surf.get_rect(center=self.auto_zoom_btn_rect.center)
        self.screen.blit(surf, text_rect)

    def draw_wave_display_button(self):
        """绘制右上角波形显示切换按钮"""
        btn_w, btn_h = 100, 30
        btn_x = WINDOW_WIDTH - btn_w - 10
        btn_y = 90  # 在自动追踪按钮下方
        self.wave_display_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        # 按钮颜色
        bg_color = (60, 60, 80)
        border_color = (120, 120, 150)

        # 按钮背景
        pygame.draw.rect(self.screen, bg_color, self.wave_display_btn_rect)
        pygame.draw.rect(self.screen, border_color, self.wave_display_btn_rect, 2)

        # 按钮文字（显示当前状态）
        if self.show_true_waves and self.show_tracking_waves:
            text = "全部波形"
        elif self.show_tracking_waves:
            text = "追标波形"
        elif self.show_true_waves:
            text = "真实波形"
        else:
            text = "隐藏波形"

        surf = self.font_cn_small.render(text, True, (255, 255, 255))
        text_rect = surf.get_rect(center=self.wave_display_btn_rect.center)
        self.screen.blit(surf, text_rect)

    def reset_auto_tracking(self):
        """重置自动追踪状态"""
        self.auto_zoom_mode = "off"
        self.tracked_station = None
        self.max_detected_intensity = 0.0
        self.tracking_start_time = 0
        self.zoom_locked = False
        self.last_intensity_update_time = 0
        self.last_zoom_time = 0
        self.is_zooming = False
        self.waiting_for_return = False

    def check_final_report(self, dt: float):
        """检测震度稳定性并播放最终报音频（Scratch兼容）"""
        if not self.station_manager or not self.earthquake or not self.sound_manager:
            return

        # 收集所有震度 > 2.5 的站点数据（Scratch逻辑）
        intensity_snapshot = ""
        for station in self.station_manager.stations:
            if station.intensity > 2.5:
                intensity_snapshot += f"{station.intensity:.1f}"

        # 检查震度快照是否变化
        if intensity_snapshot == self.last_intensity_snapshot and intensity_snapshot != "":
            # 震度稳定，累积时间
            self.intensity_stable_time += dt
        else:
            # 震度变化，重置计时
            self.intensity_stable_time = 0
            self.last_intensity_snapshot = intensity_snapshot
            self.final_report_played = False

        # 检查是否满足最终报条件（Scratch公式：e^M * 0.3）
        import math
        threshold_time = math.exp(self.earthquake.magnitude) * 0.3

        if (self.intensity_stable_time > threshold_time and
            not self.final_report_played and
            intensity_snapshot != ""):
            # 播放最终报音频
            self.sound_manager.play('final_report', volume=0.8)
            self.final_report_played = True
            print(f"[最终报] 震度稳定 {self.intensity_stable_time:.1f}秒，播放最终报音频")

    def start_auto_tracking(self):
        """开始自动追踪（等待模式）"""
        if self.auto_zoom_enabled:
            self.auto_zoom_mode = "waiting"  # 改为等待模式
            self.tracking_start_time = 0
            self.max_detected_intensity = 0.0
            self.tracked_station = None
            self.zoom_locked = False
            self.last_intensity_update_time = 0
            self.last_zoom_time = 0
            self.is_zooming = False
            self.waiting_for_return = False
            print("[自动追踪] 启动 - 等待站点检测")

    def update_auto_tracking(self):
        """
        更新自动追踪逻辑（在每帧调用）- 真实EEW模式

        追踪模式切换：
        1. waiting: 等待站点检测到地震波
        2. following_station: 检测到震度3+站点，快速锁定异动区域
        3. following_p: 锁定后追踪P波扩散（间隔式平滑缩放）
        4. following_s: 大范围高震度，追踪S波扩散（间隔式平滑缩放）
        5. return_to_epicenter: 达到最大视野后回到震央（总结）
        """
        if not self.auto_zoom_enabled or self.auto_zoom_mode == "off":
            return

        # 只处理单震源模式
        if self.sim_mode != "single" or not self.earthquake:
            return

        current_time = self.earthquake.time
        epicenter_lat = self.earthquake.lat
        epicenter_lon = self.earthquake.lon

        # 获取P波和S波半径
        p_radius = self.earthquake.get_p_wave_radius()
        s_radius = self.earthquake.get_s_wave_radius()

        # 检查是否有震度3+的站点
        high_intensity_stations = []
        for (lat, lon), (intensity, is_s_wave) in self.station_intensities.items():
            if intensity >= 3.0:
                high_intensity_stations.append((lat, lon, intensity))

        # 模式切换逻辑
        if self.auto_zoom_mode == "waiting":
            # 等待模式：不做任何操作，等待站点检测
            # 检测到第一个震度3+站点 -> 立即切换到站点追踪
            if high_intensity_stations:
                # 找最高震度站点
                high_intensity_stations.sort(key=lambda x: x[2], reverse=True)
                target_lat, target_lon, target_intensity = high_intensity_stations[0]

                if target_intensity >= 3.0:
                    self.auto_zoom_mode = "following_station"
                    self.tracked_station = (target_lat, target_lon)
                    self.max_detected_intensity = target_intensity
                    self.zoom_locked = False

                    # 首次检测到站点时播放EEW警报音并启用追标波形显示
                    if not self.eew_alert_played and self.sound_manager:
                        self.sound_manager.play_eew()
                        self.eew_alert_played = True
                        self.tracking_wave_visible = True  # 启用追标波形显示
                        self.first_detection_time = self.earthquake.time  # 记录首次检测时间
                        print(f"[EEW] 站点检测到地震波 - 开始追标 (t={self.first_detection_time:.1f}s)")

                    print(f"[自动追踪] 切换到站点追踪模式 - 震度{intensity_to_scale(target_intensity)}")

        elif self.auto_zoom_mode == "following_station":
            # 站点追踪模式：智能锁定异动站点区域
            if high_intensity_stations:
                # 持续追踪最高震度站点
                high_intensity_stations.sort(key=lambda x: x[2], reverse=True)
                target_lat, target_lon, target_intensity = high_intensity_stations[0]

                # 更新追踪目标（如果有更高震度站点）
                if target_intensity > self.max_detected_intensity:
                    self.tracked_station = (target_lat, target_lon)
                    self.max_detected_intensity = target_intensity
                    self.zoom_locked = False  # 解锁缩放
                    self.last_intensity_update_time = current_time  # 更新时间戳
                    print(f"[自动追踪] 更新追踪站点 - 震度{intensity_to_scale(target_intensity)}")

                # 智能缩放：根据站点分布范围动态调整
                if not self.zoom_locked:
                    # 计算所有震度3+站点的边界框
                    all_lats = [lat for lat, lon, intensity in high_intensity_stations]
                    all_lons = [lon for lat, lon, intensity in high_intensity_stations]

                    if len(all_lats) >= 2:
                        # 多个站点：计算边界框并添加边距
                        min_lat = min(all_lats)
                        max_lat = max(all_lats)
                        min_lon = min(all_lons)
                        max_lon = max(all_lons)

                        # 添加20%边距
                        lat_margin = (max_lat - min_lat) * 0.2
                        lon_margin = (max_lon - min_lon) * 0.2

                        target_bounds = {
                            'min_lat': min_lat - lat_margin,
                            'max_lat': max_lat + lat_margin,
                            'min_lon': min_lon - lon_margin,
                            'max_lon': max_lon + lon_margin
                        }

                        # 快速过渡到目标边界
                        alpha = 0.5
                        for key in ['min_lat', 'max_lat', 'min_lon', 'max_lon']:
                            current = self.map_bounds[key]
                            target = target_bounds[key]
                            self.map_bounds[key] = current + (target - current) * alpha

                        # 计算缩放级别
                        default_lat_range = self.default_bounds['max_lat'] - self.default_bounds['min_lat']
                        current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
                        self.zoom_level = default_lat_range / current_lat_range

                        # 检查是否稳定（边界变化小于5%）
                        if abs(current - target) / default_lat_range < 0.05:
                            self.zoom_locked = True
                            self.last_intensity_update_time = current_time
                    else:
                        # 单个站点：适度缩放（更保守，避免放太大）
                        # 震度3-4: 1.3倍, 震度5+: 1.6倍, 震度6+: 2.0倍
                        if target_intensity >= 6.0:
                            zoom_factor = 2.0
                        elif target_intensity >= 5.0:
                            zoom_factor = 1.6
                        else:
                            zoom_factor = 1.3

                        # 快速锁定（alpha=0.5，快速响应）
                        self._zoom_to_station(self.tracked_station[0], self.tracked_station[1],
                                            zoom_factor, fast=True)

                        # 检查是否已锁定（zoom_level达到目标）
                        if self.zoom_level >= zoom_factor * 0.9:
                            self.zoom_locked = True
                            self.last_intensity_update_time = current_time

                # 锁定后如果2秒内没有新的更高震度站点，切换到追P波模式
                if self.zoom_locked and (current_time - self.last_intensity_update_time) > 2.0:
                    self.auto_zoom_mode = "following_p"
                    self.zoom_locked = False
                    self.last_zoom_time = 0  # 重置缩放时间，让第一次缩放立即执行
                    print(f"[自动追踪] 切换到P波追踪模式 - 站点区域已锁定，开始追P波扩散")

                # 如果大范围出现高震度（5个以上震度5+站点）-> 切换到S波追踪
                high_intensity_count = sum(1 for _, _, i in high_intensity_stations if i >= 5.0)
                if high_intensity_count >= 5:
                    self.auto_zoom_mode = "following_s"
                    self.zoom_locked = False
                    self.last_zoom_time = 0  # 重置缩放时间，让第一次缩放立即执行
                    print(f"[自动追踪] 切换到S波追踪模式 - 大范围高震度")

        elif self.auto_zoom_mode == "following_p":
            # P波追踪模式：间隔式平滑缩放（停一下 → 缓慢缩 → 停住）
            # 计算当前视野半径（km）
            current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
            current_view_radius_km = (current_lat_range / 2) * 111  # 半径 = 范围/2 * 111km/度

            # 检查是否已达到最大视野范围
            if current_view_radius_km >= self.max_view_radius_km:
                # 已达到最大范围，准备回到震央
                if not self.waiting_for_return:
                    # 第一次达到最大视野，开始等待
                    self.waiting_for_return = True
                    self.last_zoom_time = current_time
                    print(f"[P波追踪] 已达最大视野 {self.max_view_radius_km}km - 等待5秒后回到震央")

                # 等待5秒后回到震央
                if (current_time - self.last_zoom_time) > 5.0:
                    self.auto_zoom_mode = "return_to_epicenter"
                    self.is_zooming = False
                    self.waiting_for_return = False
                    print("[总结] 进入回到震央模式")
            else:
                # 间隔式缩放：停一下（2秒）→ 缓慢缩放 → 停住
                if not self.is_zooming:
                    # 等待中：检查是否到了下次缩放时间
                    if (current_time - self.last_zoom_time) >= self.zoom_interval:
                        # 开始缩放
                        self.is_zooming = True
                        self.last_zoom_time = current_time
                        print(f"[P波追踪] 开始缩放 - 当前视野半径{current_view_radius_km:.0f}km")
                else:
                    # 正在缩放中：平滑缩放到目标范围
                    view_radius_km = min(self.max_view_radius_km, max(200, p_radius * 1.3))
                    self._zoom_to_circle(epicenter_lat, epicenter_lon, view_radius_km, smooth=True)

                    # 检查是否缩放完成（bounds变化很小）
                    new_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
                    if abs(new_lat_range - current_lat_range) < 0.1:
                        # 缩放完成，停住
                        self.is_zooming = False
                        new_radius_km = (new_lat_range / 2) * 111
                        print(f"[P波追踪] 缩放完成 - 停住（视野半径{new_radius_km:.0f}km）")

            # 如果出现新的更高震度站点，切换回站点追踪
            if high_intensity_stations:
                high_intensity_stations.sort(key=lambda x: x[2], reverse=True)
                target_lat, target_lon, target_intensity = high_intensity_stations[0]
                if target_intensity > self.max_detected_intensity:
                    self.auto_zoom_mode = "following_station"
                    self.tracked_station = (target_lat, target_lon)
                    self.max_detected_intensity = target_intensity
                    self.last_intensity_update_time = current_time
                    self.is_zooming = False
                    print(f"[自动追踪] 检测到更高震度站点 - 切回站点追踪模式")

        elif self.auto_zoom_mode == "following_s":
            # S波追踪模式：间隔式平滑缩放（停一下 → 缓慢缩 → 停住）
            # 计算当前视野半径（km）
            current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
            current_view_radius_km = (current_lat_range / 2) * 111  # 半径 = 范围/2 * 111km/度

            # 检查是否已达到最大视野范围
            if current_view_radius_km >= self.max_view_radius_km:
                # 已达到最大范围，准备回到震央
                if not self.waiting_for_return:
                    # 第一次达到最大视野，开始等待
                    self.waiting_for_return = True
                    self.last_zoom_time = current_time
                    print(f"[S波追踪] 已达最大视野 {self.max_view_radius_km}km - 等待5秒后回到震央")

                # 等待5秒后回到震央
                if (current_time - self.last_zoom_time) > 5.0:
                    self.auto_zoom_mode = "return_to_epicenter"
                    self.is_zooming = False
                    self.waiting_for_return = False
                    print("[总结] 进入回到震央模式")
            else:
                # 间隔式缩放：停一下（2秒）→ 缓慢缩放 → 停住
                if not self.is_zooming:
                    # 等待中：检查是否到了下次缩放时间
                    if (current_time - self.last_zoom_time) >= self.zoom_interval:
                        # 开始缩放
                        self.is_zooming = True
                        self.last_zoom_time = current_time
                        print(f"[S波追踪] 开始缩放 - 当前视野半径{current_view_radius_km:.0f}km")
                else:
                    # 正在缩放中：平滑缩放到目标范围
                    view_radius_km = min(self.max_view_radius_km, max(100, s_radius * 1.3))
                    self._zoom_to_circle(epicenter_lat, epicenter_lon, view_radius_km, smooth=True)

                    # 检查是否缩放完成（bounds变化很小）
                    new_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
                    if abs(new_lat_range - current_lat_range) < 0.1:
                        # 缩放完成，停住
                        self.is_zooming = False
                        new_radius_km = (new_lat_range / 2) * 111
                        print(f"[S波追踪] 缩放完成 - 停住（视野半径{new_radius_km:.0f}km）")

        elif self.auto_zoom_mode == "return_to_epicenter":
            # 回到震央模式：缓慢缩放回震央附近
            if not self.is_zooming:
                print("[总结] 开始回到震央...")
                self.is_zooming = True

            # 缓慢缩放到震央（放大到2倍视野，聚焦震央区域）
            self._zoom_to_station(epicenter_lat, epicenter_lon, zoom_factor=2.0, fast=False)

            # 检查是否回到震央完成
            current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
            default_lat_range = self.default_bounds['max_lat'] - self.default_bounds['min_lat']
            target_lat_range = default_lat_range / 2.0

            if abs(current_lat_range - target_lat_range) < 0.1:
                # 回到震央完成，切换到off模式停止自动追踪
                if self.is_zooming:  # 只打印一次
                    print("[总结] 回到震央完成 - 模拟结束")
                    self.auto_zoom_mode = "off"  # 切换到off模式，停止自动追踪
                    self.is_zooming = False

    def _zoom_to_station(self, station_lat, station_lon, zoom_factor, fast=False):
        """
        缩放到指定站点（站点居中）

        Args:
            station_lat: 站点纬度
            station_lon: 站点经度
            zoom_factor: 缩放倍数（相对默认视野）
            fast: 是否快速响应
        """
        # 计算目标地图边界（站点居中）
        default_lat_range = self.default_bounds['max_lat'] - self.default_bounds['min_lat']
        default_lon_range = self.default_bounds['max_lon'] - self.default_bounds['min_lon']

        # 缩小视野范围
        target_lat_range = default_lat_range / zoom_factor
        target_lon_range = default_lon_range / zoom_factor

        target_bounds = {
            'min_lat': station_lat - target_lat_range / 2,
            'max_lat': station_lat + target_lat_range / 2,
            'min_lon': station_lon - target_lon_range / 2,
            'max_lon': station_lon + target_lon_range / 2
        }

        # 快速过渡（alpha=0.5）或平滑过渡（alpha=0.1）
        alpha = 0.5 if fast else 0.1

        for key in ['min_lat', 'max_lat', 'min_lon', 'max_lon']:
            current = self.map_bounds[key]
            target = target_bounds[key]
            self.map_bounds[key] = current + (target - current) * alpha

        # 计算缩放级别
        current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
        self.zoom_level = default_lat_range / current_lat_range

    def _zoom_to_circle(self, center_lat, center_lon, radius_km, smooth=False):
        """
        缩放视野以包含指定圆形区域

        Args:
            center_lat: 圆心纬度
            center_lon: 圆心经度
            radius_km: 半径（公里）
            smooth: 是否平滑过渡
        """
        from projection import latlon_to_xy_km, xy_km_to_latlon

        # 计算圆的km边界
        cx_km, cy_km = latlon_to_xy_km(center_lat, center_lon)

        # 留10%边距
        margin = 1.1
        x_min_km = cx_km - radius_km * margin
        x_max_km = cx_km + radius_km * margin
        y_min_km = cy_km - radius_km * margin
        y_max_km = cy_km + radius_km * margin

        # 转换回经纬度
        min_lat, _ = xy_km_to_latlon(0, y_min_km)
        max_lat, _ = xy_km_to_latlon(0, y_max_km)
        _, min_lon = xy_km_to_latlon(x_min_km, 0)
        _, max_lon = xy_km_to_latlon(x_max_km, 0)

        # 平滑过渡（线性插值）
        if smooth and hasattr(self, 'map_bounds'):
            alpha = 0.1  # 插值系数（越小越平滑）
            target_bounds = {
                'min_lat': min_lat,
                'max_lat': max_lat,
                'min_lon': min_lon,
                'max_lon': max_lon
            }
            for key in ['min_lat', 'max_lat', 'min_lon', 'max_lon']:
                current = self.map_bounds[key]
                target = target_bounds[key]
                self.map_bounds[key] = current + (target - current) * alpha
        else:
            self.map_bounds['min_lat'] = min_lat
            self.map_bounds['max_lat'] = max_lat
            self.map_bounds['min_lon'] = min_lon
            self.map_bounds['max_lon'] = max_lon

        # 计算缩放级别
        default_lat_range = self.default_bounds['max_lat'] - self.default_bounds['min_lat']
        current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
        self.zoom_level = default_lat_range / current_lat_range

    def auto_zoom_to_epicenter(self, lat, lon, magnitude):
        """
        自动缩放到震央区域（模拟EEW系统的自动聚焦）

        Args:
            lat: 震央纬度
            lon: 震央经度
            magnitude: 震级（用于确定缩放范围）
        """
        # 根据震级确定视野范围（度）
        # M6.0 -> ±2度, M7.0 -> ±3度, M8.0 -> ±5度
        range_deg = 1.5 + magnitude * 0.5
        range_deg = max(1.5, min(6.0, range_deg))  # 限制在1.5-6度之间

        # 设置新的地图边界（以震央为中心）
        self.map_bounds['min_lat'] = lat - range_deg
        self.map_bounds['max_lat'] = lat + range_deg
        self.map_bounds['min_lon'] = lon - range_deg * 1.2  # 经度稍微宽一点
        self.map_bounds['max_lon'] = lon + range_deg * 1.2

        # 计算缩放级别
        default_lat_range = self.default_bounds['max_lat'] - self.default_bounds['min_lat']
        current_lat_range = self.map_bounds['max_lat'] - self.map_bounds['min_lat']
        self.zoom_level = default_lat_range / current_lat_range

        print(f"[自动缩放] 震央: ({lat:.2f}, {lon:.2f}), M{magnitude:.1f}")
        print(f"[自动缩放] 缩放级别: {self.zoom_level:.2f}x, 范围: ±{range_deg:.1f}°")

    def zoom_map(self, mouse_pos, factor):
        """缩放地图，以鼠标位置为中心（km 平面等比例缩放）。"""
        # 手动缩放时立即取消所有自动追踪（最高优先级）
        if self.auto_zoom_mode != "off":
            self.reset_auto_tracking()
            print("[自动追踪] 滚轮操作 - 已取消所有镜头锁定")

        new_zoom = self.zoom_level * factor

        # 限制缩放范围：最小1.0（默认），最大15.0
        if new_zoom < 1.0 or new_zoom > 15.0:
            return

        x_min_km, x_max_km, y_min_km, y_max_km, ppk, x_off, y_off = self._view_km_params()
        x_span = max(1e-6, x_max_km - x_min_km)
        y_span = max(1e-6, y_max_km - y_min_km)
        map_w_px = x_span * ppk
        map_h_px = y_span * ppk
        if map_w_px <= 1e-6 or map_h_px <= 1e-6:
            return

        mx, my = mouse_pos
        mouse_x_ratio = (mx - x_off) / map_w_px
        mouse_y_ratio = (my - y_off) / map_h_px
        mouse_x_ratio = max(0.0, min(1.0, mouse_x_ratio))
        mouse_y_ratio = max(0.0, min(1.0, mouse_y_ratio))

        # 鼠标对应的世界坐标(km)
        anchor_x_km = x_min_km + mouse_x_ratio * x_span
        anchor_y_km = y_max_km - mouse_y_ratio * y_span

        new_x_span = x_span / factor
        new_y_span = y_span / factor

        new_x_min_km = anchor_x_km - mouse_x_ratio * new_x_span
        new_x_max_km = new_x_min_km + new_x_span
        new_y_max_km = anchor_y_km + mouse_y_ratio * new_y_span
        new_y_min_km = new_y_max_km - new_y_span

        # km 边界反算到经纬度边界
        min_lat, _ = xy_km_to_latlon(0.0, new_y_min_km)
        max_lat, _ = xy_km_to_latlon(0.0, new_y_max_km)
        _, min_lon = xy_km_to_latlon(new_x_min_km, 0.0)
        _, max_lon = xy_km_to_latlon(new_x_max_km, 0.0)

        self.map_bounds['min_lon'] = min_lon
        self.map_bounds['max_lon'] = max_lon
        self.map_bounds['min_lat'] = min_lat
        self.map_bounds['max_lat'] = max_lat

        self.zoom_level = new_zoom

    def draw_map_boundaries(self):
        """绘制日本地图边界（使用都道府县数据）"""
        land_color = (0x3B, 0x42, 0x38)  # #3B4238
        border_color = (0xD2, 0xD4, 0xD8)  # #D2D4D8
        for pref in self.prefectures:
            geom = pref.get('geometry', {})
            coords = geom.get('coordinates', [])
            geom_type = geom.get('type', '')

            if geom_type == 'Polygon':
                polys = [coords[0]]
            elif geom_type == 'MultiPolygon':
                polys = [c[0] for c in coords]
            else:
                continue

            for poly in polys:
                points = [self.latlon_to_screen(lat, lon) for lon, lat in poly]
                if len(points) >= 3:
                    pygame.draw.polygon(self.screen, land_color, points)
                    pygame.draw.polygon(self.screen, border_color, points, 1)

    def handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB and self.setting_mode:
                    # 切换单/多模式
                    self.sim_mode = "multi" if self.sim_mode == "single" else "single"
                    self.earthquake = None
                    self.reset_multi_setup()
                    continue

                if self.setting_mode:
                    if self.sim_mode == "single":
                        if event.key == pygame.K_UP:
                            self.temp_depth = min(700, self.temp_depth + 10)
                        elif event.key == pygame.K_DOWN:
                            self.temp_depth = max(0, self.temp_depth - 10)
                        elif event.key == pygame.K_RIGHT:
                            self.temp_mag = min(9.5, self.temp_mag + 0.1)
                        elif event.key == pygame.K_LEFT:
                            self.temp_mag = max(1.0, self.temp_mag - 0.1)
                        elif event.key == pygame.K_RETURN:
                            # 保存真实震央位置（不随EEW修正而改变）
                            self.true_epicenter_lat = self.temp_lat
                            self.true_epicenter_lon = self.temp_lon

                            # 创建EEW追标器
                            if self.eew_tracking_enabled:
                                self.eew_tracker = EEWTracker(
                                    self.temp_lat, self.temp_lon,
                                    self.temp_depth, self.temp_mag,
                                    enabled=True
                                )
                                # 使用追标器的初始值创建地震
                                lat, lon, depth, mag = self.eew_tracker.get_current_values()
                                self.earthquake = Earthquake(lat, lon, depth, mag)
                            else:
                                self.eew_tracker = None
                                self.earthquake = Earthquake(
                                    self.temp_lat, self.temp_lon,
                                    self.temp_depth, self.temp_mag
                                )

                            # 启动自动追踪（P波跟随模式）
                            self.start_auto_tracking()

                            # 不在开始时播放EEW警报音,等站点检测到地震波时才播放
                            # 重置音频播报状态
                            if self.sound_manager:
                                self.sound_manager.reset_announcement()

                            self.setting_mode = False
                            self.region_intensities = {}
                            self.max_intensity = 0
                            self.detected_regions = []
                            self.intensity4_played = False
                            self.intensity7_played = False
                            self.max_triggered_intensity = 0.0
                            self.alert_animations.clear()
                            self.eew_alert_played = False  # 重置EEW警报音播放状态
                            self.tracking_wave_visible = False  # 重置追标波形显示状态
                            self.triggered_intensity_sounds = set()  # 重置音效触发记录

                            # 重置站点管理器
                            if self.station_manager:
                                self.station_manager.reset()

                            # 清空履歴记录，开始新的记录
                            if hasattr(self, 'history'):
                                self.history.clear()
                                print("[履歴] 开始新的地震记录")
                        elif event.key == pygame.K_r:
                            self.temp_lat = 35.7
                            self.temp_lon = 139.7
                            self.temp_depth = 10
                            self.temp_mag = 6.0
                    else:
                        # 多震源设置阶段
                        if event.key == pygame.K_UP:
                            self.temp_depth = min(700, self.temp_depth + 5)
                            # 同步更新所有已放置震源点的深度
                            for src in self.multi_sources:
                                src.depth = self.temp_depth
                                src.eq.depth = self.temp_depth
                        elif event.key == pygame.K_DOWN:
                            self.temp_depth = max(0, self.temp_depth - 5)
                            # 同步更新所有已放置震源点的深度
                            for src in self.multi_sources:
                                src.depth = self.temp_depth
                                src.eq.depth = self.temp_depth
                        elif event.key == pygame.K_RIGHT:
                            self.temp_mag = min(9.5, self.temp_mag + 0.1)
                            # 同步更新所有已放置震源点的震级
                            for src in self.multi_sources:
                                src.magnitude = self.temp_mag
                                src.eq.magnitude = self.temp_mag
                        elif event.key == pygame.K_LEFT:
                            self.temp_mag = max(1.0, self.temp_mag - 0.1)
                            # 同步更新所有已放置震源点的震级
                            for src in self.multi_sources:
                                src.magnitude = self.temp_mag
                                src.eq.magnitude = self.temp_mag
                        elif event.key == pygame.K_c:
                            self.rupture_velocity = max(0.5, self.rupture_velocity - 0.2)
                        elif event.key == pygame.K_v:
                            self.rupture_velocity = min(10.0, self.rupture_velocity + 0.2)
                        elif event.key == pygame.K_d and self.multi_state == "choose_start":
                            if self.multi_direction == "forward":
                                self.multi_direction = "backward"
                            elif self.multi_direction == "backward":
                                self.multi_direction = "both"
                            else:
                                self.multi_direction = "forward"
                        elif event.key == pygame.K_r:
                            self.reset_multi_setup()
                        elif event.key == pygame.K_RETURN:
                            if self.multi_state == "draw_fault" and len(self.fault_line) >= 2:
                                self.multi_state = "place_sources"
                            elif self.multi_state == "place_sources" and len(self.multi_sources) >= 1:
                                self.multi_state = "choose_start"
                            elif self.multi_state == "choose_start" and len(self.multi_sources) >= 1:
                                self.start_multi_simulation()
                else:
                    if event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r:
                        self.earthquake = None
                        self.eew_tracker = None  # 重置追标器
                        self.true_epicenter_lat = None  # 重置真实震央位置
                        self.true_epicenter_lon = None
                        self.reset_auto_tracking()  # 重置追踪状态
                        self.setting_mode = True
                        self.station_intensities = {}
                        self.region_max_intensities = {}
                        self.max_intensity = 0
                        self.intensity4_played = False
                        self.intensity7_played = False
                        self.max_triggered_intensity = 0.0
                        self.alert_animations.clear()
                        self.eew_alert_played = False  # 重置EEW警报音播放状态
                        self.tracking_wave_visible = False  # 重置追标波形显示状态
                        self.first_detection_time = None  # 重置首次检测时间
                        self.triggered_intensity_sounds = set()  # 重置音效触发记录

                        # 重置站点管理器
                        if self.station_manager:
                            self.station_manager.reset()

                        # 重置地图缩放
                        self.map_bounds = MAP_BOUNDS.copy()
                        self.zoom_level = 1.0

                        # 清空履歴记录
                        if hasattr(self, 'history'):
                            self.history.clear()
                            print("[履歴] 已清空历史记录")

                        if self.sim_mode == "multi":
                            self.reset_multi_setup()
                    elif event.key == pygame.K_s:
                        # S键：导出履歴记录
                        if hasattr(self, 'history') and self.earthquake:
                            import time
                            filename = f"earthquake_history_{int(time.time())}.txt"
                            self.history.export_to_file(filename)
                            summary = self.history.get_summary()
                            print(f"[总结] 时长: {summary['duration']:.1f}秒, "
                                  f"最大震度: {summary['max_intensity']:.1f}, "
                                  f"记录数: {summary['total_records']}")
                    elif event.key == pygame.K_t:
                        self.display_mode = MODE_STATION if self.display_mode == MODE_REGION else MODE_REGION
                    elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                        self.time_scale = min(10, self.time_scale * 1.5)
                    elif event.key == pygame.K_MINUS:
                        self.time_scale = max(0.1, self.time_scale / 1.5)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键
                    # 检查是否点击了模式按钮
                    if hasattr(self, 'mode_btn_rect') and self.mode_btn_rect.collidepoint(event.pos):
                        self.display_mode = MODE_STATION if self.display_mode == MODE_REGION else MODE_REGION
                    # 检查是否点击了自动追踪按钮
                    elif hasattr(self, 'auto_zoom_btn_rect') and self.auto_zoom_btn_rect.collidepoint(event.pos):
                        if self.auto_zoom_mode == "off" and not self.setting_mode:
                            # 重新启动自动追踪
                            self.start_auto_tracking()
                        else:
                            # 禁用自动追踪
                            self.reset_auto_tracking()
                    # 检查是否点击了波形显示按钮
                    elif hasattr(self, 'wave_display_btn_rect') and self.wave_display_btn_rect.collidepoint(event.pos):
                        # 循环切换显示模式
                        if self.show_true_waves and self.show_tracking_waves:
                            # 全部 -> 只追标
                            self.show_true_waves = False
                            self.show_tracking_waves = True
                        elif not self.show_true_waves and self.show_tracking_waves:
                            # 只追标 -> 只真实
                            self.show_true_waves = True
                            self.show_tracking_waves = False
                        elif self.show_true_waves and not self.show_tracking_waves:
                            # 只真实 -> 全部
                            self.show_true_waves = True
                            self.show_tracking_waves = True
                    elif self.setting_mode:
                        lat, lon = self.screen_to_latlon(*event.pos)
                        if self.sim_mode == "single":
                            self.temp_lat = lat
                            self.temp_lon = lon
                        else:
                            if self.multi_state == "draw_fault":
                                self.fault_line.append((lat, lon))
                            elif self.multi_state == "place_sources":
                                snap_lat, snap_lon = self.project_to_fault(lat, lon)
                                self.multi_sources.append(RuptureSource(snap_lat, snap_lon, self.temp_depth, self.temp_mag))
                            elif self.multi_state == "choose_start" and self.multi_sources:
                                # 选择最近的震源为起点
                                best_idx = 0
                                best_d = float("inf")
                                for i, src in enumerate(self.multi_sources):
                                    d = math.hypot(src.lat - lat, src.lon - lon)
                                    if d < best_d:
                                        best_d = d
                                        best_idx = i
                                self.multi_start_source = self.multi_sources[best_idx]
                elif event.button == 3:  # 右键
                    if self.setting_mode and self.sim_mode == "multi":
                        if self.multi_state == "draw_fault" and self.fault_line:
                            self.fault_line.pop()
                        elif self.multi_state == "place_sources" and self.multi_sources:
                            self.multi_sources.pop()
                    elif not self.setting_mode and self.sim_mode == "single":
                        # 只有单震源模式下才允许右键重置
                        self.earthquake = None
                        self.setting_mode = True
                        self.station_intensities = {}
                        self.region_max_intensities = {}
                        self.intensity4_played = False
                        self.intensity7_played = False
                        self.max_triggered_intensity = 0.0
                        self.alert_animations.clear()
                        self.eew_alert_played = False  # 重置EEW警报音播放状态
                        self.tracking_wave_visible = False  # 重置追标波形显示状态
                        self.first_detection_time = None  # 重置首次检测时间
                        self.triggered_intensity_sounds = set()  # 重置音效触发记录
                        # 重置站点管理器
                        if self.station_manager:
                            self.station_manager.reset()
                elif event.button == 4:  # 滚轮向上 - 放大
                    self.zoom_map(event.pos, 1.2)
                elif event.button == 5:  # 滚轮向下 - 缩小
                    self.zoom_map(event.pos, 0.8)

            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    self.zoom_map(pygame.mouse.get_pos(), 1.2)
                elif event.y < 0:
                    self.zoom_map(pygame.mouse.get_pos(), 0.8)

    def run(self):
        """主循环"""
        self.station_intensities = {}
        self.region_max_intensities = {}

        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            self.handle_events()

            # 更新
            if not self.paused:
                if self.sim_mode == "single" and self.earthquake:
                    self.earthquake.update(dt * self.time_scale)

                    # 先计算站点震度（用于驱动EEW追标器）
                    self.calculate_station_intensities()

                    # 新增：更新站点管理器（返回检测到的震度等级）
                    if self.station_manager:
                        detected_levels = self.station_manager.update(
                            self.earthquake,
                            self.earthquake.time,
                            dt * self.time_scale  # 传递dt参数用于渐进式增长
                        )

                        # 从新站点系统更新区域震度（用于区域填色）
                        self.update_region_intensities_from_new_stations()

                        # 全局音效触发逻辑：每个震度等级只播放一次
                        if self.sound_manager and detected_levels:
                            new_levels = detected_levels - self.triggered_intensity_sounds
                            if new_levels:
                                # 从低到高排序播放
                                for level in sorted(new_levels):
                                    sound_name = f'intensity_{level}'
                                    self.sound_manager.play(sound_name, volume=0.8)
                                    self.triggered_intensity_sounds.add(level)

                        # 同步最大震度到主系统
                        station_max_intensity = max(
                            [s.intensity for s in self.station_manager.stations],
                            default=-3
                        )
                        if station_max_intensity > self.max_intensity:
                            self.max_intensity = station_max_intensity

                        # 音频增长逻辑：检测震度稳定性并播放最终报（Scratch兼容）
                        self.check_final_report(dt * self.time_scale)

                        # 记录站点数据到履歴（用于总结）
                        self.history.record_stations(
                            self.earthquake.time,
                            self.station_manager.stations
                        )

                    # 新增：更新EEW警报框
                    if hasattr(self, 'eew_alert_box') and self.station_manager:
                        self.eew_alert_box.update(self.earthquake, self.station_manager, dt)

                    # 更新EEW追标器（站点驱动）
                    if self.eew_tracker:
                        # 统计检测到地震波的站点数（震度>=3）
                        detected_station_count = sum(
                            1 for (_, _), (intensity, _) in self.station_intensities.items()
                            if intensity >= 3.0
                        )

                        # 站点驱动修正
                        was_revised = self.eew_tracker.update(detected_station_count, self.earthquake.time)
                        if was_revised:
                            # 地震信息被修正，更新地震对象并重新计算震度
                            lat, lon, depth, mag = self.eew_tracker.get_current_values()
                            self.earthquake.lat = lat
                            self.earthquake.lon = lon
                            self.earthquake.depth = depth
                            self.earthquake.magnitude = mag

                            # 播放"訂正"音频
                            if self.sound_manager and self.eew_tracker.consume_correction_flag():
                                self.sound_manager.play('correction', volume=0.8)

                            # 重新计算站点震度（基于修正后的地震参数）
                            self.calculate_station_intensities()

                    # 更新自动追踪
                    self.update_auto_tracking()

                elif self.sim_mode == "multi" and self.multi_manager:
                    self.multi_manager.update(dt * self.time_scale)
                    self.calculate_station_intensities()

            # 绘制
            self.screen.fill((0x2B, 0x36, 0x45))  # 海洋颜色 #2B3645

            # 先绘制地图边界（两种模式共用）
            self.draw_map_boundaries()

            # 绘制区域填色（两种模式共用）
            if not self.setting_mode:
                self.draw_regions_with_intensity(fill_only=True)

            # 站点模式：绘制站点
            if self.display_mode == MODE_STATION:
                # 绘制新站点系统（1748个观测站，带渐进式增长）
                if hasattr(self, 'station_manager') and self.station_manager and self.earthquake and not self.setting_mode:
                    self.station_manager.render(self.screen, self, self.station_icons)

                # 旧站点系统（已禁用，使用旧震度计算逻辑）
                # self.draw_stations()
            # 区域模式：绘制区域震度图标（z-order高于站点）
            else:
                self.draw_regions_with_intensity(icons_only=True)

            self.draw_wave_circles()
            self.draw_alert_circles()

            # 新增：绘制EEW警报框
            if hasattr(self, 'eew_alert_box') and not self.setting_mode:
                self.eew_alert_box.render(self.screen, self.earthquake, self.locator)

            self.draw_earthquake_info()
            self.draw_setting_info()
            self.draw_help()
            self.draw_mode_button()
            self.draw_auto_zoom_button()  # 绘制自动追踪按钮
            self.draw_wave_display_button()  # 绘制波形显示按钮

            pygame.display.flip()

        pygame.quit()

if __name__ == "__main__":
    sim = EarthquakeSimulator()
    sim.run()
