#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EEW追标模式 - 模拟紧急地震速报的动态修正过程

真实的EEW系统会在地震发生后不断更新震级、震源位置等信息
本模块模拟这种"追标"（追踪修正）过程，让模拟器更真实

简化版B-Δ法：站点数越多，收敛越快
"""
import random


class EEWTracker:
    """
    EEW追标器 - 模拟地震信息的动态修正

    工作原理：
    1. 初始发布的信息可能不准确（故意加入误差）
    2. 随着检测到的站点数增加，逐步修正为真实值
    3. 每次修正触发"訂正"（订正）通知
    """

    def __init__(self, true_lat, true_lon, true_depth, true_mag, enabled=True):
        """
        初始化EEW追标器（站点驱动模式）

        Args:
            true_lat: 真实震央纬度
            true_lon: 真实震央经度
            true_depth: 真实震源深度 (km)
            true_mag: 真实震级
            enabled: 是否启用追标模式
        """
        self.enabled = enabled

        # 真实值
        self.true_lat = true_lat
        self.true_lon = true_lon
        self.true_depth = true_depth
        self.true_mag = true_mag

        # 当前报告值（初始值有较大误差）
        if enabled:
            # 初始位置误差：±0.3-0.8度（较大偏差）
            lat_error = random.uniform(-0.8, 0.8)
            lon_error = random.uniform(-0.8, 0.8)
            self.current_lat = true_lat + lat_error
            self.current_lon = true_lon + lon_error

            # 初始深度误差：±10-30km（较大偏差）
            depth_error = random.uniform(-30, 30)
            self.current_depth = max(0, true_depth + depth_error)

            # 初始震级误差：±0.3-0.8
            mag_error = random.uniform(-0.8, 0.8)
            self.current_mag = max(1.0, min(9.5, true_mag + mag_error))
        else:
            # 禁用时直接使用真实值
            self.current_lat = true_lat
            self.current_lon = true_lon
            self.current_depth = true_depth
            self.current_mag = true_mag

        # 追标状态（站点驱动模式）
        self.revision_count = 0  # 修正次数
        self.last_detected_station_count = 0  # 上次检测到的站点数
        self.convergence_threshold = 0.05  # 收敛阈值（位置0.05度，震级0.1，深度5km）

        # 当前误差（用于逐步收敛）
        self.current_lat_error = lat_error if enabled else 0
        self.current_lon_error = lon_error if enabled else 0
        self.current_depth_error = depth_error if enabled else 0
        self.current_mag_error = mag_error if enabled else 0

        # 是否需要播放"訂正"音频
        self.needs_correction_announcement = False

        # 推翻重来阈值（当误差过大时才推翻）
        self.overthrow_mag_threshold = 1.0  # 震级误差>1.0时推翻
        self.overthrow_depth_threshold = 30  # 深度误差>30km时推翻

        print(f"[EEW追标] {'启用' if enabled else '禁用'}")
        if enabled:
            print(f"  初始值: ({self.current_lat:.2f}, {self.current_lon:.2f}), "
                  f"{self.current_depth:.0f}km, M{self.current_mag:.1f}")
            print(f"  真实值: ({self.true_lat:.2f}, {self.true_lon:.2f}), "
                  f"{self.true_depth:.0f}km, M{self.true_mag:.1f}")

    def update(self, detected_station_count, elapsed_time):
        """
        更新追标状态（站点驱动模式 - 简化版B-Δ法）

        站点数越多，收敛越快（模拟多站点定位的精度提升）

        Args:
            detected_station_count: 当前检测到地震波的站点数（震度>=3）
            elapsed_time: 地震发生后经过的时间（秒）

        Returns:
            bool: 是否发生了修正
        """
        if not self.enabled:
            return False

        # 检查是否已收敛（接近真实值）
        if self.is_converged():
            return False

        # 只在检测到新站点时才修正（站点数增加）
        # 或者每检测到5个新站点修正一次
        station_increase = detected_station_count - self.last_detected_station_count

        # 至少需要3个站点才开始修正
        if detected_station_count < 3:
            return False

        # 站点数增加至少5个或首次达到3个站点时才修正
        should_correct = False
        if detected_station_count >= 3 and self.revision_count == 0:
            # 首次修正：检测到至少3个站点
            should_correct = True
        elif station_increase >= 5:
            # 后续修正：每增加5个站点修正一次
            should_correct = True

        if not should_correct:
            return False

        # 更新站点计数
        self.last_detected_station_count = detected_station_count
        self.revision_count += 1

        # 检查是否需要推翻重来（误差过大）
        mag_error_abs = abs(self.current_mag_error)
        depth_error_abs = abs(self.current_depth_error)

        if mag_error_abs > self.overthrow_mag_threshold or depth_error_abs > self.overthrow_depth_threshold:
            # 推翻重来：意识到震级或深度完全错误
            self.current_lat_error = random.uniform(-0.5, 0.5)
            self.current_lon_error = random.uniform(-0.5, 0.5)
            self.current_depth_error = random.uniform(-20, 20)
            self.current_mag_error = random.uniform(-0.5, 0.5)
            print(f"[EEW追标] 第{self.revision_count}次修正 - **推翻重来** (站点:{detected_station_count}, t={elapsed_time:.1f}s)")
            print(f"  原因: 震级误差{mag_error_abs:.1f}或深度误差{depth_error_abs:.0f}km过大")
        else:
            # 正常修正：误差逐步收敛
            # 站点越多，修正幅度越大（更有信心）- 简化版B-Δ法
            if detected_station_count >= 20:
                decay_rate = random.uniform(0.4, 0.6)  # 大量站点：快速收敛
            elif detected_station_count >= 10:
                decay_rate = random.uniform(0.3, 0.5)  # 较多站点：适度收敛
            else:
                decay_rate = random.uniform(0.2, 0.4)  # 少量站点：缓慢收敛

            self.current_lat_error *= (1 - decay_rate)
            self.current_lon_error *= (1 - decay_rate)
            self.current_depth_error *= (1 - decay_rate)
            self.current_mag_error *= (1 - decay_rate)

        # 应用误差到当前值
        self.current_lat = self.true_lat + self.current_lat_error
        self.current_lon = self.true_lon + self.current_lon_error
        self.current_depth = max(0, self.true_depth + self.current_depth_error)
        self.current_mag = max(1.0, min(9.5, self.true_mag + self.current_mag_error))

        # 标记需要播放"訂正"音频
        self.needs_correction_announcement = True

        print(f"[EEW追标] 第{self.revision_count}次修正 (站点:{detected_station_count}, t={elapsed_time:.1f}s)")
        print(f"  修正后: ({self.current_lat:.2f}, {self.current_lon:.2f}), "
              f"{self.current_depth:.0f}km, M{self.current_mag:.1f}")

        return True

    def _lerp(self, current, target, t):
        """线性插值"""
        return current + (target - current) * t

    def is_converged(self):
        """
        检查是否已收敛到真实值

        Returns:
            bool: 是否已收敛（误差小于阈值）
        """
        if not self.enabled:
            return True

        # 检查各项误差是否小于阈值
        lat_error_abs = abs(self.current_lat_error)
        lon_error_abs = abs(self.current_lon_error)
        depth_error_abs = abs(self.current_depth_error)
        mag_error_abs = abs(self.current_mag_error)

        converged = (
            lat_error_abs < self.convergence_threshold and
            lon_error_abs < self.convergence_threshold and
            depth_error_abs < 5 and  # 深度误差<5km
            mag_error_abs < 0.1  # 震级误差<0.1
        )

        if converged and not hasattr(self, '_convergence_logged'):
            print(f"[EEW追标] 已收敛 - 完成{self.revision_count}回訂正")
            self._convergence_logged = True

        return converged

    def get_current_values(self):
        """
        获取当前报告值

        Returns:
            tuple: (lat, lon, depth, mag)
        """
        return (self.current_lat, self.current_lon,
                self.current_depth, self.current_mag)

    def consume_correction_flag(self):
        """
        消耗"需要播放訂正音频"标志

        Returns:
            bool: 是否需要播放訂正音频（只返回一次True）
        """
        if self.needs_correction_announcement:
            self.needs_correction_announcement = False
            return True
        return False

    def is_tracking_complete(self):
        """
        是否已完成所有修正

        Returns:
            bool: 是否已收敛到真实值
        """
        return self.is_converged() or not self.enabled


# ============================================================================
# 测试代码
# ============================================================================

def test_eew_tracker():
    """测试EEW追标器"""
    import time

    print("=" * 70)
    print("EEW追标器测试")
    print("=" * 70)

    # 创建追标器（真实震源：东京附近，M7.0，深度30km）
    tracker = EEWTracker(
        true_lat=35.7,
        true_lon=139.7,
        true_depth=30,
        true_mag=7.0,
        enabled=True
    )

    # 模拟站点逐步检测到地震波
    print("\n模拟追标过程:")
    print("-" * 70)

    station_counts = [0, 1, 2, 3, 5, 8, 13, 20, 30, 50]
    for i, count in enumerate(station_counts):
        t = i * 2  # 每2秒检测到更多站点
        updated = tracker.update(count, t)

        if updated:
            lat, lon, depth, mag = tracker.get_current_values()
            print(f"  -> 当前值: ({lat:.2f}, {lon:.2f}), {depth:.0f}km, M{mag:.1f}")

            if tracker.consume_correction_flag():
                print("     >>> 播放'訂正'音频")

        if tracker.is_converged():
            print("\n  *** 已收敛 ***")
            break

    # 最终结果
    print("\n" + "-" * 70)
    lat, lon, depth, mag = tracker.get_current_values()
    print(f"追标完成!")
    print(f"  最终值: ({lat:.2f}, {lon:.2f}), {depth:.0f}km, M{mag:.1f}")
    print(f"  真实值: ({tracker.true_lat:.2f}, {tracker.true_lon:.2f}), "
          f"{tracker.true_depth:.0f}km, M{tracker.true_mag:.1f}")
    print(f"  总修正次数: {tracker.revision_count}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_eew_tracker()
