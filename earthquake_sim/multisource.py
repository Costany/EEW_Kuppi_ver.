"""多震源管理模块：负责断层折线投影、破裂调度与震度聚合。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from earthquake import Earthquake
from intensity import calc_jma_intensity
from projection import latlon_to_xy_km


@dataclass
class RuptureSource:
    lat: float
    lon: float
    depth: float
    magnitude: float
    weight: float = 1.0
    activate_at: Optional[float] = 0.0  # 秒
    distance_on_fault: float = 0.0  # km
    eq: Earthquake = field(init=False)
    active: bool = False

    def __post_init__(self):
        self.eq = Earthquake(self.lat, self.lon, self.depth, self.magnitude)


class MultiSourceManager:
    """管理多震源破裂与波传播。"""

    def __init__(self, polyline: Optional[List[Tuple[float, float]]] = None, rupture_velocity: float = 2.5):
        self.polyline: List[Tuple[float, float]] = polyline or []
        self.sources: List[RuptureSource] = []
        self.rupture_velocity = max(0.1, rupture_velocity)
        self.time = 0.0
        self.direction: str = "forward"  # forward / backward / both
        self.start_source: RuptureSource | None = None

    # 数据配置 -----------------------------------------------------
    def set_sources(self, sources: List[RuptureSource]):
        self.sources = sources
        self.time = 0.0
        for src in self.sources:
            src.active = False
            src.eq.time = 0.0

    def set_start_source(self, source: RuptureSource | None):
        self.start_source = source

    def set_direction(self, direction: str):
        if direction in ("forward", "backward", "both"):
            self.direction = direction

    def set_polyline(self, polyline: List[Tuple[float, float]]):
        self.polyline = polyline

    # 破裂时间计算 -------------------------------------------------
    def _polyline_km(self) -> Tuple[List[Tuple[float, float]], List[float]]:
        """返回折线各点 km 坐标与累积里程。"""
        km_points = [latlon_to_xy_km(lat, lon) for lat, lon in self.polyline]
        cumulative = [0.0]
        for i in range(1, len(km_points)):
            x0, y0 = km_points[i - 1]
            x1, y1 = km_points[i]
            cumulative.append(cumulative[-1] + math.hypot(x1 - x0, y1 - y0))
        return km_points, cumulative

    def _project_distance_on_fault(self, lat: float, lon: float) -> float:
        """计算点在折线上的投影距离（km）。"""
        if len(self.polyline) < 2:
            return 0.0
        km_points, cumulative = self._polyline_km()
        px, py = latlon_to_xy_km(lat, lon)
        best_dist = 0.0
        best_d2 = float("inf")
        for i in range(len(km_points) - 1):
            (x0, y0), (x1, y1) = km_points[i], km_points[i + 1]
            vx, vy = x1 - x0, y1 - y0
            seg_len2 = vx * vx + vy * vy
            if seg_len2 <= 1e-9:
                continue
            t = ((px - x0) * vx + (py - y0) * vy) / seg_len2
            t_clamped = max(0.0, min(1.0, t))
            proj_x = x0 + t_clamped * vx
            proj_y = y0 + t_clamped * vy
            d2 = (proj_x - px) ** 2 + (proj_y - py) ** 2
            if d2 < best_d2:
                best_d2 = d2
                along = math.hypot(proj_x - x0, proj_y - y0)
                best_dist = cumulative[i] + along
        return best_dist

    def _sort_sources_by_fault(self) -> List[RuptureSource]:
        if not self.sources:
            return []
        if len(self.polyline) < 2:
            # 回退：按经度排序，近似东西向
            for src in self.sources:
                src.distance_on_fault = src.lon
            return sorted(self.sources, key=lambda s: s.distance_on_fault)
        for src in self.sources:
            src.distance_on_fault = self._project_distance_on_fault(src.lat, src.lon)
        return sorted(self.sources, key=lambda s: s.distance_on_fault)

    def recompute_activation_times(self):
        """根据起点、方向和破裂速度分配各源的激活时间。"""
        ordered = self._sort_sources_by_fault()
        if not ordered:
            return
        self.sources = ordered

        # 找到起点震源（排序后）
        if self.start_source is None:
            start_src = self.sources[0]
        else:
            start_src = self.start_source

        start_dist = start_src.distance_on_fault

        for src in self.sources:
            dist = src.distance_on_fault
            src.active = False
            src.eq.time = 0.0
            if src is start_src:
                src.activate_at = 0.0
                continue
            if self.direction == "forward":
                if dist < start_dist:
                    src.activate_at = None
                else:
                    src.activate_at = (dist - start_dist) / self.rupture_velocity
            elif self.direction == "backward":
                if dist > start_dist:
                    src.activate_at = None
                else:
                    src.activate_at = (start_dist - dist) / self.rupture_velocity
            else:  # both
                src.activate_at = abs(dist - start_dist) / self.rupture_velocity

    # 运行与查询 ---------------------------------------------------
    def update(self, dt: float):
        """推进时间，更新已激活震源的波半径。"""
        self.time += dt
        for src in self.sources:
            if src.activate_at is None:
                continue
            if self.time >= src.activate_at:
                if not src.active:
                    src.active = True
                    src.eq.time = self.time - src.activate_at
                else:
                    src.eq.update(dt)

    def get_wave_circles(self) -> List[dict]:
        """返回当前已激活震源的波前信息。"""
        circles = []
        for src in self.sources:
            if not src.active:
                continue
            circles.append(
                {
                    "lat": src.lat,
                    "lon": src.lon,
                    "p_radius": src.eq.get_p_wave_radius(),
                    "s_radius": src.eq.get_s_wave_radius(),
                }
            )
        return circles

    def calc_intensity(self, lat: float, lon: float, amp: float = 1.0) -> tuple[float, bool]:
        """计算给定点的最大震度，返回 (intensity, is_s_wave)。"""
        max_intensity = 0.0
        max_is_s = False
        bai = (amp * 4 + amp * amp) / 5.0

        for src in self.sources:
            if not src.active:
                continue
            epicentral_dist = src.eq.get_epicentral_distance(lat, lon)
            s_intensity = calc_jma_intensity(src.eq.magnitude, src.eq.depth, epicentral_dist, bai=bai)
            p_intensity = s_intensity / 1.5 - 0.5

            s_radius = src.eq.get_s_wave_radius()
            p_radius = src.eq.get_p_wave_radius()

            if epicentral_dist <= s_radius and s_intensity >= 0.5:
                if s_intensity > max_intensity:
                    max_intensity = s_intensity
                    max_is_s = True
            elif epicentral_dist <= p_radius and p_intensity >= 0.5:
                if p_intensity > max_intensity:
                    max_intensity = p_intensity
                    max_is_s = False

        return max_intensity, max_is_s
