"""地震历史记录系统（Scratch兼容）"""

import math
from typing import List, Tuple, Optional

class EarthquakeHistory:
    """地震履歴记录器 - 记录观测点数据用于事后分析"""

    def __init__(self):
        self.records: List[Tuple[float, int, str]] = []  # [(时刻, 类型码, 数据), ...]
        self.last_snapshot = ""  # 上次快照（避免重复记录）
        self.last_eew_revision = 0  # 上次EEW报号

    def clear(self):
        """清空历史记录"""
        self.records.clear()
        self.last_snapshot = ""
        self.last_eew_revision = 0

    def record_stations(self, time: float, stations: list):
        """记录站点数据（类型码3）

        Args:
            time: 当前时刻（秒）
            stations: Station对象列表
        """
        # 压缩站点震度数据（Scratch格式）
        compressed = ""
        for station in stations:
            # (震度 + 3) * 10，转为两位整数
            value = int((station.intensity + 3) * 10)
            # 限制在00-98之间
            value = max(0, min(98, value))
            compressed += f"{value:02d}"

        # 检查是否与上次相同（避免重复记录）
        if compressed != self.last_snapshot:
            # 格式：floor(时刻) + 数据
            record_data = f"{int(time)}{compressed}"
            self.records.append((time, 3, record_data))
            self.last_snapshot = compressed

    def record_eew(self, time: float, eew_info: dict, revision_count: int):
        """记录EEW信息（类型码2）

        Args:
            time: 当前时刻（秒）
            eew_info: EEW信息字典
            revision_count: 当前报号
        """
        if revision_count != self.last_eew_revision:
            # 压缩EEW数据
            compressed = self._compress_eew(eew_info, revision_count)
            self.records.append((time, 2, compressed))
            self.last_eew_revision = revision_count

    def _compress_eew(self, eew_info: dict, revision_count: int) -> str:
        """压缩EEW信息为字符串"""
        # 简化版：记录震级、深度、报号
        mag = eew_info.get('magnitude', 0)
        depth = eew_info.get('depth', 0)
        lat = eew_info.get('lat', 0)
        lon = eew_info.get('lon', 0)

        return f"{lat:.1f},{lon:.1f},{depth},{mag:.1f},{revision_count}"

    def get_summary(self) -> dict:
        """生成地震总结报告

        Returns:
            总结字典，包含：
            - total_records: 总记录数
            - duration: 记录时长（秒）
            - max_intensity: 最大震度
            - eew_revisions: EEW修正次数
        """
        if not self.records:
            return {
                'total_records': 0,
                'duration': 0,
                'max_intensity': 0,
                'eew_revisions': 0
            }

        # 统计信息
        duration = self.records[-1][0] - self.records[0][0] if len(self.records) > 1 else 0
        eew_count = sum(1 for _, type_code, _ in self.records if type_code == 2)
        station_count = sum(1 for _, type_code, _ in self.records if type_code == 3)

        # 计算最大震度（从站点记录中提取）
        max_intensity = -3
        for _, type_code, data in self.records:
            if type_code == 3:  # 站点数据
                # 跳过时间戳部分（前N位是时间戳）
                intensity_data = data[10:]  # 假设时间戳10位
                # 每两位表示一个站点震度
                for i in range(0, len(intensity_data), 2):
                    if i + 1 < len(intensity_data):
                        try:
                            value = int(intensity_data[i:i+2])
                            intensity = value / 10.0 - 3.0
                            max_intensity = max(max_intensity, intensity)
                        except ValueError:
                            continue

        return {
            'total_records': len(self.records),
            'duration': duration,
            'max_intensity': max_intensity,
            'eew_revisions': eew_count,
            'station_records': station_count
        }

    def export_to_file(self, filename: str):
        """导出历史记录到文件

        Args:
            filename: 输出文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# 地震履歴记录\n")
                f.write(f"# 总记录数: {len(self.records)}\n")
                f.write("# 格式: 时刻,类型码,数据\n\n")

                for time, type_code, data in self.records:
                    f.write(f"{time:.2f},{type_code},{data}\n")

            print(f"[履歴] 已导出 {len(self.records)} 条记录到 {filename}")
        except Exception as e:
            print(f"[履歴] 导出失败: {e}")
