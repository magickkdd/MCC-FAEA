# Gymnasium-style interface summary

`LiberoEnv` follows the standard Gymnasium interaction pattern:

- `reset()` — start a new episode, return the first observation.
- `step(action)` — apply one action, return `(obs, reward, done, info)`.
- Episode ends when `done` is True (step limit) or when you stop calling step.

Reference: Towers et al., "Gymnasium: A standard interface for reinforcement
learning environments", https://gymnasium.farama.org

Differences from vanilla Gymnasium in this setup:

- Success is NOT the `done` flag. Always query `env.check_success()`.
- The action space is absolute end-effector Cartesian control (7 numbers), not
  joint velocities.
- Observations are privileged ground-truth state, not pixels.
