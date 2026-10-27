"""모양(참/거짓 격자)을 서로 겹쳐도 되는 직사각형 몇 개로 덮는다 — 꼭짓점 수를 줄이려고(같은 텍스처를 입히는 메시라 겹쳐도 화면은 같음).
cover(mask) → [(x0, y0, x1, y1)] (x1·y1 은 끝 다음 칸)"""
import numpy as np


def _grow(m, y, x):
    """(y, x)를 포함하는 칸 중 넓이가 가장 큰 직사각형(모양 안에서만)."""
    H, W = m.shape
    best = None
    # 위쪽 끝을 y 로 두고 아래로 내려가며 가능한 가로 폭을 좁혀 간다 + 위로도 늘려 본다
    for top in range(y, -1, -1):
        if not m[top, x]:
            break
        for bot in range(y, H):
            if not m[bot, x]:
                break
            rows = m[top:bot + 1]
            col = rows.all(0)
            l = x
            while l > 0 and col[l - 1]:
                l -= 1
            r = x
            while r < W - 1 and col[r + 1]:
                r += 1
            area = (bot - top + 1) * (r - l + 1)
            if best is None or area > best[0]:
                best = (area, (l, top, r + 1, bot + 1))
    return best[1]


def cover(mask):
    m = np.asarray(mask, bool); left = m.copy(); rects = []
    while left.any():
        ys, xs = np.where(left)
        k = np.argmin(ys * m.shape[1] + xs)
        x0, y0, x1, y1 = _grow(m, ys[k], xs[k])
        rects.append((x0, y0, x1, y1))
        left[y0:y1, x0:x1] = False
    # 다른 직사각형에 완전히 덮이는 것 지우기
    keep = []
    for i, r in enumerate(rects):
        cov = np.zeros_like(m)
        for j, s in enumerate(rects):
            if j != i and (j not in [k for k in range(len(rects)) if rects[k] is None]):
                cov[s[1]:s[3], s[0]:s[2]] = True
        x0, y0, x1, y1 = r
        if cov[y0:y1, x0:x1].all():
            rects[i] = None
        else:
            keep.append(r)
    return keep


def corners(rects):
    return {p for x0, y0, x1, y1 in rects for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))}
