"""日本地图渲染模块"""
import json
import os
import pygame
from typing import Tuple, Dict, List, Optional

class Prefecture:
    """县/区域数据"""
    def __init__(self, name: str, coords: List, properties: Dict = None):
        self.name = name
        self.coords = coords  # [(lon, lat), ...]
        self.properties = properties or {}
        self.max_intensity = -3  # 区域内最大震度
        self.fill_color = None  # 填充颜色

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取边界范围 (min_lat, max_lat, min_lon, max_lon)"""
        lats = [lat for lon, lat in self.coords]
        lons = [lon for lon, lat in self.coords]
        return (min(lats), max(lats), min(lons), max(lons))


class MapRenderer:
    def __init__(self, geojson_path: str = None):
        """加载地图数据"""
        self.polygons = []
        self.prefectures: List[Prefecture] = []  # 县级区域列表
        if geojson_path and os.path.exists(geojson_path):
            self.load_geojson(geojson_path)

    def load_geojson(self, path: str):
        """从GeoJSON加载多边形"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for feature in data.get('features', []):
            geom = feature.get('geometry', {})
            geom_type = geom.get('type', '')
            coords = geom.get('coordinates', [])
            properties = feature.get('properties', {})

            # 获取区域名称
            name = properties.get('name', properties.get('震央地名', 'Unknown'))

            if geom_type == 'Polygon':
                self.polygons.append(coords[0])
                self.prefectures.append(Prefecture(name, coords[0], properties))
            elif geom_type == 'MultiPolygon':
                for poly in coords:
                    self.polygons.append(poly[0])
                    self.prefectures.append(Prefecture(name, poly[0], properties))

    def update_prefecture_intensities(self, station_manager):
        """更新县级区域的震度（根据区域内站点最大震度）"""
        for prefecture in self.prefectures:
            bounds = prefecture.get_bounds()
            max_intensity = station_manager.get_max_intensity_in_region(bounds)
            prefecture.max_intensity = max_intensity

            # 根据震度设置填充颜色
            prefecture.fill_color = self._get_intensity_fill_color(max_intensity)

    def _get_intensity_fill_color(self, intensity: float) -> Optional[Tuple[int, int, int, int]]:
        """根据震度获取填充颜色（RGBA）"""
        if intensity < 0:
            return None  # 不填充
        elif intensity < 1:
            return None  # 震度0不填充
        elif intensity < 2:
            return (100, 150, 255, 80)   # 震度1 浅蓝
        elif intensity < 3:
            return (50, 100, 200, 100)   # 震度2 蓝
        elif intensity < 4:
            return (50, 255, 50, 120)    # 震度3 绿/黄
        elif intensity < 5:
            return (255, 200, 0, 140)    # 震度4 橙黄
        elif intensity < 5.5:
            return (255, 150, 0, 160)    # 震度5弱 橙
        elif intensity < 6:
            return (255, 50, 0, 180)     # 震度5强 红橙
        elif intensity < 6.5:
            return (255, 0, 0, 200)      # 震度6弱 红
        elif intensity < 7:
            return (200, 0, 100, 220)    # 震度6强 紫红
        else:
            return (150, 0, 150, 240)    # 震度7 紫

    def draw(self, screen, latlon_to_screen_func, color=(60, 60, 80)):
        """绘制地图边界"""
        for polygon in self.polygons:
            if len(polygon) < 3:
                continue
            points = []
            for lon, lat in polygon:
                x, y = latlon_to_screen_func(lat, lon)
                points.append((x, y))
            if len(points) >= 3:
                pygame.draw.polygon(screen, color, points, 1)

    def draw_filled(self, screen, latlon_to_screen_func):
        """绘制填充的县级地图"""
        for prefecture in self.prefectures:
            if prefecture.fill_color is None:
                continue

            # 转换坐标
            points = []
            for lon, lat in prefecture.coords:
                x, y = latlon_to_screen_func(lat, lon)
                points.append((int(x), int(y)))

            if len(points) >= 3:
                # 创建临时surface用于半透明填充
                temp_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(temp_surface, prefecture.fill_color, points)
                screen.blit(temp_surface, (0, 0))
