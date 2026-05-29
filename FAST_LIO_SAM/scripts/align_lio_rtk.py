#!/usr/bin/env python3
"""
将 lio.csv 和 rtk.csv 按时间戳对齐，输出 aligned.csv

对齐方式：以 LIO 时间戳为基准，在 RTK 中找最近邻帧，记录时间差。

用法：
  python3 align_lio_rtk.py --dir /tmp/mapping_log
  python3 align_lio_rtk.py --lio lio.csv --rtk rtk.csv --output aligned.csv

输出列：
  timestamp, dt_ms,
  lio_x, lio_y, lio_z, lio_qx, lio_qy, lio_qz, lio_qw,
  rtk_x, rtk_y, rtk_z, rtk_qx, rtk_qy, rtk_qz, rtk_qw
  (dt_ms = LIO时间 - RTK时间，单位毫秒)
"""

import argparse
import csv
import os
import sys

import numpy as np


def load_csv(path):
    rows = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def align(lio_rows, rtk_rows, max_dt):
    rtk_stamps = np.array([r["timestamp"] for r in rtk_rows])
    result = []
    dropped = 0

    for lio in lio_rows:
        t = lio["timestamp"]
        idx = np.argmin(np.abs(rtk_stamps - t))
        dt = t - rtk_rows[idx]["timestamp"]

        if abs(dt) > max_dt:
            dropped += 1
            continue

        rtk = rtk_rows[idx]
        result.append({
            "timestamp": t,
            "dt_ms": round(dt * 1000, 2),
            "lio_x": lio["x"], "lio_y": lio["y"], "lio_z": lio["z"],
            "lio_qx": lio["qx"], "lio_qy": lio["qy"],
            "lio_qz": lio["qz"], "lio_qw": lio["qw"],
            "rtk_x": rtk["x"], "rtk_y": rtk["y"], "rtk_z": rtk["z"],
            "rtk_qx": rtk["qx"], "rtk_qy": rtk["qy"],
            "rtk_qz": rtk["qz"], "rtk_qw": rtk["qw"],
        })

    return result, dropped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", help="包含 lio.csv 和 rtk.csv 的目录")
    parser.add_argument("--lio", help="LIO csv 路径（与 --dir 二选一）")
    parser.add_argument("--rtk", help="RTK csv 路径（与 --dir 二选一）")
    parser.add_argument("--output", help="输出路径，默认 <dir>/aligned.csv")
    parser.add_argument("--max_dt", type=float, default=0.1, help="最大时间差(s)，默认 0.1")
    args = parser.parse_args()

    if args.dir:
        lio_path = os.path.join(args.dir, "lio.csv")
        rtk_path = os.path.join(args.dir, "rtk.csv")
        out_path = args.output or os.path.join(args.dir, "aligned.csv")
    elif args.lio and args.rtk:
        lio_path = args.lio
        rtk_path = args.rtk
        out_path = args.output or "aligned.csv"
    else:
        print("请指定 --dir 或同时指定 --lio 和 --rtk", file=sys.stderr)
        sys.exit(1)

    print(f"加载 LIO : {lio_path}")
    print(f"加载 RTK : {rtk_path}")
    lio_rows = load_csv(lio_path)
    rtk_rows = load_csv(rtk_path)
    print(f"  LIO {len(lio_rows)} 条，RTK {len(rtk_rows)} 条")

    aligned, dropped = align(lio_rows, rtk_rows, args.max_dt)
    print(f"  对齐成功 {len(aligned)} 条，丢弃 {dropped} 条（时间差 > {args.max_dt*1000:.0f}ms）")

    if aligned:
        dts = [abs(r["dt_ms"]) for r in aligned]
        print(f"  时间差统计: mean={sum(dts)/len(dts):.1f}ms  max={max(dts):.1f}ms")

    # 检测 LIO 重置：lio_x/y/z 同时接近 0（每次建图开始）
    print("\n--- LIO 原点重置检测（每次建图起点对应的 RTK 坐标）---")
    sessions = []
    in_origin = False
    for r in aligned:
        lio_dist = (r["lio_x"]**2 + r["lio_y"]**2 + r["lio_z"]**2) ** 0.5
        if lio_dist < 0.5 and not in_origin:
            in_origin = True
            sessions.append(r)
            print(f"  建图起点 t={r['timestamp']:.1f}  "
                  f"LIO=({r['lio_x']:.3f},{r['lio_y']:.3f},{r['lio_z']:.3f})  "
                  f"RTK=({r['rtk_x']:.3f},{r['rtk_y']:.3f},{r['rtk_z']:.3f})")
        elif lio_dist > 2.0:
            in_origin = False

    if len(sessions) >= 2:
        print(f"\n  共检测到 {len(sessions)} 次建图")
        print("  各次起点 RTK 坐标差值（相对第一次）:")
        r0 = sessions[0]
        for i, r in enumerate(sessions[1:], 1):
            dx = r["rtk_x"] - r0["rtk_x"]
            dy = r["rtk_y"] - r0["rtk_y"]
            dz = r["rtk_z"] - r0["rtk_z"]
            dist = (dx**2 + dy**2 + dz**2) ** 0.5
            print(f"    第{i+1}次 vs 第1次: dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m  总偏移={dist:.3f}m")

    fieldnames = [
        "timestamp", "dt_ms",
        "lio_x", "lio_y", "lio_z", "lio_qx", "lio_qy", "lio_qz", "lio_qw",
        "rtk_x", "rtk_y", "rtk_z", "rtk_qx", "rtk_qy", "rtk_qz", "rtk_qw",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(aligned)

    print(f"保存到: {out_path}")


if __name__ == "__main__":
    main()
