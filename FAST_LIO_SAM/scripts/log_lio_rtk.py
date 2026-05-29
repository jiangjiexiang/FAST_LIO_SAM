#!/usr/bin/env python3
"""
独立记录 LIO 和 RTK 位姿到两个 CSV，不做时间同步。

输出：
  <output_dir>/lio.csv   — timestamp, x, y, z, qx, qy, qz, qw
  <output_dir>/rtk.csv   — timestamp, x, y, z, qx, qy, qz, qw

用法：
  roslaunch fast_lio_sam mapping_mid360.launch log_output:=/tmp/mapping_log
  或手动：python3 log_lio_rtk.py --output_dir /tmp/mapping_log
"""

import argparse
import csv
import os
import signal
import sys

import rospy
from nav_msgs.msg import Odometry


def make_writer(path):
    f = open(path, "w", newline="")
    w = csv.writer(f)
    w.writerow(["timestamp", "x", "y", "z", "qx", "qy", "qz", "qw"])
    f.flush()
    return f, w


class LioRtkLogger:
    def __init__(self, output_dir, lio_topic, rtk_topic):
        os.makedirs(output_dir, exist_ok=True)
        lio_path = os.path.join(output_dir, "lio.csv")
        rtk_path = os.path.join(output_dir, "rtk.csv")

        self.lio_f, self.lio_w = make_writer(lio_path)
        self.rtk_f, self.rtk_w = make_writer(rtk_path)
        self.lio_count = 0
        self.rtk_count = 0

        rospy.Subscriber(lio_topic, Odometry, self.lio_cb, queue_size=200)
        rospy.Subscriber(rtk_topic, Odometry, self.rtk_cb, queue_size=200)

        rospy.loginfo(f"[lio_rtk_logger] LIO -> {lio_path}")
        rospy.loginfo(f"[lio_rtk_logger] RTK -> {rtk_path}")

    def lio_cb(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        t = msg.header.stamp.to_sec()
        self.lio_w.writerow([f"{t:.6f}",
                              f"{p.x:.6f}", f"{p.y:.6f}", f"{p.z:.6f}",
                              f"{q.x:.6f}", f"{q.y:.6f}", f"{q.z:.6f}", f"{q.w:.6f}"])
        self.lio_f.flush()
        self.lio_count += 1
        if self.lio_count % 50 == 0:
            rospy.loginfo(f"[lio_rtk_logger] LIO {self.lio_count} 条  ({p.x:.2f},{p.y:.2f},{p.z:.2f})")

    def rtk_cb(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        t = msg.header.stamp.to_sec()
        self.rtk_w.writerow([f"{t:.6f}",
                              f"{p.x:.6f}", f"{p.y:.6f}", f"{p.z:.6f}",
                              f"{q.x:.6f}", f"{q.y:.6f}", f"{q.z:.6f}", f"{q.w:.6f}"])
        self.rtk_f.flush()
        self.rtk_count += 1
        if self.rtk_count % 100 == 0:
            rospy.loginfo(f"[lio_rtk_logger] RTK {self.rtk_count} 条  ({p.x:.2f},{p.y:.2f},{p.z:.2f})")

    def close(self):
        self.lio_f.close()
        self.rtk_f.close()
        rospy.loginfo(f"[lio_rtk_logger] 完成: LIO {self.lio_count} 条, RTK {self.rtk_count} 条")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="/tmp/mapping_log")
    parser.add_argument("--lio_topic", default="/Odometry")
    parser.add_argument("--rtk_topic", default="/apollo/localization/ins570d/pose")
    args, _ = parser.parse_known_args()

    rospy.init_node("lio_rtk_logger", anonymous=True)

    logger = LioRtkLogger(args.output_dir, args.lio_topic, args.rtk_topic)

    def shutdown(sig, frame):
        logger.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    rospy.spin()
    logger.close()


if __name__ == "__main__":
    main()
