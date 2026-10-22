"""LiberoEnv — FAEA 复现的仿真 wrapper（agent 唯一仿真入口）。

设计约束（见 SPEC.md §4.1）：
- agent 只依赖本模块文档化的 API；LIBERO/robosuite 内部细节不外泄
- reset() 计 1 try；trial cap 由 runner 预写在 .sim_state.json 里，超限抛异常
- 视频逐 try 自动录制，obs 为特权状态（不推进物理）
- 成功判定唯一权威信号：check_success()（LIBERO 任务原生谓词）
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
# FAEA 专属 LIBERO 配置（官方 LIBERO 仓库路径），不占用 ~/.libero 全局配置
os.environ.setdefault("LIBERO_CONFIG_PATH", "/home/czx/.libero-faea")

import numpy as np

STATE_FILENAME = ".sim_state.json"
_DEFAULT_VIDEO_RES = 256
_DEFAULT_VIDEO_FPS = 20

# suite 名 -> LIBERO benchmark 注册类名（小写）
SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_90", "libero_10")


class TrialCapExceeded(RuntimeError):
    """仿真尝试次数（reset 次数）达到本工作区预设上限。"""


def _load_benchmark():
    from libero.libero import benchmark

    return benchmark


def list_tasks() -> list[dict]:
    """枚举全部 LIBERO 任务：返回 [{task_id, suite, index, language, task_name}]。

    task_id = "<suite>_<index>"，index 为该 suite 任务表的 0 起位置。
    """
    benchmark = _load_benchmark()
    out = []
    for suite in ("libero_spatial", "libero_object", "libero_goal", "libero_90"):
        bench = benchmark.get_benchmark_dict()[suite]()
        for i in range(bench.n_tasks):
            task = bench.get_task(i)
            out.append(
                {
                    "task_id": f"{suite}_{i}",
                    "suite": suite,
                    "index": i,
                    "language": task.language,
                    "task_name": task.name,
                }
            )
    return out


class LiberoEnv:
    """一个 LIBERO 任务的仿真环境（绝对末端位姿控制 + 特权状态 + 自动录像）。

    用法：
        env = LiberoEnv(task_id="libero_object_0")
        obs = env.reset()                      # 1 try
        obs, reward, done, info = env.step(a)  # a = [x,y,z,roll,pitch,yaw,gripper]
        state = env.get_obs()                  # 特权状态，不推进物理
        ok = env.check_success()
        env.save_video()                       # 结束当前 try 的录像（可选）
        env.close()
    """

    def __init__(
        self,
        task_id: str,
        record_video: bool = True,
        trial_cap: int | None = None,
        video_res: int = _DEFAULT_VIDEO_RES,
        video_fps: int = _DEFAULT_VIDEO_FPS,
        max_steps: int = 1500,
        seed: int = 0,
    ):
        self.task_id = task_id
        self._video_fps = video_fps
        self._max_steps = max_steps
        self._record = record_video

        suite, index = self._parse_task_id(task_id)
        benchmark = _load_benchmark()
        bench = benchmark.get_benchmark_dict()[suite]()
        assert 0 <= index < bench.n_tasks, f"index {index} 超出 {suite} 共 {bench.n_tasks} 个任务"
        task = bench.get_task(index)
        bddl_path = bench.get_task_bddl_file_path(index)
        self.task_name = task.name
        self.language = task.language
        # torch>=2.6 默认 weights_only=True，旧 .pruned_init（含 numpy 数组）会被拒；
        # 来源为官方 LIBERO 仓库，可信，显式关闭
        import torch
        from libero.libero import get_libero_path

        init_states_path = os.path.join(
            get_libero_path("init_states"), task.problem_folder, task.init_states_file
        )
        init_states = torch.load(init_states_path, weights_only=False, map_location="cpu")
        self._init_state = np.asarray(init_states[0])

        # try 计数与 cap：状态文件由 runner 预写，跨脚本进程存活。
        # 默认在 cwd；runner 经 FAEA_STATE_PATH 指到 agent 可写范围之外（防篡改）
        self._state_path = Path(
            os.environ.get("FAEA_STATE_PATH", str(Path.cwd() / STATE_FILENAME))
        )
        state = self._read_state()
        self._trial_cap = trial_cap if trial_cap is not None else state.get("trial_cap")
        self._try_count = int(state.get("try_count", 0))
        self._persist_state()

        np.random.seed(seed)

        self._env = self._make_env(bddl_path, video_res)
        self._t = 0
        self._frames: list[np.ndarray] = []
        self._try_index = self._try_count  # 当前 try 的编号（从 1 起）

    # ------------------------------------------------------------------ 公开 API

    def reset(self) -> dict:
        """重置到任务初始状态并开始一次新的仿真尝试。每次调用计 1 try。"""
        if self._trial_cap is not None and self._try_count >= self._trial_cap:
            raise TrialCapExceeded(
                f"trial cap {self._trial_cap} exceeded (tries={self._try_count}). "
                "Stop and write meta.json with your best result."
            )
        self._try_count += 1
        self._try_index = self._try_count
        self._persist_state()

        self._env.reset()
        obs = self._env.set_init_state(self._init_state)
        self._t = 0
        self._frames = []
        if self._record:
            self._frames.append(self._camera_image(obs))
        return self._privileged(obs)

    def step(self, action):
        """推进一步。action = [x, y, z, roll, pitch, yaw, gripper]。

        前 6 维是世界系绝对末端位姿目标（米/弧度），第 7 维 gripper：
        +1 张开，-1 闭合。done=True 仅表示步数到上限，不表示成功。
        """
        action = np.asarray(action, dtype=np.float64).reshape(-1)
        assert action.shape == (7,), f"action 必须是 7 维，收到 {action.shape}"
        wire = action.copy()
        wire[6] = -wire[6]  # 文档约定 +1=张开/-1=闭合；robosuite Panda 相反，此处翻转
        obs, reward, done, info = self._env.step(wire)
        self._t += 1
        if self._record:
            self._frames.append(self._camera_image(obs))
        done = bool(done) or self._t >= self._max_steps
        info = dict(info or {})
        info["success"] = self._env.check_success()
        info["step_count"] = self._t
        return self._privileged(obs), float(reward), done, info

    def get_obs(self) -> dict:
        """特权状态观测（不推进物理，不消耗 try）。"""
        return self._privileged(self._env.env._get_observations())

    def check_success(self) -> bool:
        """任务原生成功谓词（唯一权威成功信号）。"""
        return bool(self._env.check_success())

    def save_video(self, path: str | None = None) -> str | None:
        """把当前 try 的录像落盘。不录视频或无帧时返回 None。"""
        if not self._record or not self._frames:
            return None
        import imageio

        path = path or f"try_{self._try_index:03d}.mp4"
        with imageio.get_writer(path, fps=self._video_fps, macro_block_size=1) as w:
            for f in self._frames:
                w.append_data(f)
        self._frames = []
        return path

    def close(self) -> None:
        try:
            if self._record and self._frames:
                self.save_video()
        finally:
            try:
                self._env.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _parse_task_id(task_id: str) -> tuple[str, int]:
        suite, _, idx = task_id.rpartition("_")
        if suite not in SUITES or not idx.isdigit():
            raise ValueError(
                f"task_id 形如 'libero_object_0'（<suite>_<index>），收到: {task_id!r}"
            )
        return suite, int(idx)

    @staticmethod
    def _make_env(bddl_path: str, video_res: int):
        import robosuite as suite
        from libero.libero.envs import OffScreenRenderEnv

        # 绝对末端控制：劫持控制器配置加载，为 OSC_POSE 注入 absolute/world
        orig_load = suite.load_controller_config

        def _patched_load(*args, **kwargs):
            cfg = orig_load(*args, **kwargs)
            if isinstance(cfg, dict) and cfg.get("type") in ("OSC_POSE", "OSC_POSITION"):
                # robosuite 1.4.0：control_delta=False 即绝对位姿目标（世界系，
                # 无缩放）；姿态为轴角（axis-angle）而非欧拉角
                cfg["control_delta"] = False
            return cfg

        suite.load_controller_config = _patched_load
        try:
            env = OffScreenRenderEnv(
                bddl_file_name=bddl_path,
                camera_heights=video_res,
                camera_widths=video_res,
            )
        finally:
            suite.load_controller_config = orig_load
        return env

    def _camera_image(self, obs: dict) -> np.ndarray:
        img = obs.get("agentview_image")
        if img is None:
            return np.zeros((self._video_res, self._video_res, 3), dtype=np.uint8)
        return np.asarray(img)[::-1].copy()  # 转正图像方向

    def _privileged(self, obs: dict) -> dict:
        import mujoco

        sim = self._env.sim
        model, data = sim.model, sim.data
        eef = {
            "eef_pos": np.asarray(obs["robot0_eef_pos"], dtype=float).tolist(),
            "eef_quat": np.asarray(obs["robot0_eef_quat"], dtype=float).tolist(),
            "gripper_open": float(
                np.clip(np.mean(np.abs(obs["robot0_gripper_qpos"])) / 0.05, 0.0, 1.0)
            ),
        }
        objects = {}
        for j in range(model.njnt):
            if model.jnt_type[j] != int(mujoco.mjtJoint.mjJNT_FREE):
                continue
            bid = int(model.jnt_bodyid[j])
            try:
                name = model.body(bid).name
            except Exception:
                name = f"body_{bid}"
            adr = int(model.jnt_qposadr[j])
            objects[name] = {
                "pos": data.qpos[adr : adr + 3].tolist(),
                "quat": data.qpos[adr + 3 : adr + 7].tolist(),
            }
        return {
            **eef,
            "objects": objects,
            "articulated_joints": self._articulated_joints(model, data, mujoco),
            "task_info": {
                "task_id": self.task_id,
                "language": self.language,
                "try_count": self._try_count,
                "trial_cap": self._trial_cap,
                "step_count": self._t,
            },
        }

    @staticmethod
    def _articulated_joints(model, data, mujoco) -> dict:
        """铰接物体（抽屉/门/旋钮）的关节状态，供观测使用。

        只包含非机器人 body 的 slide/hinge 关节。qpos 单位：
        slide = 米，hinge = 弧度。handle_pos 优先取 handle 网格中心，
        没有 handle 网格时退回该 body 所有几何体的中心。
        """
        out = {}
        types = {
            int(mujoco.mjtJoint.mjJNT_SLIDE): "slide",
            int(mujoco.mjtJoint.mjJNT_HINGE): "hinge",
        }
        for j in range(model.njnt):
            jtype = int(model.jnt_type[j])
            if jtype not in types:
                continue
            bid = int(model.jnt_bodyid[j])
            bname = model.body(bid).name
            if bname.startswith(("robot0_", "gripper0_")):
                continue
            adr = int(model.jnt_qposadr[j])
            lo, hi = (float(x) for x in model.jnt_range[j])
            qpos = float(data.qpos[adr])
            axis = np.asarray(data.xaxis[j], dtype=float)
            anchor = np.asarray(data.xanchor[j], dtype=float)
            body_pos = np.asarray(data.xpos[bid], dtype=float)
            body_quat = np.asarray(data.xquat[bid], dtype=float)

            geoms = [g for g in range(model.ngeom) if int(model.geom_bodyid[g]) == bid]
            handle_pos = None
            handle_mesh = None
            for g in geoms:
                if int(model.geom_type[g]) != int(mujoco.mjtGeom.mjGEOM_MESH):
                    continue
                try:
                    mesh_name = model.mesh(int(model.geom_dataid[g])).name
                except Exception:
                    continue
                if "handle" in (mesh_name or "").lower():
                    handle_pos = np.asarray(data.geom_xpos[g], dtype=float)
                    handle_mesh = mesh_name
                    break
            if handle_pos is None:
                if geoms:
                    handle_pos = np.asarray(
                        [data.geom_xpos[g] for g in geoms], dtype=float
                    ).mean(axis=0)
                else:
                    handle_pos = body_pos

            rec = {
                "body": bname,
                "type": types[jtype],
                "qpos": qpos,
                "range": [lo, hi],
                "travel": hi - lo,
                "axis_world": axis.tolist(),
                "anchor_pos": anchor.tolist(),
                "body_pos": body_pos.tolist(),
                "body_quat": body_quat.tolist(),
                "handle_pos": handle_pos.tolist(),
                "handle_mesh": handle_mesh,
            }
            if types[jtype] == "slide" and hi > lo:
                closed = hi if abs(hi) < abs(lo) else lo
                open_pos = hi if closed == lo else lo
                rec["open_fraction"] = (qpos - closed) / (open_pos - closed)
                rec["opening_direction"] = (
                    axis * (1.0 if open_pos > closed else -1.0)
                ).tolist()
            else:
                rel = handle_pos - anchor
                radial = rel - axis * float(np.dot(rel, axis))
                rec["handle_radius"] = float(np.linalg.norm(radial))
            out[model.joint(j).name] = rec
        return out

    def _read_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text())
        except Exception:
            return {}

    def _persist_state(self) -> None:
        self._state_path.write_text(
            json.dumps({"try_count": self._try_count, "trial_cap": self._trial_cap})
        )
