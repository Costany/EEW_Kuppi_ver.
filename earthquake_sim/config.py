# 地震模拟配置参数

# 波速 (km/s)
P_WAVE_SPEED = 7.3
S_WAVE_SPEED = 4.1

# 地球参数
EARTH_RADIUS = 6371  # km
LAT_KM = 110.9493189  # 纬度1度对应的km
LON_KM = 87.3271156   # 经度1度对应的km (日本纬度约35度)

# Scratch 原版的投影/距离近似（以日本附近为基准的墨卡托式投影到“km平面”）
# 说明：Scratch 先把经纬度转换成平面坐标（单位近似为 km），再在该平面里计算波前与距离，
# 因此在屏幕上表现为“正圆扩散”。
SCRATCH_REF_LON = 138.0
SCRATCH_REF_LAT = 37.0
SCRATCH_X_KM_PER_DEG = 89.2  # (lon - 138) * 89.2
# 89.22 * (5473695 / 95534) 来自 Scratch 项目中的常数（用于墨卡托 y 的缩放）
SCRATCH_MERCATOR_Y_SCALE = 89.22 * (5473695 / 95534)

# JMA震度计算参数
# 计测震度 = 2 * log10(加速度) + 0.94
# 或使用距离衰减公式

# 震度等级颜色 (JMA标准)
INTENSITY_COLORS = {
    0: (200, 200, 200),   # 震度0 - 灰色
    1: (100, 150, 200),   # 震度1 - 浅蓝
    2: (50, 180, 50),     # 震度2 - 绿色
    3: (200, 200, 0),     # 震度3 - 黄色
    4: (255, 150, 0),     # 震度4 - 橙色
    5: (255, 80, 0),      # 震度5弱
    '5+': (255, 0, 0),    # 震度5强 - 红色
    6: (180, 0, 50),      # 震度6弱
    '6+': (150, 0, 100),  # 震度6强
    7: (100, 0, 100),     # 震度7 - 紫色
}

# 窗口设置
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

# 地图范围 (日本)
MAP_BOUNDS = {
    'min_lon': 122.0,
    'max_lon': 154.0,
    'min_lat': 24.0,
    'max_lat': 46.0,
}

# 多震源模式常量
MODE_SINGLE = 0
MODE_MULTI = 1

# 多震源子状态
MULTI_DRAW_FAULT = 0
MULTI_SELECT_SOURCES = 1
MULTI_SELECT_START = 2
MULTI_SELECT_DIR = 3
MULTI_SET_PARAMS = 4
MULTI_RUNNING = 5

# 默认破裂速度
DEFAULT_RUPTURE_VELOCITY = 2.5  # km/s
