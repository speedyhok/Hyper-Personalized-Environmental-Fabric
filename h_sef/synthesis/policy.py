# h_sef/synthesis/policy.py
"""
Closed-Loop Reinforcement Learning Control Policy.
Implements a Q-Learning agent to optimize environmental parameters.
Maximizes user Valence while driving Arousal toward state-dependent targets.
"""

import random
from typing import Dict, Any, Tuple
import numpy as np

class ClosedLoopRLPolicy:
    def __init__(self, target_state: str = "Focus"):
        # Target state defines target arousal:
        # "Focus" wants moderate-high arousal (0.4)
        # "Calm" wants low arousal (-0.6)
        self.target_state = target_state
        self.target_arousal = 0.4 if target_state == "Focus" else -0.6
        
        # RL Hyperparameters
        self.alpha = 0.1     # Learning rate
        self.gamma = 0.9     # Discount factor
        self.epsilon = 0.1   # Exploration rate
        
        # Action space: 6 discrete environmental adjustments
        # 0: Decrease temperature (Cooling)
        # 1: Increase temperature (Heating)
        # 2: Dim lighting (low lux, warm spectrum)
        # 3: Brighten lighting (high lux, cool spectrum)
        # 4: Activate relaxation beats (Alpha)
        # 5: Activate concentration beats (Gamma)
        self.action_labels = [
            "Cool Room Temp",
            "Warm Room Temp",
            "Dim Lights",
            "Brighten Lights",
            "Alpha Beats (Relax)",
            "Gamma Beats (Focus)"
        ]
        self.n_actions = len(self.action_labels)
        
        # Discretized State Space:
        # Valence: Negative (<0), Positive (>=0) [2 buckets]
        # Arousal: Low (<-0.2), Neutral (-0.2 to 0.2), High (>0.2) [3 buckets]
        # Cognitive Load: Low (<0.5), High (>=0.5) [2 buckets]
        # Total unique states = 2 * 3 * 2 = 12
        self.q_table: Dict[Tuple[int, int, int], np.ndarray] = {}

    def _get_discrete_state(self, valence: float, arousal: float, cog_load: float) -> Tuple[int, int, int]:
        v_idx = 0 if valence < 0.0 else 1
        
        if arousal < -0.2:
            a_idx = 0
        elif arousal > 0.2:
            a_idx = 2
        else:
            a_idx = 1
            
        l_idx = 0 if cog_load < 0.5 else 1
        
        return (v_idx, a_idx, l_idx)

    def _init_state_in_q_table(self, state_key: Tuple[int, int, int]):
        if state_key not in self.q_table:
            # Initialize with small random values to break ties
            self.q_table[state_key] = np.random.uniform(0.0, 0.1, self.n_actions)

    def select_action(self, valence: float, arousal: float, cog_load: float) -> Tuple[int, str]:
        """Selects an action using an epsilon-greedy policy."""
        state_key = self._get_discrete_state(valence, arousal, cog_load)
        self._init_state_in_q_table(state_key)
        
        if random.random() < self.epsilon:
            # Explore: pick random action
            action_idx = random.randint(0, self.n_actions - 1)
        else:
            # Exploit: pick action with max Q-value
            action_idx = int(np.argmax(self.q_table[state_key]))
            
        return action_idx, self.action_labels[action_idx]

    def compute_reward(self, valence: float, arousal: float, action_idx: int) -> float:
        """
        Reward Function:
        R = Valence - 0.7 * |Arousal - TargetArousal| - 0.05 * ActionPenalty
        Promotes positive emotional valence and target arousal while penalizing actuator noise.
        """
        arousal_error = abs(arousal - self.target_arousal)
        
        # Penalize action changes to avoid rapid oscillating actuator fluctuations
        action_penalty = 0.0
        if action_idx in [0, 1]:  # Temperature adjustments have mechanical cost
            action_penalty = 0.1
            
        reward = valence - (0.7 * arousal_error) - (0.05 * action_penalty)
        return float(reward)

    def update_q_value(
        self,
        curr_state: Dict[str, float],
        action_idx: int,
        reward: float,
        next_state: Dict[str, float]
    ) -> float:
        """Performs a Q-learning update step."""
        s_curr = self._get_discrete_state(
            curr_state["valence"], curr_state["arousal"], curr_state["cognitive_load"]
        )
        s_next = self._get_discrete_state(
            next_state["valence"], next_state["arousal"], next_state["cognitive_load"]
        )
        
        self._init_state_in_q_table(s_curr)
        self._init_state_in_q_table(s_next)
        
        # Bellman Equation update
        old_q = self.q_table[s_curr][action_idx]
        max_next_q = np.max(self.q_table[s_next])
        
        new_q = old_q + self.alpha * (reward + self.gamma * max_next_q - old_q)
        self.q_table[s_curr][action_idx] = new_q
        
        return float(new_q)
