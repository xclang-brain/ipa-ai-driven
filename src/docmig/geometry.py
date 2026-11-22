"""図形と矢印の位置の計算。長さの単位は EMU（1 pt = 12700 EMU）。"""

from __future__ import annotations

import math

EMU_PER_PT = 12700

# 端点からこの距離（pt）より遠い図形は、接続先の候補にしない
NEAR_LIMIT_PT = 12.0


def rotate(point: tuple[float, float], center: tuple[float, float], rot_60000: int):
    """point を center のまわりに回転する。rot_60000 は 1/60000 度単位（時計回り）。"""
    if not rot_60000:
        return point
    angle = math.radians(rot_60000 / 60000.0)
    dx, dy = point[0] - center[0], point[1] - center[1]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return (center[0] + dx * cos_a - dy * sin_a, center[1] + dx * sin_a + dy * cos_a)


def connector_endpoints(bbox, flip_h: bool, flip_v: bool, rot_60000: int):
    """線やコネクタの始点と終点を求める。

    線は、外接する四角の対角を結ぶものとして保存されている。反転がなければ
    左上が始点、右下が終点になる。回転は四角の中心のまわりにかかる。
    """
    x, y, w, h = bbox
    start = (x + (w if flip_h else 0), y + (h if flip_v else 0))
    end = (x + (0 if flip_h else w), y + (0 if flip_v else h))
    center = (x + w / 2, y + h / 2)
    return rotate(start, center, rot_60000), rotate(end, center, rot_60000)


def distance_to_border(point, bbox) -> float:
    """点から四角の辺までの距離。点が四角の内側にあるときは、最も近い辺までの距離。"""
    px, py = point
    x, y, w, h = bbox
    inside = x <= px <= x + w and y <= py <= y + h
    if inside:
        return min(px - x, x + w - px, py - y, y + h - py)
    dx = max(x - px, 0, px - (x + w))
    dy = max(y - py, 0, py - (y + h))
    return math.hypot(dx, dy)


def nearest_shape(point, shapes, limit_pt: float = NEAR_LIMIT_PT):
    """点に最も近い図形を返す。limit_pt より遠い場合は None。

    距離が同じ場合は小さい図形を選ぶ（大きな枠の中に置かれた図形を優先するため）。
    """
    best = None
    for shape in shapes:
        x, y, w, h = shape["bbox"]
        if w <= 0 and h <= 0:
            continue
        dist = distance_to_border(point, shape["bbox"]) / EMU_PER_PT
        key = (round(dist, 1), w * h)
        if best is None or key < best[0]:
            best = (key, shape, dist)
    if best is None or best[2] > limit_pt:
        return None
    return {"shape": best[1]["id"], "distance_pt": round(best[2], 1)}
