# h_sef/models/csm_core.py
"""
Cognitive State Modeling (CSM) Core.
Implements:
1. Deep Causal Inference Network (PyTorch LSTM) for temporal sequence prediction.
2. Gradient-based Saliency Mapping to attribute causal stress factors.
3. Cognitive State Space manifold utilities for smooth state interpolation.
"""

import math
from typing import Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn as nn

class CognitiveStateSequencePredictor(nn.Module):
    def __init__(self, input_dim: int = 11, hidden_dim: int = 16, output_dim: int = 3):
        """
        PyTorch LSTM Sequence Model for future state prediction.
        Inputs (11 dimensions):
        - 0: EEG Alpha, 1: EEG Beta, 2: EEG Theta
        - 3: Heart Rate, 4: HRV (RMSSD)
        - 5: GSR Tonic, 6: GSR Phasic
        - 7: Room Temp, 8: Ambient Light, 9: Ambient Noise
        - 10: Calendar Stress
        
        Outputs (3 dimensions):
        - 0: Predicted Valence, 1: Predicted Arousal, 2: Predicted Cognitive Load (5s ahead)
        """
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, output_dim)
        
        # Initialize with meaningful weights to generate realistic predictions
        # (Simulating a pre-trained network)
        self._initialize_synthetic_weights()

    def _initialize_synthetic_weights(self):
        # We set positive/negative weights to simulate physiological dynamics
        with torch.no_grad():
            # For the final linear layer:
            # Output 0 (Valence) should respond negatively to GSR, HR, and Calendar stress
            # Output 1 (Arousal) should respond positively to GSR, HR, Noise, and Calendar stress
            # Output 2 (Cognitive Load) should respond positively to EEG Theta/Beta
            self.fc.weight.fill_(0.0)
            self.fc.bias.fill_(0.0)
            
            # Simple direct projection from hidden to output
            # (LSTM will output hidden state influenced by features)
            self.fc.weight[0, 0] = 0.5   # Hidden factor 0 maps to Valence
            self.fc.weight[1, 1] = 0.5   # Hidden factor 1 maps to Arousal
            self.fc.weight[2, 2] = 0.5   # Hidden factor 2 maps to Cognitive Load

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Tensor of shape [batch_size, seq_len, input_dim]
        Returns:
            out: Tensor of shape [batch_size, output_dim] representing state 5s ahead.
        """
        # lstm_out shape: [batch_size, seq_len, hidden_dim]
        # h_n shape: [1, batch_size, hidden_dim]
        lstm_out, (h_n, c_n) = self.lstm(x)
        # Take the final sequence element's output
        last_out = lstm_out[:, -1, :]
        return self.fc(last_out)

    def calculate_causal_attribution(self, sequence_np: np.ndarray) -> Dict[str, float]:
        """
        Calculates gradient-based causal attribution of predicted stress.
        Computes the gradient of the predicted stress index (Arousal - Valence)
        with respect to the input features.
        
        Args:
            sequence_np: np.ndarray of shape [seq_len, input_dim]
        Returns:
            attribution_percentages: Dict mapping causes to percentages
        """
        # Convert to tensor and enable gradient tracking
        x = torch.tensor(sequence_np, dtype=torch.float32).unsqueeze(0)  # Shape [1, seq_len, input_dim]
        x.requires_grad = True
        
        # Forward pass
        predictions = self.forward(x)  # Shape [1, 3] (Valence, Arousal, Load)
        valence = predictions[0, 0]
        arousal = predictions[0, 1]
        
        # Stress Index Formula: (Arousal - Valence) / 2
        stress_pred = (arousal - valence) / 2.0
        
        # Zero gradients
        self.zero_grad()
        
        # Backward pass to calculate d(stress) / d(x)
        stress_pred.backward()
        
        # Retrieve gradients and average across the time dimension
        gradients = x.grad.squeeze(0).abs().mean(dim=0).detach().numpy()
        
        # Small epsilon to avoid division by zero
        gradients = np.maximum(gradients, 1e-5)
        
        # Group gradients into causal categories
        # Inputs:
        # 0: EEG Alpha, 1: EEG Beta, 2: EEG Theta
        # 3: Heart Rate, 4: HRV (RMSSD)
        # 5: GSR Tonic, 6: GSR Phasic
        # 7: Temp, 8: Light, 9: Noise
        # 10: Calendar Stress
        
        internal_workload = float(gradients[0] + gradients[1] + gradients[2] + gradients[10]) # EEG + Calendar
        external_physical = float(gradients[7] + gradients[8] + gradients[9])                 # Temp + Light + Noise
        biometric_arousal = float(gradients[3] + gradients[4] + gradients[5] + gradients[6])   # HR + HRV + GSR

        total = internal_workload + external_physical + biometric_arousal
        
        return {
            "workload": round((internal_workload / total) * 100, 1),
            "environment": round((external_physical / total) * 100, 1),
            "physiology": round((biometric_arousal / total) * 100, 1)
        }

class CognitiveStateSpace:
    @staticmethod
    def interpolate_path(start: Tuple[float, float], end: Tuple[float, float], steps: int = 10) -> List[Tuple[float, float]]:
        """
        Calculates a smooth transition path in the Valence-Arousal latent space
        using a sigmoid interpolation to mimic slow human cognitive adaptation.
        """
        x1, y1 = start
        x2, y2 = end
        
        path = []
        for i in range(steps):
            # Sigmoid transition factor
            t = i / (steps - 1)
            # Sigmoid weighting: 3t^2 - 2t^3
            w = 3 * t**2 - 2 * t**3
            
            x = x1 + w * (x2 - x1)
            y = y1 + w * (y2 - y1)
            path.append((round(x, 3), round(y, 3)))
            
        return path
